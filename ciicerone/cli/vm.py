"""CLI commands for VM-based attack simulation.

This module provides CLI commands for managing and executing
AI-controlled VM attack simulations.
"""

import asyncio
import json
import os
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()


@click.group("vm")
def vm_group():
    """VM-based attack simulation commands (experimental — not part of v1).

    Run AI-controlled attack simulations in isolated virtual machines.
    Requires Docker or a hypervisor (Proxmox, VMware, etc.) to be configured.
    """
    pass


@vm_group.command("setup")
@click.option(
    "--hypervisor", "-h",
    type=click.Choice(["docker", "azure", "proxmox", "libvirt", "vmware"]),
    default="docker",
    help="Hypervisor type to use"
)
@click.option("--force", "-f", is_flag=True, help="Force setup even if already configured")
@click.option("--location", "-l", default="eastus2", help="Azure region (azure only)")
@click.option("--vm-size", "-s", default="Standard_D4s_v3", help="Azure VM size (azure only)")
def setup_infrastructure(hypervisor: str, force: bool, location: str, vm_size: str):
    """Set up VM infrastructure for attack simulations.

    This will:
    1. Create isolated network for attacks
    2. Pull/create base VM templates
    3. Configure security settings

    For Azure: provisions a cloud VM with Docker, Phantom Kali tool-server,
    and a DVWA target. Requires Azure CLI (az) installed and logged in.
    """
    console.print(Panel(
        "[bold]VM Attack Simulation Setup[/bold]\n\n"
        f"Hypervisor: {hypervisor}",
        title="Ciicerone VM Setup"
    ))

    if hypervisor == "docker":
        _setup_docker_infrastructure(force)
    elif hypervisor == "azure":
        _setup_azure_infrastructure(force, location, vm_size)
    else:
        console.print(f"[yellow]Hypervisor '{hypervisor}' support coming soon.[/yellow]")
        console.print("Currently only Docker and Azure are fully implemented.")


def _setup_docker_infrastructure(force: bool):
    """Set up Docker-based infrastructure."""
    import subprocess

    console.print("\n[bold]Step 1: Checking Docker...[/bold]")

    # Check Docker is running
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            console.print("[red]Docker is not running. Please start Docker first.[/red]")
            return
        console.print("[green]✓ Docker is running[/green]")
    except FileNotFoundError:
        console.print("[red]Docker not found. Please install Docker first.[/red]")
        return

    console.print("\n[bold]Step 2: Creating attack network...[/bold]")

    # Create isolated network
    try:
        subprocess.run(
            ["docker", "network", "create", "--internal", "ciicerone-attack-net"],
            capture_output=True,
            check=False  # May already exist
        )
        console.print("[green]✓ Attack network created (isolated, no internet)[/green]")
    except Exception as e:
        console.print(f"[yellow]Network may already exist: {e}[/yellow]")

    console.print("\n[bold]Step 3: Building attacker VM image...[/bold]")

    # Check if we need to build the image
    result = subprocess.run(
        ["docker", "images", "-q", "ciicerone/ubuntu-attacker"],
        capture_output=True,
        text=True
    )

    if result.stdout.strip() and not force:
        console.print("[green]✓ Attacker image already exists[/green]")
    else:
        console.print("Building Ubuntu attacker image (this may take a few minutes)...")

        # Create Dockerfile for attacker
        dockerfile_content = """
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

# Update and install base tools
RUN apt-get update && apt-get install -y \\
    openssh-server \\
    python3 \\
    python3-pip \\
    python3-venv \\
    git \\
    curl \\
    wget \\
    nmap \\
    netcat-openbsd \\
    dnsutils \\
    whois \\
    net-tools \\
    iputils-ping \\
    traceroute \\
    tcpdump \\
    nikto \\
    hydra \\
    sqlmap \\
    && rm -rf /var/lib/apt/lists/*

# Install Python security tools
RUN pip3 install --break-system-packages \\
    impacket \\
    crackmapexec \\
    requests \\
    paramiko

# Configure SSH
RUN mkdir /var/run/sshd && \\
    echo 'root:${LAB_SSH_PASSWORD:-labpass}' | chpasswd && \\
    sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config

EXPOSE 22

CMD ["/usr/sbin/sshd", "-D"]
"""

        # Write Dockerfile
        dockerfile_path = Path("/tmp/ciicerone-attacker-dockerfile")
        dockerfile_path.write_text(dockerfile_content)

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Building image...", total=None)

            result = subprocess.run(
                ["docker", "build", "-t", "ciicerone/ubuntu-attacker", "-f", str(dockerfile_path), "/tmp"],
                capture_output=True,
                text=True
            )

            if result.returncode == 0:
                console.print("[green]✓ Attacker image built successfully[/green]")
            else:
                console.print(f"[red]Failed to build image: {result.stderr}[/red]")
                return

    console.print("\n[bold]Step 4: Creating target VM image...[/bold]")

    # Check if target image exists
    result = subprocess.run(
        ["docker", "images", "-q", "ciicerone/ubuntu-target"],
        capture_output=True,
        text=True
    )

    if result.stdout.strip() and not force:
        console.print("[green]✓ Target image already exists[/green]")
    else:
        # Create target Dockerfile
        target_dockerfile = """
FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \\
    openssh-server \\
    apache2 \\
    mysql-server \\
    python3 \\
    net-tools \\
    && rm -rf /var/lib/apt/lists/*

# Configure SSH
RUN mkdir /var/run/sshd && \\
    echo 'root:${LAB_TARGET_PASSWORD:-targetpass}' | chpasswd && \\
    sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config

# Add vulnerable user
RUN useradd -m -s /bin/bash admin && \\
    echo 'admin:${LAB_USER_PASSWORD:-userpass}' | chpasswd

EXPOSE 22 80 3306

CMD service apache2 start && /usr/sbin/sshd -D
"""

        dockerfile_path = Path("/tmp/ciicerone-target-dockerfile")
        dockerfile_path.write_text(target_dockerfile)

        result = subprocess.run(
            ["docker", "build", "-t", "ciicerone/ubuntu-target", "-f", str(dockerfile_path), "/tmp"],
            capture_output=True,
            text=True
        )

        if result.returncode == 0:
            console.print("[green]✓ Target image built successfully[/green]")
        else:
            console.print(f"[red]Failed to build target image: {result.stderr}[/red]")

    console.print("\n" + "="*50)
    console.print("[bold green]Setup complete![/bold green]")
    console.print("\nNext steps:")
    console.print("  1. Run: [cyan]ciicerone vm start-lab[/cyan]")
    console.print("  2. Run: [cyan]ciicerone vm attack --scenario phishing[/cyan]")


def _setup_azure_infrastructure(force: bool, location: str, vm_size: str):
    """Set up Azure-based infrastructure with Docker sandbox."""
    import subprocess
    import shutil as _shutil

    console.print("\n[bold]Step 1: Checking Azure CLI...[/bold]")

    if _shutil.which("az") is None:
        console.print("[red]Azure CLI (az) not found. Install: brew install azure-cli[/red]")
        return

    result = subprocess.run(["az", "account", "show"], capture_output=True, text=True)
    if result.returncode != 0:
        console.print("[red]Not logged in to Azure. Run: az login[/red]")
        return
    console.print("[green]✓ Azure CLI authenticated[/green]")

    console.print("\n[bold]Step 2: Locating provisioning script...[/bold]")

    script_path = Path(__file__).resolve().parents[1].parent / "scripts" / "azure_provision.sh"
    if not script_path.exists():
        console.print(f"[red]Provisioning script not found at {script_path}[/red]")
        return
    console.print(f"[green]✓ Script found: {script_path}[/green]")

    console.print("\n[bold]Step 3: Provisioning Azure resources...[/bold]")
    console.print(f"[dim]Location: {location} | VM Size: {vm_size}[/dim]")
    console.print("[yellow]This takes 5-10 minutes. Building Kali image inside VM...[/yellow]\n")

    env = os.environ.copy()
    env["CIICERONE_LOCATION"] = location
    env["CIICERONE_VM_SIZE"] = vm_size

    result = subprocess.run(
        ["bash", str(script_path)],
        env=env,
    )

    if result.returncode == 0:
        console.print("\n[bold green]✓ Azure sandbox provisioned successfully![/bold green]")
        console.print("\nNext steps:")
        console.print("  1. Set CIICERONE_TOOL_SERVER_URL in your .env")
        console.print("  2. Run: [cyan]ciicerone vm attack --scenario phishing[/cyan]")
        console.print("  3. Cleanup: [cyan]az group delete --name ciicerone-rg --yes --no-wait[/cyan]")
    else:
        console.print(f"\n[red]Provisioning failed with exit code {result.returncode}[/red]")
        console.print("Check the output above for details.")


@vm_group.command("start-lab")
@click.option("--targets", "-t", default=1, help="Number of target VMs to create")
def start_lab(targets: int):
    """Start the attack simulation lab environment.

    Creates attacker and target VMs in isolated network.
    """
    console.print(Panel(
        f"[bold]Starting Attack Lab[/bold]\n\n"
        f"Attacker VMs: 1\n"
        f"Target VMs: {targets}",
        title="Ciicerone Lab"
    ))

    import subprocess

    # Start attacker VM
    console.print("\n[bold]Starting attacker VM...[/bold]")

    result = subprocess.run(
        [
            "docker", "run", "-d",
            "--name", "ciicerone-attacker",
            "--network", "ciicerone-attack-net",
            "--hostname", "attacker",
            "ciicerone/ubuntu-attacker"
        ],
        capture_output=True,
        text=True
    )

    if result.returncode == 0:
        console.print("[green]✓ Attacker VM started[/green]")
    else:
        if "already in use" in result.stderr:
            console.print("[yellow]Attacker VM already running[/yellow]")
        else:
            console.print(f"[red]Failed: {result.stderr}[/red]")
            return

    # Start target VMs
    for i in range(targets):
        target_name = f"ciicerone-target-{i+1}"
        console.print(f"\n[bold]Starting {target_name}...[/bold]")

        result = subprocess.run(
            [
                "docker", "run", "-d",
                "--name", target_name,
                "--network", "ciicerone-attack-net",
                "--hostname", f"target{i+1}",
                "ciicerone/ubuntu-target"
            ],
            capture_output=True,
            text=True
        )

        if result.returncode == 0:
            console.print(f"[green]✓ {target_name} started[/green]")
        else:
            if "already in use" in result.stderr:
                console.print(f"[yellow]{target_name} already running[/yellow]")
            else:
                console.print(f"[red]Failed: {result.stderr}[/red]")

    # Get IP addresses
    console.print("\n[bold]Lab Status:[/bold]")

    table = Table(title="VM Information")
    table.add_column("Name", style="cyan")
    table.add_column("IP Address", style="green")
    table.add_column("Status", style="yellow")

    # Get attacker IP
    result = subprocess.run(
        ["docker", "inspect", "-f", "{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}", "ciicerone-attacker"],
        capture_output=True,
        text=True
    )
    attacker_ip = result.stdout.strip() or "Unknown"
    table.add_row("ciicerone-attacker", attacker_ip, "Running")

    # Get target IPs
    for i in range(targets):
        target_name = f"ciicerone-target-{i+1}"
        result = subprocess.run(
            ["docker", "inspect", "-f", "{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}", target_name],
            capture_output=True,
            text=True
        )
        target_ip = result.stdout.strip() or "Unknown"
        table.add_row(target_name, target_ip, "Running")

    console.print(table)

    console.print("\n[bold]To access attacker VM:[/bold]")
    console.print("  docker exec -it ciicerone-attacker bash")
    console.print("\n[bold]To run attack simulation:[/bold]")
    console.print("  ciicerone vm attack --scenario phishing")


@vm_group.command("stop-lab")
def stop_lab():
    """Stop and remove all lab VMs."""
    import subprocess

    console.print("[bold]Stopping lab environment...[/bold]")

    # Get all ciicerone containers
    result = subprocess.run(
        ["docker", "ps", "-a", "--filter", "name=ciicerone-", "--format", "{{.Names}}"],
        capture_output=True,
        text=True
    )

    containers = result.stdout.strip().split("\n")
    containers = [c for c in containers if c]

    if not containers:
        console.print("[yellow]No lab containers found.[/yellow]")
        return

    for container in containers:
        console.print(f"Stopping {container}...")
        subprocess.run(["docker", "rm", "-f", container], capture_output=True)

    console.print(f"[green]✓ Stopped {len(containers)} containers[/green]")


@vm_group.command("status")
def lab_status():
    """Show status of lab VMs."""
    import subprocess

    result = subprocess.run(
        ["docker", "ps", "-a", "--filter", "name=ciicerone-", "--format", "table {{.Names}}\t{{.Status}}\t{{.Ports}}"],
        capture_output=True,
        text=True
    )

    if result.stdout.strip():
        console.print("[bold]Lab Status:[/bold]\n")
        console.print(result.stdout)
    else:
        console.print("[yellow]No lab VMs found. Run 'ciicerone vm start-lab' first.[/yellow]")


@vm_group.command("attack")
@click.option(
    "--scenario", "-s",
    type=click.Path(exists=True),
    help="Path to scenario YAML file"
)
@click.option(
    "--scenario-type", "-t",
    type=click.Choice(["reconnaissance", "phishing", "lateral", "full"]),
    default="reconnaissance",
    help="Built-in scenario type"
)
@click.option(
    "--target", "-T",
    default="ciicerone-target-1",
    help="Target VM name or IP"
)
@click.option("--dry-run", is_flag=True, help="Plan attack without executing")
@click.option("--output", "-o", type=click.Path(), help="Save results to file")
def run_attack(
    scenario: Optional[str],
    scenario_type: str,
    target: str,
    dry_run: bool,
    output: Optional[str]
):
    """Run an AI-controlled attack simulation (experimental — not yet implemented).

    The AI will autonomously plan and execute attacks based on the scenario,
    adapting its strategy based on what it discovers.

    Note: the underlying VM operator backend is still a skeleton and raises
    NotImplementedError, so this command is not yet functional.
    """
    console.print(Panel(
        f"[bold]AI Attack Simulation[/bold]\n\n"
        f"Scenario: {scenario or scenario_type}\n"
        f"Target: {target}\n"
        f"Mode: {'Dry Run (planning only)' if dry_run else 'Live Execution'}",
        title="Ciicerone Attack"
    ))

    # Load scenario
    if scenario:
        import yaml
        with open(scenario) as f:
            scenario_data = yaml.safe_load(f)
    else:
        scenario_data = _get_builtin_scenario(scenario_type)

    # Get target info
    target_info = _get_target_info(target)

    if dry_run:
        # Just show the plan
        console.print("\n[bold]Attack Plan (Dry Run):[/bold]")
        asyncio.run(_plan_attack_async(scenario_data, target_info))
    else:
        # Execute the attack
        console.print("\n[bold]Executing Attack...[/bold]")
        result = asyncio.run(_execute_attack_async(scenario_data, target_info, target, output))

        if result and output:
            console.print(f"\n[green]Results saved to {output}[/green]")


def _get_builtin_scenario(scenario_type: str) -> dict:
    """Get a built-in scenario definition."""
    scenarios = {
        "reconnaissance": {
            "name": "Network Reconnaissance",
            "description": "Discover hosts, services, and vulnerabilities on target network",
            "threat_type": "network_intrusion",
            "objectives": [
                "Discover live hosts",
                "Identify open ports and services",
                "Find potential vulnerabilities"
            ],
            "techniques": ["T1595", "T1046", "T1592"],
        },
        "phishing": {
            "name": "Phishing Attack Simulation",
            "description": "Simulate spearphishing attack with payload delivery",
            "threat_type": "phishing",
            "objectives": [
                "Craft convincing phishing email",
                "Deliver payload to target",
                "Establish initial access"
            ],
            "techniques": ["T1566", "T1204", "T1059"],
        },
        "lateral": {
            "name": "Lateral Movement",
            "description": "Move from initial foothold to other systems",
            "threat_type": "network_intrusion",
            "objectives": [
                "Enumerate local credentials",
                "Discover adjacent systems",
                "Pivot to new hosts"
            ],
            "techniques": ["T1021", "T1087", "T1135"],
        },
        "full": {
            "name": "Full Attack Chain",
            "description": "Complete attack from reconnaissance to data exfiltration",
            "threat_type": "data_breach",
            "objectives": [
                "Reconnaissance",
                "Initial access",
                "Privilege escalation",
                "Data collection",
                "Simulated exfiltration"
            ],
            "techniques": ["T1595", "T1566", "T1068", "T1005", "T1048"],
        }
    }
    return scenarios.get(scenario_type, scenarios["reconnaissance"])


def _get_target_info(target: str) -> dict:
    """Get information about target VM."""
    import subprocess

    # Try to get IP from Docker
    result = subprocess.run(
        ["docker", "inspect", "-f", "{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}", target],
        capture_output=True,
        text=True
    )

    ip = result.stdout.strip()
    if not ip:
        # Assume target is already an IP
        ip = target

    return {
        "name": target,
        "ip_address": ip,
        "os_type": "linux",
        "network": "ciicerone-attack-net"
    }


async def _plan_attack_async(scenario: dict, target_info: dict):
    """Plan attack and display the plan."""
    from ciicerone.vm import AIAttackAgent, VMOperator
    from ciicerone.vm.models import InfrastructureConfig

    try:
        from ciicerone.llm.manager import LLMManager
        llm = LLMManager()
    except Exception as e:
        console.print(f"[yellow]Warning: Could not initialize LLM: {e}[/yellow]")
        console.print("Using mock planning...")
        _display_mock_plan(scenario)
        return

    config = InfrastructureConfig()
    vm_operator = VMOperator(config)
    agent = AIAttackAgent(llm, vm_operator)

    try:
        plan = await agent.plan_attack(scenario, target_info)

        # Display plan
        console.print(f"\n[bold]{plan.name}[/bold]")
        console.print(f"Description: {plan.description}")
        console.print(f"\nObjectives: {', '.join(plan.objectives)}")
        console.print(f"MITRE Techniques: {', '.join(plan.mitre_techniques)}")
        console.print(f"Estimated Duration: {plan.timeout_minutes} minutes")

        console.print("\n[bold]Attack Steps:[/bold]")
        for i, step in enumerate(plan.steps, 1):
            console.print(f"\n{i}. [{step.phase.value}] {step.technique_name}")
            console.print(f"   {step.description}")
            console.print(f"   Commands: {step.commands[:2]}...")  # Show first 2

    except Exception as e:
        console.print(f"[red]Planning failed: {e}[/red]")


async def _execute_attack_async(
    scenario: dict,
    target_info: dict,
    target: str,
    output: Optional[str]
) -> Optional[dict]:
    """Execute attack and return results."""
    from ciicerone.vm import AIAttackAgent, VMOperator
    from ciicerone.vm.models import InfrastructureConfig

    try:
        from ciicerone.llm.manager import LLMManager
        llm = LLMManager()
    except Exception as e:
        console.print(f"[red]Error: LLM required for attack execution: {e}[/red]")
        return None

    config = InfrastructureConfig()
    vm_operator = VMOperator(config)
    agent = AIAttackAgent(llm, vm_operator)

    try:
        # Plan
        console.print("Planning attack...")
        plan = await agent.plan_attack(scenario, target_info)

        console.print(f"Plan: {plan.name} ({len(plan.steps)} steps)")

        # Execute
        console.print("\nExecuting attack...")
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Running attack simulation...", total=None)

            result = await agent.execute_attack(
                plan,
                attacker_vm="ciicerone-attacker",
                target_vms=[target]
            )

        # Display results
        console.print("\n" + "="*50)
        console.print("[bold]Attack Results[/bold]")
        console.print(f"Success Rate: {result.success_rate*100:.0f}%")
        console.print(f"Duration: {result.duration_seconds:.1f} seconds")
        console.print(f"Hosts Compromised: {len(result.compromised_hosts)}")
        console.print(f"Credentials Captured: {result.credentials_captured}")
        console.print(f"Services Discovered: {result.services_discovered}")

        if result.executive_summary:
            console.print(f"\n[bold]Summary:[/bold]\n{result.executive_summary}")

        if result.recommendations:
            console.print("\n[bold]Recommendations:[/bold]")
            for rec in result.recommendations[:5]:
                console.print(f"  • {rec}")

        # Save results
        if output:
            result_dict = result.dict()
            with open(output, "w") as f:
                json.dump(result_dict, f, indent=2, default=str)

        return result.dict()

    except Exception as e:
        console.print(f"[red]Attack failed: {e}[/red]")
        return None


def _display_mock_plan(scenario: dict):
    """Display mock plan when LLM is not available."""
    console.print(f"\n[bold]{scenario.get('name', 'Attack Plan')}[/bold]")
    console.print(f"Description: {scenario.get('description', 'N/A')}")
    console.print(f"\nObjectives: {', '.join(scenario.get('objectives', []))}")

    console.print("\n[bold]Planned Steps (mock):[/bold]")
    mock_steps = [
        ("reconnaissance", "Network scanning with nmap"),
        ("initial_access", "Attempt SSH authentication"),
        ("discovery", "Enumerate users and services"),
        ("collection", "Gather system information"),
    ]

    for i, (phase, desc) in enumerate(mock_steps, 1):
        console.print(f"  {i}. [{phase}] {desc}")


# Export the group
__all__ = ["vm_group"]
