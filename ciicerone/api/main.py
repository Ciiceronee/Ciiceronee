"""FastAPI application for Ciicerone API.

This module provides the main FastAPI application with core endpoints
for threat simulation, scenario management, and system health checks.
"""

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional
from contextlib import asynccontextmanager
from uuid import UUID, uuid4

from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from ciicerone.core.models import ThreatScenario, SimulationResult, ThreatType
from ciicerone.core.simulator import Simulator
from ciicerone.core.event_sourcing import AggregateType, Event, EventStore
from ciicerone.core.postgres_event_store import PostgresEventStore
from ciicerone.llm.manager import LLMManager
from ciicerone.config.loader import CiiceroneConfig, load_config
from ciicerone.safety.content_filter import ContentFilter, get_global_filter
from ciicerone.safety.exceptions import ContentFilterError
from ciicerone.api.storage import ScenarioStorage, init_storage, resolve_database_url

# Import API routers
from ciicerone.api.routers import manuals_router, knowledge_router, feedback_router
from ciicerone.api.auth import APIKeyAuthMiddleware

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global instances
simulator: Optional[Simulator] = None
llm_manager: Optional[LLMManager] = None
storage: Optional[ScenarioStorage] = None
event_store: Optional[EventStore] = None

# Default configuration location (repository root config.yaml)
DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config.yaml"


def load_api_config() -> CiiceroneConfig:
    """Load the Ciicerone configuration for the API.

    Uses the repository ``config.yaml`` when present, otherwise falls back to
    ``config.yaml`` in the current working directory, and finally to defaults.
    """
    try:
        if DEFAULT_CONFIG_PATH.exists():
            return load_config(DEFAULT_CONFIG_PATH)
        return load_config()
    except Exception as e:
        logger.warning(f"Failed to load API configuration ({e}); using defaults")
        return CiiceroneConfig()


# Pydantic models for API
class ScenarioRequest(BaseModel):
    """Request model for creating threat scenarios."""
    name: str = Field(..., description="Name of the threat scenario")
    threat_type: ThreatType = Field(..., description="Type of threat")
    description: str = Field("", description="Detailed description of the scenario")
    severity: str = Field("medium", description="Severity level (low, medium, high, critical)")
    target_systems: List[str] = Field(default_factory=list, description="Target systems")
    attack_vectors: List[str] = Field(default_factory=list, description="Attack vectors")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class ScenarioResponse(BaseModel):
    """Response model for threat scenarios."""
    scenario_id: str
    name: str
    threat_type: ThreatType
    description: str
    severity: str
    target_systems: List[str]
    attack_vectors: List[str]
    created_at: datetime
    metadata: Dict[str, Any]


class SimulationRequest(BaseModel):
    """Request model for simulation execution."""
    scenario_id: str = Field(..., description="ID of the scenario to simulate")
    max_stages: Optional[int] = Field(10, description="Maximum number of simulation stages")


class HealthResponse(BaseModel):
    """Response model for health checks."""
    status: str
    timestamp: datetime
    version: str
    components: Dict[str, str]


class ContentGenerationRequest(BaseModel):
    """Request model for direct content generation."""
    prompt: str = Field(..., description="The prompt for content generation")
    scenario_type: str = Field("custom", description="Type of scenario")
    max_tokens: int = Field(1000, description="Maximum tokens to generate")
    temperature: float = Field(0.7, description="Generation temperature")
    provider: Optional[str] = Field(None, description="Specific LLM provider to use")


class ContentGenerationResponse(BaseModel):
    """Response model for content generation."""
    content: str
    provider_used: str
    tokens_used: int
    generation_time_seconds: float
    safety_score: float
    metadata: Dict[str, Any]


# Dependencies
def get_simulator() -> Simulator:
    """Get the threat simulator instance."""
    if simulator is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Threat simulator not initialized"
        )
    return simulator


def get_llm_manager() -> LLMManager:
    """Get the LLM manager instance."""
    if llm_manager is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LLM manager not initialized"
        )
    return llm_manager


async def _append_audit_event(
    event_type: str,
    aggregate_id: UUID,
    version: int,
    event_data: Dict[str, Any],
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """Append a simulation lifecycle event to the audit trail.

    Audit failures are logged but never fail the request being audited -
    the event store is an observer, not a gate.
    """
    if event_store is None:
        return
    try:
        await event_store.append(
            Event(
                event_id=uuid4(),
                aggregate_id=aggregate_id,
                aggregate_type=AggregateType.SIMULATION,
                event_type=event_type,
                event_data=event_data,
                metadata=metadata or {},
                sequence_number=0,  # assigned by the database on insert
                timestamp=datetime.now(timezone.utc),
                version=version,
            )
        )
        logger.info(f"Audit event appended: {event_type} (aggregate {aggregate_id}, v{version})")
    except Exception as e:
        logger.error(f"Failed to append audit event {event_type}: {e}")


def get_content_filter() -> ContentFilter:
    """Get the shared content safety filter instance."""
    return get_global_filter()


def get_storage() -> Optional[ScenarioStorage]:
    """Get the scenario/simulation storage instance (None when disabled)."""
    return storage


def _block_detail(prefix: str, filter_result) -> str:
    """Build a human-readable block reason from a FilterResult."""
    categories = (
        ", ".join(c.value for c in filter_result.categories_detected)
        or filter_result.risk_level.name
    )
    recommendations = " ".join(filter_result.recommendations)
    detail = f"{prefix} ({categories})"
    return f"{detail}. {recommendations}" if recommendations else detail


def create_app(config: Optional[CiiceroneConfig] = None) -> FastAPI:
    """Create the Ciicerone FastAPI application.

    Args:
        config: Optional pre-loaded configuration. When omitted, the
            repository ``config.yaml`` (or one in the current working
            directory) is loaded.

    Raises:
        RuntimeError: If authentication is enabled but no API key is
            configured, so misconfigured deployments fail fast at startup.
    """
    config = config or load_api_config()

    auth_config = config.api.authentication
    if auth_config.enabled:
        if not auth_config.api_key:
            raise RuntimeError(
                "API authentication is enabled (api.authentication.enabled=true) "
                "but no API key is configured. Set api.authentication.api_key in "
                "config.yaml or export CIICERONE_API_KEY / API_KEY."
            )
    else:
        logger.warning(
            "SECURITY WARNING: API authentication is DISABLED - all API "
            "endpoints are publicly accessible. Set "
            "api.authentication.enabled: true and configure an API key "
            "before exposing this service beyond localhost."
        )

    cors_config = config.api.cors

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """Application lifespan manager."""
        global simulator, llm_manager, storage, event_store

        # Startup
        logger.info("Starting Ciicerone API...")
        try:
            llm_manager = LLMManager(config=config.llm)
            simulator = Simulator(llm_provider=llm_manager)
        except Exception as e:
            logger.error(f"Failed to initialize Ciicerone API: {str(e)}")
            raise

        # Persistence layer (graceful degradation: no DATABASE_URL or an
        # unreachable database means storage/event store stay disabled)
        storage = await init_storage(config)
        database_url = resolve_database_url(config)
        if storage is not None and database_url is not None:
            try:
                # PostgresEventStore takes a plain asyncpg DSN, not a
                # SQLAlchemy URL - strip any +driver suffix.
                pg_dsn = database_url.replace("postgresql+asyncpg://", "postgresql://", 1)
                pg_store = await PostgresEventStore.create(pg_dsn)
                event_store = EventStore(postgres_store=pg_store)
                logger.info("Event sourcing audit trail enabled (PostgreSQL)")
            except Exception as e:
                logger.warning(
                    f"Failed to initialize PostgreSQL event store ({e}); "
                    "event sourcing audit trail disabled."
                )
                event_store = None
        else:
            event_store = None
            logger.info("Event sourcing audit trail disabled (no PostgreSQL)")

        logger.info("Ciicerone API started successfully")

        yield

        # Shutdown
        logger.info("Shutting down Ciicerone API...")
        if event_store is not None and event_store.postgres_store is not None:
            await event_store.postgres_store.close()
            event_store = None
        if storage is not None:
            await storage.close()
            storage = None

    # Create FastAPI app
    app = FastAPI(
        title="Ciicerone API",
        version="0.1.0",
        description="Advanced AI-powered threat simulation and analysis platform",
        lifespan=lifespan
    )

    # Authentication middleware (CORS is added last so it runs outermost and
    # handles preflight requests before auth can reject them)
    app.add_middleware(
        APIKeyAuthMiddleware,
        enabled=auth_config.enabled,
        api_key=auth_config.api_key,
        exempt_paths=auth_config.exempt_paths,
        header_name=auth_config.header,
    )

    # CORS middleware - origins/methods restricted to configuration; no wildcards
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_config.origins,
        allow_methods=cors_config.methods,
        allow_headers=cors_config.headers,
        # Never send credentials for wildcard or default origins
        allow_credentials=cors_config.allow_credentials
        and "*" not in cors_config.origins,
    )

    # Include API routers
    app.include_router(manuals_router, prefix="/api")
    app.include_router(knowledge_router, prefix="/api")
    app.include_router(feedback_router, prefix="/api")
    # TODO: Implement threat_hunting router and re-enable
    # app.include_router(threat_hunting_router, prefix="/api")

    # Health check endpoints
    @app.get("/", response_model=Dict[str, str])
    async def read_root():
        """Root endpoint."""
        return {
            "message": "Ciicerone API",
            "version": "0.1.0",
            "status": "operational"
        }

    @app.get("/health", response_model=HealthResponse)
    async def health_check():
        """Health check endpoint."""
        try:
            # Check component health
            components = {
                "api": "healthy",
                "simulator": "healthy" if simulator else "unavailable",
                "llm_manager": "healthy" if llm_manager else "unavailable",
                "storage": "healthy" if storage else "disabled",
                "event_store": "healthy" if event_store else "disabled"
            }

            # Overall status
            overall_status = "healthy" if all(
                status == "healthy" for status in components.values()
            ) else "degraded"

            return HealthResponse(
                status=overall_status,
                timestamp=datetime.utcnow(),
                version="0.1.0",
                components=components
            )

        except Exception as e:
            logger.error(f"Health check failed: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Health check failed"
            )

    # Scenario management endpoints
    @app.post("/scenarios", response_model=ScenarioResponse, status_code=status.HTTP_201_CREATED)
    async def create_scenario(request: ScenarioRequest):
        """Create a new threat scenario."""
        try:
            scenario = ThreatScenario(
                name=request.name,
                threat_type=request.threat_type,
                description=request.description,
                severity=request.severity,
                target_systems=request.target_systems,
                attack_vectors=request.attack_vectors,
                metadata=request.metadata
            )

            store = get_storage()
            if store is not None:
                await store.create_scenario(scenario)

            return ScenarioResponse(
                scenario_id=scenario.scenario_id,
                name=scenario.name,
                threat_type=scenario.threat_type,
                description=scenario.description,
                severity=scenario.severity,
                target_systems=scenario.target_systems,
                attack_vectors=scenario.attack_vectors,
                created_at=scenario.created_at,
                metadata=scenario.metadata
            )

        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to create scenario: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create scenario"
            )

    # Simulation endpoints
    @app.post("/simulations", status_code=status.HTTP_202_ACCEPTED)
    async def run_simulation(
        request: SimulationRequest,
        sim: Simulator = Depends(get_simulator)
    ):
        """Execute a threat simulation."""
        try:
            store = get_storage()
            if store is not None:
                # Load the scenario persisted via POST /scenarios
                scenario = await store.get_scenario(request.scenario_id)
                if scenario is None:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Scenario {request.scenario_id} not found"
                    )
            else:
                # Storage disabled - fall back to the previous in-memory behavior
                logger.info(
                    "Storage disabled - fabricating in-memory scenario for "
                    f"simulation request {request.scenario_id}"
                )
                scenario = ThreatScenario(
                    name=f"Scenario_{request.scenario_id}",
                    threat_type=ThreatType.CUSTOM,
                    description="API-initiated simulation scenario"
                )

            # Audit trail: one aggregate per simulation run. The run id is
            # returned as audit_trail_id so clients can fetch the trail.
            run_id = uuid4()
            await _append_audit_event(
                "SimulationStarted",
                run_id,
                1,
                {
                    "scenario_id": request.scenario_id,
                    "scenario_name": scenario.name,
                    "threat_type": getattr(
                        scenario.threat_type, "value", str(scenario.threat_type)
                    ),
                    "storage_backed": store is not None,
                },
            )

            try:
                # Execute simulation
                result = await sim.execute_simulation(scenario)
            except Exception as e:
                await _append_audit_event(
                    "SimulationFailed", run_id, 2, {"error": str(e)}
                )
                raise

            await _append_audit_event(
                "SimulationCompleted",
                run_id,
                2,
                {
                    "result_id": result.result_id,
                    "scenario_id": result.scenario_id,
                    "status": getattr(result.status, "value", str(result.status)),
                    "stages_completed": len(result.stages),
                    "success_rate": result.success_rate,
                    "duration_seconds": result.total_duration_seconds,
                },
            )

            if store is not None:
                try:
                    await store.create_simulation(result)
                except Exception as e:
                    # Persistence failure must not fail the executed simulation
                    logger.error(f"Failed to persist simulation record: {e}")

            return {
                "message": "Simulation executed successfully",
                "result_id": result.result_id,
                "audit_trail_id": str(run_id),
                "status": result.status,
                "stages_completed": len(result.stages),
                "success_rate": result.success_rate,
                "duration_seconds": result.total_duration_seconds
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Simulation failed: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Simulation failed: {str(e)}"
            )

    @app.get("/simulations")
    async def list_simulations(store: Optional[ScenarioStorage] = Depends(get_storage)):
        """List persisted simulation records, most recent first."""
        if store is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Simulation storage is disabled (no DATABASE_URL configured)"
            )
        try:
            return {"simulations": await store.list_simulations()}
        except Exception as e:
            logger.error(f"Failed to list simulations: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to list simulations"
            )

    @app.get("/simulations/{simulation_id}")
    async def get_simulation(
        simulation_id: str,
        store: Optional[ScenarioStorage] = Depends(get_storage)
    ):
        """Get a persisted simulation record by ID."""
        if store is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Simulation storage is disabled (no DATABASE_URL configured)"
            )
        try:
            record = await store.get_simulation(simulation_id)
            if record is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Simulation {simulation_id} not found"
                )
            return record
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to get simulation {simulation_id}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to get simulation"
            )

    @app.get("/audit/events/{aggregate_id}")
    async def get_audit_trail(aggregate_id: str):
        """Get the append-only event audit trail for a simulation run.

        The aggregate id is the `audit_trail_id` returned by POST /simulations.
        """
        if event_store is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Event store is disabled (no PostgreSQL configured)"
            )
        try:
            aggregate_uuid = UUID(aggregate_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="aggregate_id must be a UUID"
            )
        try:
            events = await event_store.get_events(aggregate_uuid)
            return {
                "aggregate_id": str(aggregate_uuid),
                "event_count": len(events),
                "events": [event.to_dict() for event in events],
            }
        except Exception as e:
            logger.error(f"Failed to read audit trail {aggregate_id}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to read audit trail"
            )

    @app.get("/simulations/active")
    async def get_active_simulations(sim: Simulator = Depends(get_simulator)):
        """Get currently active simulations."""
        try:
            active = sim.get_active_simulations()
            return {
                "active_simulations": len(active),
                "simulations": [
                    {
                        "result_id": result_id,
                        "status": result.status,
                        "scenario_id": result.scenario_id,
                        "stages_completed": len(result.stages),
                        "start_time": result.start_time.isoformat()
                    }
                    for result_id, result in active.items()
                ]
            }
        except Exception as e:
            logger.error(f"Failed to get active simulations: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to get active simulations"
            )

    # LLM endpoints
    @app.post("/llm/generate", response_model=ContentGenerationResponse)
    async def generate_content(
        request: ContentGenerationRequest,
        llm: LLMManager = Depends(get_llm_manager),
        content_filter: ContentFilter = Depends(get_content_filter),
    ):
        """Generate content directly using LLM providers."""
        filter_context = {
            "endpoint": "/llm/generate",
            "scenario_type": request.scenario_type,
        }

        # Safety layer: screen the incoming prompt before it reaches any LLM
        try:
            prompt_result = content_filter.filter(
                request.prompt, context={**filter_context, "stage": "input"}
            )
        except ContentFilterError as e:
            logger.error(f"Safety filter error on prompt: {e}")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Safety filter temporarily unavailable: {str(e)}"
            )

        if not prompt_result.is_safe:
            logger.warning(f"Prompt blocked by safety filter: {prompt_result.risk_level.name}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=_block_detail("Prompt blocked by safety filter", prompt_result)
            )

        try:
            start_time = datetime.utcnow()

            # Generate content using the LLM manager
            response = await llm.generate_content(
                prompt=request.prompt,
                scenario_type=request.scenario_type,
                max_tokens=request.max_tokens,
                temperature=request.temperature,
                provider_name=request.provider
            )

            end_time = datetime.utcnow()
            generation_time = (end_time - start_time).total_seconds()

            # Safety layer: screen generated output before returning it
            output_result = content_filter.filter(
                response.content, context={**filter_context, "stage": "output"}
            )

            if not output_result.is_safe:
                logger.warning(
                    f"Generated content blocked by safety filter: {output_result.risk_level.name}"
                )
                # 422 Unprocessable Entity (literal: the HTTP_422_UNPROCESSABLE_ENTITY
                # alias is deprecated in newer starlette versions)
                raise HTTPException(
                    status_code=422,
                    detail=_block_detail("Generated content blocked by safety filter", output_result)
                )

            usage = getattr(response, 'usage', None)
            if isinstance(usage, dict):
                tokens_used = usage.get('input_tokens', 0) + usage.get('output_tokens', 0)
            else:
                tokens_used = usage.total_tokens if usage else 0

            return ContentGenerationResponse(
                content=response.content,
                provider_used=response.provider,
                tokens_used=tokens_used,
                generation_time_seconds=generation_time,
                safety_score=response.safety_score if hasattr(response, 'safety_score') else 1.0,
                metadata=response.metadata if hasattr(response, 'metadata') else {}
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Content generation failed: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Content generation failed: {str(e)}"
            )

    @app.get("/llm/providers")
    async def list_providers(llm: LLMManager = Depends(get_llm_manager)):
        """List available LLM providers."""
        try:
            providers = llm.get_available_providers()
            return {
                "providers": providers,
                "default_provider": llm.get_default_provider(),
                "total_providers": len(providers)
            }
        except Exception as e:
            logger.error(f"Failed to list providers: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to list providers"
            )

    @app.get("/llm/status")
    async def llm_status(llm: LLMManager = Depends(get_llm_manager)):
        """Get LLM provider status."""
        try:
            return {
                "llm_manager": "operational",
                "available_providers": ["openai", "anthropic"],
                "status": "ready"
            }
        except Exception as e:
            logger.error(f"Failed to get LLM status: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to get LLM status"
            )

    # Error handlers
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request, exc):
        """Custom HTTP exception handler."""
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.detail,
                "status_code": exc.status_code,
                "timestamp": datetime.utcnow().isoformat()
            }
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request, exc):
        """General exception handler."""
        logger.error(f"Unhandled exception: {str(exc)}")
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal server error",
                "status_code": 500,
                "timestamp": datetime.utcnow().isoformat()
            }
        )

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
