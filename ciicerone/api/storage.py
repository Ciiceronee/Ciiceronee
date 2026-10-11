"""PostgreSQL-backed persistence for API scenarios and simulations.

This module provides the SQLAlchemy async storage layer used by the FastAPI
application. It persists threat scenarios and simulation records so the API
survives restarts and the audit trail is queryable.

Graceful degradation is a hard requirement: when no PostgreSQL URL is
configured (or the database is unreachable at startup) the API keeps running
with storage disabled and falls back to the previous in-memory behavior, so
OSS users without Postgres are not broken.

The generic ``sa.Uuid`` / ``sa.JSON`` column types keep the table definitions
portable: unit tests can run the same code against SQLite via aiosqlite while
production uses PostgreSQL (where ``sa.Uuid`` compiles to native UUID and the
Alembic migration uses JSONB - see migrations/versions/003).
"""

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import Column, DateTime, ForeignKey, JSON, MetaData, String, Table, Uuid, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from ciicerone.config.loader import CiiceroneConfig
from ciicerone.core.models import SimulationResult, ThreatScenario

logger = logging.getLogger(__name__)

metadata = MetaData()

scenarios_table = Table(
    "scenarios",
    metadata,
    Column("scenario_id", Uuid(as_uuid=True), primary_key=True),
    Column("name", String(255), nullable=False),
    Column("spec", JSON, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)

simulations_table = Table(
    "simulations",
    metadata,
    Column("simulation_id", Uuid(as_uuid=True), primary_key=True),
    Column("scenario_id", Uuid(as_uuid=True), ForeignKey("scenarios.scenario_id"), nullable=False),
    Column("status", String(50), nullable=False),
    Column("started_at", DateTime(timezone=True), nullable=False),
    Column("finished_at", DateTime(timezone=True), nullable=True),
    Column("result", JSON, nullable=True),
)


def _scenario_to_spec(scenario: ThreatScenario) -> Dict[str, Any]:
    """Serialize a ThreatScenario into a JSON-safe spec dictionary."""
    threat_type = scenario.threat_type
    return {
        "name": scenario.name,
        "threat_type": threat_type.value if hasattr(threat_type, "value") else str(threat_type),
        "description": scenario.description,
        "severity": scenario.severity,
        "target_systems": list(scenario.target_systems),
        "attack_vectors": list(scenario.attack_vectors),
        "metadata": dict(scenario.metadata),
        "created_at": scenario.created_at.isoformat(),
    }


def _spec_to_scenario(spec: Dict[str, Any], scenario_id: UUID) -> ThreatScenario:
    """Rebuild a ThreatScenario from a stored spec dictionary."""
    created_at = datetime.fromisoformat(spec["created_at"]) if spec.get("created_at") else None
    return ThreatScenario(
        name=spec["name"],
        threat_type=spec["threat_type"],
        description=spec.get("description", ""),
        severity=spec.get("severity", "medium"),
        target_systems=list(spec.get("target_systems") or []),
        attack_vectors=list(spec.get("attack_vectors") or []),
        metadata=dict(spec.get("metadata") or {}),
        created_at=created_at or datetime.now(timezone.utc),
        scenario_id=str(scenario_id),
    )


class ScenarioStorage:
    """Async repository for scenarios and simulation records."""

    def __init__(self, engine: AsyncEngine, session_factory: async_sessionmaker) -> None:
        self._engine = engine
        self._session_factory = session_factory

    @classmethod
    async def create(
        cls,
        database_url: str,
        *,
        create_tables: bool = False,
        **engine_kwargs: Any,
    ) -> "ScenarioStorage":
        """Create a storage instance from a SQLAlchemy async database URL.

        Args:
            database_url: SQLAlchemy async URL (postgresql+asyncpg:// or sqlite+aiosqlite://).
            create_tables: When True, create tables via metadata.create_all.
                Production schema is managed by Alembic migrations instead.
            **engine_kwargs: Extra arguments forwarded to create_async_engine.
        """
        if database_url.startswith("postgresql"):
            # Pin search_path so unqualified table names resolve to the schema
            # Alembic manages (public), not the "$user" schema that PostgreSQL
            # prefers by default (the docker init script creates one named
            # after the DB user, e.g. ciicerone.simulations).
            connect_args = engine_kwargs.setdefault("connect_args", {})
            connect_args.setdefault("server_settings", {})["search_path"] = "public"
        engine = create_async_engine(database_url, **engine_kwargs)
        storage = cls(engine, async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False))
        if create_tables:
            async with engine.begin() as conn:
                await conn.run_sync(metadata.create_all)
        return storage

    async def close(self) -> None:
        """Dispose of the connection pool."""
        await self._engine.dispose()

    async def ping(self) -> bool:
        """Check connectivity with a cheap query."""
        try:
            async with self._engine.connect() as conn:
                await conn.exec_driver_sql("SELECT 1")
            return True
        except Exception as e:
            logger.warning(f"Database ping failed: {e}")
            return False

    # =========================================================================
    # Scenarios
    # =========================================================================

    async def create_scenario(self, scenario: ThreatScenario) -> None:
        """Persist a threat scenario."""
        async with self._session_factory() as session:
            async with session.begin():
                await session.execute(
                    scenarios_table.insert().values(
                        scenario_id=UUID(scenario.scenario_id),
                        name=scenario.name,
                        spec=_scenario_to_spec(scenario),
                        created_at=datetime.now(timezone.utc),
                    )
                )

    async def get_scenario(self, scenario_id: str) -> Optional[ThreatScenario]:
        """Load a threat scenario by ID, or None when unknown."""
        try:
            scenario_uuid = UUID(str(scenario_id))
        except ValueError:
            return None
        async with self._session_factory() as session:
            row = await session.execute(
                select(scenarios_table.c.scenario_id, scenarios_table.c.spec).where(
                    scenarios_table.c.scenario_id == scenario_uuid
                )
            )
            record = row.first()
            if record is None:
                return None
            return _spec_to_scenario(record.spec, record.scenario_id)

    # =========================================================================
    # Simulations
    # =========================================================================

    async def create_simulation(self, result: SimulationResult) -> None:
        """Persist a simulation record from a SimulationResult."""
        async with self._session_factory() as session:
            async with session.begin():
                await session.execute(
                    simulations_table.insert().values(
                        simulation_id=UUID(result.result_id),
                        scenario_id=UUID(str(result.scenario_id)),
                        status=result.status.value if hasattr(result.status, "value") else str(result.status),
                        started_at=result.start_time,
                        finished_at=result.end_time,
                        result=_result_to_record(result),
                    )
                )

    async def get_simulation(self, simulation_id: str) -> Optional[Dict[str, Any]]:
        """Load a simulation record by ID, or None when unknown."""
        try:
            sim_uuid = UUID(str(simulation_id))
        except ValueError:
            return None
        async with self._session_factory() as session:
            row = await session.execute(
                simulations_table.select().where(simulations_table.c.simulation_id == sim_uuid)
            )
            record = row.mappings().first()
            if record is None:
                return None
            return _record_to_response(record)

    async def list_simulations(self, limit: int = 100) -> List[Dict[str, Any]]:
        """List simulation records, most recent first."""
        async with self._session_factory() as session:
            rows = await session.execute(
                simulations_table.select()
                .order_by(simulations_table.c.started_at.desc())
                .limit(limit)
            )
            return [_record_to_response(record) for record in rows.mappings().all()]


def _result_to_record(result: SimulationResult) -> Dict[str, Any]:
    """Serialize a SimulationResult into a JSON-safe record dictionary."""
    return {
        "result_id": result.result_id,
        "scenario_id": str(result.scenario_id),
        "status": result.status.value if hasattr(result.status, "value") else str(result.status),
        "stages_completed": len(result.stages),
        "successful_stages": sum(1 for stage in result.stages if stage.success),
        "success_rate": result.success_rate,
        "total_duration_seconds": result.total_duration_seconds,
        "error_message": result.error_message,
        "start_time": result.start_time.isoformat(),
        "end_time": result.end_time.isoformat() if result.end_time else None,
        "metadata": dict(result.metadata),
    }


def _record_to_response(record: Dict[str, Any]) -> Dict[str, Any]:
    """Convert a simulations table row into an API response dictionary."""
    return {
        "simulation_id": str(record["simulation_id"]),
        "scenario_id": str(record["scenario_id"]),
        "status": record["status"],
        "started_at": record["started_at"].isoformat() if record["started_at"] else None,
        "finished_at": record["finished_at"].isoformat() if record["finished_at"] else None,
        "result": record["result"],
    }


def resolve_database_url(config: CiiceroneConfig) -> Optional[str]:
    """Resolve the PostgreSQL URL from config or DATABASE_URL.

    Returns None when no URL is configured. Non-PostgreSQL URLs (e.g. the
    placeholder sqlite URL in the default config.yaml) are not usable by the
    async storage layer and yield None with a warning.
    """
    url = getattr(config, "database", None) and config.database.url
    env_url = os.getenv("DATABASE_URL")
    if url and not url.startswith("postgres"):
        # Config still holds the default placeholder (e.g. sqlite) - an
        # explicitly set DATABASE_URL env var is the real intent.
        url = env_url or None
    else:
        url = url or env_url
    if not url:
        return None
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        return "postgresql+asyncpg://" + url[len("postgresql://"):]
    if url.startswith("postgresql+"):
        return url
    logger.warning(
        f"Configured database URL '{url}' is not PostgreSQL; "
        "API storage requires PostgreSQL and will be disabled."
    )
    return None


async def init_storage(config: CiiceroneConfig) -> Optional[ScenarioStorage]:
    """Initialize storage with graceful degradation.

    When no PostgreSQL URL is configured or the database is unreachable at
    startup, logs a clear warning and returns None so the API keeps running
    with storage disabled instead of crashing.
    """
    url = resolve_database_url(config)
    if url is None:
        logger.info(
            "No DATABASE_URL configured - API storage disabled; "
            "scenarios and simulations will not be persisted."
        )
        return None

    try:
        storage = await ScenarioStorage.create(url)
        if not await storage.ping():
            raise ConnectionError("database ping failed")
        logger.info("API storage initialized (PostgreSQL)")
        return storage
    except Exception as e:
        logger.warning(
            f"Failed to connect to PostgreSQL ({e}); "
            "API storage disabled - running with in-memory behavior only."
        )
        try:
            await storage.close()  # type: ignore[possibly-undefined]
        except Exception:
            pass
        return None
