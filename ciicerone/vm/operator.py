"""VM Operator for controlling virtual machines.

.. note::
    VM automation is **experimental** and **not part of v1**. Most operator
    methods are unimplemented stubs (``NotImplementedError``) and exist only
    as the design target for the post-v1 roadmap. Do not rely on this module
    in production.

This module provides the interface for AI agents to interact with VMs,
including command execution, file transfer, and screenshot capture.
"""

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path

from .models import (
    VMConfig,
    VMInfo,
    VMState,
    CommandResult,
    InfrastructureConfig,
    HypervisorType,
)

logger = logging.getLogger(__name__)


class VMOperator:
    """
    Interface for AI agent to control virtual machines.

    Provides capabilities for:
    - VM lifecycle management (create, start, stop, destroy)
    - Command execution (SSH for Linux, WinRM for Windows)
    - File transfer (upload/download)
    - Screenshot capture
    - Snapshot management

    Supports multiple hypervisors:
    - Docker (default, easiest to set up)
    - Proxmox VE
    - VMware vSphere
    - Libvirt/KVM
    - Cloud providers (AWS, Azure, GCP)

    Example:
        config = InfrastructureConfig(hypervisor_type=HypervisorType.DOCKER)
        operator = VMOperator(config)

        # Create attacker VM
        vm = await operator.create_vm(
            VMConfig(name="attacker", template="ubuntu-attacker", is_attacker=True)
        )

        # Execute command
        result = await operator.execute_command(vm.vm_id, "nmap -sV target")
        print(result.stdout)
    """

    def __init__(self, config: Optional[InfrastructureConfig] = None):
        """Initialize VM operator.

        Args:
            config: Infrastructure configuration. Defaults to Docker-based setup.
        """
        self.config = config or InfrastructureConfig()
        self._hypervisor = self._init_hypervisor()
        self._active_vms: Dict[str, VMInfo] = {}
        self._connections: Dict[str, Any] = {}

    def _init_hypervisor(self) -> "BaseHypervisor":
        """Initialize the hypervisor client based on config."""
        hypervisor_map = {
            HypervisorType.DOCKER: DockerHypervisor,
            HypervisorType.PROXMOX: ProxmoxHypervisor,
            HypervisorType.LIBVIRT: LibvirtHypervisor,
        }

        hypervisor_class = hypervisor_map.get(
            self.config.hypervisor_type,
            DockerHypervisor
        )
        return hypervisor_class(self.config)

    async def create_vm(self, vm_config: VMConfig) -> VMInfo:
        """
        Create a new VM from template.

        Args:
            vm_config: Configuration for the new VM

        Returns:
            VMInfo with details of created VM
        """
        logger.info(f"Creating VM: {vm_config.name} from template {vm_config.template}")

        # Create VM through hypervisor
        vm_id = await self._hypervisor.create_vm(vm_config)

        # Wait for VM to be ready
        ip_address = await self._wait_for_vm_ready(vm_id, vm_config)

        vm_info = VMInfo(
            vm_id=vm_id,
            name=vm_config.name,
            state=VMState.RUNNING,
            os_type=vm_config.os_type,
            ip_address=ip_address,
            config=vm_config,
        )

        self._active_vms[vm_id] = vm_info
        logger.info(f"VM created: {vm_id} at {ip_address}")

        return vm_info

    async def execute_command(
        self,
        vm_id: str,
        command: str,
        timeout_seconds: int = 60,
        capture_screenshot: bool = False,
        working_dir: Optional[str] = None,
    ) -> CommandResult:
        """
        Execute a command on the VM.

        Args:
            vm_id: ID of target VM
            command: Command to execute
            timeout_seconds: Command timeout
            capture_screenshot: Whether to capture screen after command
            working_dir: Working directory for command

        Returns:
            CommandResult with output and optional screenshot
        """
        start_time = time.time()

        # Get VM info
        vm_info = self._active_vms.get(vm_id)
        if not vm_info:
            raise ValueError(f"VM not found: {vm_id}")

        # Get or create connection
        conn = await self._get_connection(vm_id, vm_info)

        # Execute command
        try:
            if vm_info.os_type == "windows":
                stdout, stderr, exit_code = await self._execute_winrm(
                    conn, command, timeout_seconds, working_dir
                )
            else:
                stdout, stderr, exit_code = await self._execute_ssh(
                    conn, command, timeout_seconds, working_dir
                )
        except asyncio.TimeoutError:
            return CommandResult(
                command=command,
                stdout="",
                stderr="Command timed out",
                exit_code=-1,
                execution_time_ms=(time.time() - start_time) * 1000,
                vm_id=vm_id,
            )

        execution_time = (time.time() - start_time) * 1000

        # Capture screenshot if requested
        screenshot = None
        if capture_screenshot:
            screenshot = await self.capture_screenshot(vm_id)

        return CommandResult(
            command=command,
            stdout=stdout,
            stderr=stderr,
            exit_code=exit_code,
            execution_time_ms=execution_time,
            screenshot=screenshot,
            vm_id=vm_id,
        )

    async def execute_script(
        self,
        vm_id: str,
        script_content: str,
        script_type: str = "bash",
        args: Optional[List[str]] = None,
    ) -> CommandResult:
        """
        Upload and execute a script on the VM.

        Args:
            vm_id: Target VM ID
            script_content: Script content to execute
            script_type: Type of script (bash, python, powershell)
            args: Arguments to pass to script

        Returns:
            CommandResult with script output
        """
        # Determine script extension and interpreter
        script_map = {
            "bash": (".sh", "bash"),
            "python": (".py", "python3"),
            "powershell": (".ps1", "powershell -ExecutionPolicy Bypass -File"),
            "perl": (".pl", "perl"),
            "ruby": (".rb", "ruby"),
        }

        ext, interpreter = script_map.get(script_type, (".sh", "bash"))

        # Generate unique script path
        script_name = f"ciicerone_script_{int(time.time())}{ext}"
        if script_type == "powershell":
            remote_path = f"C:\\Windows\\Temp\\{script_name}"
        else:
            remote_path = f"/tmp/{script_name}"

        # Upload script
        await self.upload_file(vm_id, script_content.encode(), remote_path)

        # Make executable (Linux/Unix)
        if script_type in ["bash", "python", "perl", "ruby"]:
            await self.execute_command(vm_id, f"chmod +x {remote_path}")

        # Build execution command
        cmd = f"{interpreter} {remote_path}"
        if args:
            cmd += " " + " ".join(args)

        # Execute script
        result = await self.execute_command(vm_id, cmd)

        # Cleanup script file
        if script_type == "powershell":
            await self.execute_command(vm_id, f"Remove-Item -Path '{remote_path}' -Force")
        else:
            await self.execute_command(vm_id, f"rm -f {remote_path}")

        return result

    async def upload_file(
        self,
        vm_id: str,
        content: bytes,
        remote_path: str,
    ) -> bool:
        """
        Upload file to VM.

        Args:
            vm_id: Target VM ID
            content: File content as bytes
            remote_path: Destination path on VM

        Returns:
            True if successful
        """
        vm_info = self._active_vms.get(vm_id)
        if not vm_info:
            raise ValueError(f"VM not found: {vm_id}")

        conn = await self._get_connection(vm_id, vm_info)

        if vm_info.os_type == "windows":
            await self._upload_winrm(conn, content, remote_path)
        else:
            await self._upload_sftp(conn, content, remote_path)

        logger.debug(f"Uploaded file to {vm_id}:{remote_path}")
        return True

    async def download_file(
        self,
        vm_id: str,
        remote_path: str,
    ) -> bytes:
        """
        Download file from VM.

        Args:
            vm_id: Source VM ID
            remote_path: Path to file on VM

        Returns:
            File content as bytes
        """
        vm_info = self._active_vms.get(vm_id)
        if not vm_info:
            raise ValueError(f"VM not found: {vm_id}")

        conn = await self._get_connection(vm_id, vm_info)

        if vm_info.os_type == "windows":
            return await self._download_winrm(conn, remote_path)
        else:
            return await self._download_sftp(conn, remote_path)

    async def capture_screenshot(self, vm_id: str) -> Optional[bytes]:
        """
        Capture screenshot of VM display.

        Args:
            vm_id: VM to screenshot

        Returns:
            Screenshot as PNG bytes, or None if not supported
        """
        return await self._hypervisor.capture_screenshot(vm_id)

    async def snapshot_vm(self, vm_id: str, name: str) -> str:
        """
        Create snapshot of VM state.

        Args:
            vm_id: VM to snapshot
            name: Snapshot name

        Returns:
            Snapshot ID
        """
        snapshot_id = await self._hypervisor.create_snapshot(vm_id, name)

        if vm_id in self._active_vms:
            self._active_vms[vm_id].snapshots.append(snapshot_id)

        logger.info(f"Created snapshot {snapshot_id} for VM {vm_id}")
        return snapshot_id

    async def restore_snapshot(self, vm_id: str, snapshot_id: str) -> bool:
        """
        Restore VM to snapshot state.

        Args:
            vm_id: VM to restore
            snapshot_id: Snapshot to restore to

        Returns:
            True if successful
        """
        # Close existing connection (state will change)
        if vm_id in self._connections:
            await self._close_connection(vm_id)

        success = await self._hypervisor.restore_snapshot(vm_id, snapshot_id)

        # Wait for VM to be ready again
        if success:
            vm_info = self._active_vms.get(vm_id)
            if vm_info and vm_info.config:
                await self._wait_for_vm_ready(vm_id, vm_info.config)

        return success

    async def get_network_info(self, vm_id: str) -> Dict[str, Any]:
        """Get network configuration of VM."""
        vm_info = self._active_vms.get(vm_id)
        if not vm_info:
            raise ValueError(f"VM not found: {vm_id}")

        if vm_info.os_type == "windows":
            result = await self.execute_command(vm_id, "ipconfig /all")
        else:
            result = await self.execute_command(
                vm_id,
                "ip addr show; echo '---ROUTES---'; ip route; echo '---DNS---'; cat /etc/resolv.conf 2>/dev/null || true"
            )

        return {
            "vm_id": vm_id,
            "ip_address": vm_info.ip_address,
            "raw_output": result.stdout,
        }

    async def list_processes(self, vm_id: str) -> List[Dict[str, Any]]:
        """List running processes on VM."""
        vm_info = self._active_vms.get(vm_id)
        if not vm_info:
            raise ValueError(f"VM not found: {vm_id}")

        if vm_info.os_type == "windows":
            result = await self.execute_command(
                vm_id,
                "Get-Process | Select-Object Id, ProcessName, CPU, WorkingSet | ConvertTo-Json"
            )
        else:
            result = await self.execute_command(
                vm_id,
                "ps aux --sort=-%mem | head -50"
            )

        return self._parse_process_list(result.stdout, vm_info.os_type)

    async def stop_vm(self, vm_id: str) -> bool:
        """Stop a running VM."""
        if vm_id in self._connections:
            await self._close_connection(vm_id)

        success = await self._hypervisor.stop_vm(vm_id)

        if success and vm_id in self._active_vms:
            self._active_vms[vm_id].state = VMState.STOPPED

        return success

    async def start_vm(self, vm_id: str) -> bool:
        """Start a stopped VM."""
        success = await self._hypervisor.start_vm(vm_id)

        if success and vm_id in self._active_vms:
            self._active_vms[vm_id].state = VMState.RUNNING
            # Wait for it to be ready
            if self._active_vms[vm_id].config:
                await self._wait_for_vm_ready(vm_id, self._active_vms[vm_id].config)

        return success

    async def destroy_vm(self, vm_id: str) -> bool:
        """Destroy VM and clean up resources."""
        # Close connection
        if vm_id in self._connections:
            await self._close_connection(vm_id)

        # Destroy through hypervisor
        success = await self._hypervisor.destroy_vm(vm_id)

        # Remove from tracking
        self._active_vms.pop(vm_id, None)

        logger.info(f"Destroyed VM: {vm_id}")
        return success

    async def cleanup_all(self) -> None:
        """Destroy all active VMs and clean up."""
        vm_ids = list(self._active_vms.keys())
        for vm_id in vm_ids:
            try:
                await self.destroy_vm(vm_id)
            except Exception as e:
                logger.error(f"Failed to destroy VM {vm_id}: {e}")

        # Close any remaining connections
        for vm_id in list(self._connections.keys()):
            await self._close_connection(vm_id)

    # -------------------------------------------------------------------------
    # Private methods
    # -------------------------------------------------------------------------

    async def _wait_for_vm_ready(
        self,
        vm_id: str,
        config: VMConfig,
        timeout: int = 300
    ) -> Optional[str]:
        """Wait for VM to be accessible via SSH/WinRM."""
        start = time.time()

        while time.time() - start < timeout:
            try:
                # Get IP from hypervisor
                ip_address = await self._hypervisor.get_vm_ip(vm_id)
                if not ip_address:
                    await asyncio.sleep(5)
                    continue

                # Try to connect
                vm_info = VMInfo(
                    vm_id=vm_id,
                    name=config.name,
                    state=VMState.RUNNING,
                    os_type=config.os_type,
                    ip_address=ip_address,
                    config=config,
                )
                self._active_vms[vm_id] = vm_info

                await self._get_connection(vm_id, vm_info)
                return ip_address

            except Exception as e:
                logger.debug(f"VM {vm_id} not ready yet: {e}")
                await asyncio.sleep(5)

        raise TimeoutError(f"VM {vm_id} not ready after {timeout} seconds")

    async def _get_connection(self, vm_id: str, vm_info: VMInfo) -> Any:
        """Get or create connection to VM."""
        if vm_id in self._connections:
            return self._connections[vm_id]

        if not vm_info.ip_address:
            raise ValueError(f"No IP address for VM {vm_id}")

        config = vm_info.config
        if not config:
            raise ValueError(f"No config for VM {vm_id}")

        if vm_info.os_type == "windows":
            conn = await self._create_winrm_connection(vm_info)
        else:
            conn = await self._create_ssh_connection(vm_info)

        self._connections[vm_id] = conn
        return conn

    async def _create_ssh_connection(self, vm_info: VMInfo) -> Any:
        """Create SSH connection to Linux VM."""
        try:
            import asyncssh
        except ImportError:
            raise ImportError("asyncssh required for SSH connections: pip install asyncssh")

        config = vm_info.config

        connect_kwargs = {
            "host": vm_info.ip_address,
            "username": config.ssh_user,
            "known_hosts": None,  # Disable host key checking for lab environment
        }

        if config.ssh_key_path:
            connect_kwargs["client_keys"] = [config.ssh_key_path]
        elif config.ssh_password:
            connect_kwargs["password"] = config.ssh_password

        return await asyncssh.connect(**connect_kwargs)

    async def _create_winrm_connection(self, vm_info: VMInfo) -> Any:
        """Create WinRM connection to Windows VM."""
        try:
            import winrm
        except ImportError:
            raise ImportError("pywinrm required for Windows connections: pip install pywinrm")

        config = vm_info.config

        session = winrm.Session(
            vm_info.ip_address,
            auth=(config.ssh_user, config.ssh_password),
            transport="ntlm",
        )

        return session

    async def _execute_ssh(
        self,
        conn: Any,
        command: str,
        timeout: int,
        working_dir: Optional[str],
    ) -> Tuple[str, str, int]:
        """Execute command via SSH."""
        if working_dir:
            command = f"cd {working_dir} && {command}"

        result = await asyncio.wait_for(
            conn.run(command, check=False),
            timeout=timeout
        )

        return result.stdout, result.stderr, result.returncode

    async def _execute_winrm(
        self,
        conn: Any,
        command: str,
        timeout: int,
        working_dir: Optional[str],
    ) -> Tuple[str, str, int]:
        """Execute command via WinRM."""
        if working_dir:
            command = f"cd {working_dir}; {command}"

        # WinRM is synchronous, run in thread pool
        loop = asyncio.get_event_loop()
        result = await asyncio.wait_for(
            loop.run_in_executor(None, conn.run_ps, command),
            timeout=timeout
        )

        return (
            result.std_out.decode("utf-8", errors="ignore"),
            result.std_err.decode("utf-8", errors="ignore"),
            result.status_code,
        )

    async def _upload_sftp(self, conn: Any, content: bytes, remote_path: str) -> None:
        """Upload file via SFTP."""
        async with conn.start_sftp_client() as sftp:
            async with sftp.open(remote_path, "wb") as f:
                await f.write(content)

    async def _download_sftp(self, conn: Any, remote_path: str) -> bytes:
        """Download file via SFTP."""
        async with conn.start_sftp_client() as sftp:
            async with sftp.open(remote_path, "rb") as f:
                return await f.read()

    async def _upload_winrm(self, conn: Any, content: bytes, remote_path: str) -> None:
        """Upload file via WinRM (base64 encoded)."""
        import base64
        encoded = base64.b64encode(content).decode("ascii")

        # PowerShell command to decode and write file
        ps_cmd = f"""
        $bytes = [Convert]::FromBase64String('{encoded}')
        [IO.File]::WriteAllBytes('{remote_path}', $bytes)
        """

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, conn.run_ps, ps_cmd)

    async def _download_winrm(self, conn: Any, remote_path: str) -> bytes:
        """Download file via WinRM (base64 encoded)."""
        import base64

        ps_cmd = f"[Convert]::ToBase64String([IO.File]::ReadAllBytes('{remote_path}'))"

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, conn.run_ps, ps_cmd)

        encoded = result.std_out.decode("utf-8").strip()
        return base64.b64decode(encoded)

    async def _close_connection(self, vm_id: str) -> None:
        """Close connection to VM."""
        if vm_id in self._connections:
            conn = self._connections.pop(vm_id)
            if hasattr(conn, "close"):
                try:
                    conn.close()
                except Exception:
                    pass

    def _parse_process_list(self, output: str, os_type: str) -> List[Dict[str, Any]]:
        """Parse process list output."""
        processes = []

        if os_type == "windows":
            try:
                import json
                return json.loads(output)
            except Exception:
                return []
        else:
            # Parse ps aux output
            lines = output.strip().split("\n")[1:]  # Skip header
            for line in lines:
                parts = line.split(None, 10)
                if len(parts) >= 11:
                    processes.append({
                        "user": parts[0],
                        "pid": parts[1],
                        "cpu": parts[2],
                        "mem": parts[3],
                        "command": parts[10],
                    })

        return processes


# =============================================================================
# Hypervisor Implementations
# =============================================================================

class BaseHypervisor:
    """Base class for hypervisor implementations."""

    def __init__(self, config: InfrastructureConfig):
        self.config = config

    async def create_vm(self, vm_config: VMConfig) -> str:
        raise NotImplementedError

    async def start_vm(self, vm_id: str) -> bool:
        raise NotImplementedError

    async def stop_vm(self, vm_id: str) -> bool:
        raise NotImplementedError

    async def destroy_vm(self, vm_id: str) -> bool:
        raise NotImplementedError

    async def get_vm_ip(self, vm_id: str) -> Optional[str]:
        raise NotImplementedError

    async def create_snapshot(self, vm_id: str, name: str) -> str:
        raise NotImplementedError

    async def restore_snapshot(self, vm_id: str, snapshot_id: str) -> bool:
        raise NotImplementedError

    async def capture_screenshot(self, vm_id: str) -> Optional[bytes]:
        return None  # Not all hypervisors support this


class DockerHypervisor(BaseHypervisor):
    """Docker-based hypervisor (easiest to set up)."""

    def __init__(self, config: InfrastructureConfig):
        super().__init__(config)
        self._client = None

    def _get_client(self):
        """Get Docker client."""
        if self._client is None:
            try:
                import docker
                self._client = docker.from_env()
            except ImportError:
                raise ImportError("docker package required: pip install docker")
        return self._client

    async def create_vm(self, vm_config: VMConfig) -> str:
        """Create container as VM."""
        client = self._get_client()

        # Map template names to Docker images
        image_map = {
            "ubuntu-attacker": "ciicerone/ubuntu-attacker:latest",
            "ubuntu-target": "ubuntu:22.04",
            "windows-target": "mcr.microsoft.com/windows/servercore:ltsc2022",
        }

        image = image_map.get(vm_config.template, vm_config.template)

        # Create container
        loop = asyncio.get_event_loop()
        container = await loop.run_in_executor(
            None,
            lambda: client.containers.run(
                image,
                name=vm_config.name,
                detach=True,
                network=self.config.attack_network_name,
                mem_limit=f"{vm_config.memory_gb}g",
                cpu_count=vm_config.cpu_cores,
                environment={
                    "SSH_USER": vm_config.ssh_user,
                    "SSH_PASSWORD": vm_config.ssh_password or "ciicerone",
                },
                # Keep container running
                command="tail -f /dev/null" if vm_config.os_type != "windows" else None,
            )
        )

        return container.id

    async def start_vm(self, vm_id: str) -> bool:
        """Start container."""
        client = self._get_client()
        try:
            container = client.containers.get(vm_id)
            container.start()
            return True
        except Exception as e:
            logger.error(f"Failed to start container {vm_id}: {e}")
            return False

    async def stop_vm(self, vm_id: str) -> bool:
        """Stop container."""
        client = self._get_client()
        try:
            container = client.containers.get(vm_id)
            container.stop(timeout=10)
            return True
        except Exception as e:
            logger.error(f"Failed to stop container {vm_id}: {e}")
            return False

    async def destroy_vm(self, vm_id: str) -> bool:
        """Remove container."""
        client = self._get_client()
        try:
            container = client.containers.get(vm_id)
            container.remove(force=True)
            return True
        except Exception as e:
            logger.error(f"Failed to remove container {vm_id}: {e}")
            return False

    async def get_vm_ip(self, vm_id: str) -> Optional[str]:
        """Get container IP address."""
        client = self._get_client()
        try:
            container = client.containers.get(vm_id)
            container.reload()

            networks = container.attrs.get("NetworkSettings", {}).get("Networks", {})
            for network_name, network_info in networks.items():
                if network_info.get("IPAddress"):
                    return network_info["IPAddress"]

            return None
        except Exception as e:
            logger.error(f"Failed to get IP for container {vm_id}: {e}")
            return None

    async def create_snapshot(self, vm_id: str, name: str) -> str:
        """Create container commit as snapshot."""
        client = self._get_client()
        container = client.containers.get(vm_id)

        loop = asyncio.get_event_loop()
        image = await loop.run_in_executor(
            None,
            lambda: container.commit(repository="ciicerone-snapshot", tag=name)
        )

        return image.id

    async def restore_snapshot(self, vm_id: str, snapshot_id: str) -> bool:
        """Restore not directly supported in Docker, need to recreate."""
        # For Docker, we'd need to stop, remove, and create new container from snapshot
        # This is a simplified implementation
        logger.warning("Docker snapshot restore requires manual recreation")
        return False


class ProxmoxHypervisor(BaseHypervisor):
    """Proxmox VE hypervisor implementation."""

    async def create_vm(self, vm_config: VMConfig) -> str:
        """Clone VM from template in Proxmox."""
        # Implementation would use Proxmox API
        raise NotImplementedError("Proxmox integration coming soon")

    async def start_vm(self, vm_id: str) -> bool:
        raise NotImplementedError("Proxmox integration coming soon")

    async def stop_vm(self, vm_id: str) -> bool:
        raise NotImplementedError("Proxmox integration coming soon")

    async def destroy_vm(self, vm_id: str) -> bool:
        raise NotImplementedError("Proxmox integration coming soon")

    async def get_vm_ip(self, vm_id: str) -> Optional[str]:
        raise NotImplementedError("Proxmox integration coming soon")

    async def create_snapshot(self, vm_id: str, name: str) -> str:
        raise NotImplementedError("Proxmox integration coming soon")

    async def restore_snapshot(self, vm_id: str, snapshot_id: str) -> bool:
        raise NotImplementedError("Proxmox integration coming soon")


class LibvirtHypervisor(BaseHypervisor):
    """Libvirt/KVM hypervisor implementation."""

    async def create_vm(self, vm_config: VMConfig) -> str:
        raise NotImplementedError("Libvirt integration coming soon")

    async def start_vm(self, vm_id: str) -> bool:
        raise NotImplementedError("Libvirt integration coming soon")

    async def stop_vm(self, vm_id: str) -> bool:
        raise NotImplementedError("Libvirt integration coming soon")

    async def destroy_vm(self, vm_id: str) -> bool:
        raise NotImplementedError("Libvirt integration coming soon")

    async def get_vm_ip(self, vm_id: str) -> Optional[str]:
        raise NotImplementedError("Libvirt integration coming soon")

    async def create_snapshot(self, vm_id: str, name: str) -> str:
        raise NotImplementedError("Libvirt integration coming soon")

    async def restore_snapshot(self, vm_id: str, snapshot_id: str) -> bool:
        raise NotImplementedError("Libvirt integration coming soon")
