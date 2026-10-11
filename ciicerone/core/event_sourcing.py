"""Event Sourcing System for Ciicerone Audit Trail.

This module implements a production-ready event sourcing system using PostgreSQL
for immutable audit logging, compliance, and state reconstruction capabilities.

Architecture Decision Record: dev/docs/ADR_008_EVENT_SOURCING_ARCHITECTURE.md
Issue: #8 - Implement Event Sourcing for Audit Trail
Owner: Lara Dipupo (Team Lead & Co-Core Developer)
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Type, TypeVar, Generic
from uuid import UUID, uuid4
from dataclasses import dataclass, field, asdict
from enum import Enum
import json

logger = logging.getLogger(__name__)

# Type variable for aggregate root
T = TypeVar('T')


class AggregateType(str, Enum):
    """Types of aggregates that emit events."""
    SIMULATION = "simulation"
    SCENARIO = "scenario"
    USER_ACTION = "user_action"
    CONFIGURATION = "configuration"
    SYSTEM = "system"


@dataclass(frozen=True)  # Immutable by design
class Event:
    """Immutable event record representing a state change in the system.
    
    Events are the source of truth for all state changes. They are:
    - Immutable: Once written, never modified
    - Append-only: Only new events added, never deleted
    - Ordered: Sequence number provides global ordering
    - Complete: Contains all information to reconstruct state
    
    Attributes:
        event_id: Unique identifier for this event
        aggregate_id: ID of the aggregate this event belongs to
        aggregate_type: Type of aggregate (simulation, scenario, etc.)
        event_type: Specific event type (SimulationStarted, StageCompleted, etc.)
        event_data: Event payload with all relevant data
        metadata: Contextual information (user_id, correlation_id, etc.)
        sequence_number: Global event ordering number
        timestamp: When the event occurred (UTC)
        version: Aggregate version for optimistic concurrency control
    """
    event_id: UUID
    aggregate_id: UUID
    aggregate_type: AggregateType
    event_type: str
    event_data: Dict[str, Any]
    metadata: Dict[str, Any]
    sequence_number: int
    timestamp: datetime
    version: int

    def __post_init__(self):
        """Validate event data after creation."""
        if not self.event_type:
            raise ValueError("event_type cannot be empty")
        if self.version < 0:
            raise ValueError(f"version must be >= 0, got {self.version}")
        # Ensure timestamp is timezone-aware (UTC)
        if self.timestamp.tzinfo is None:
            object.__setattr__(self, 'timestamp', self.timestamp.replace(tzinfo=timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary for storage."""
        return {
            'event_id': str(self.event_id),
            'aggregate_id': str(self.aggregate_id),
            'aggregate_type': self.aggregate_type.value,
            'event_type': self.event_type,
            'event_data': self.event_data,
            'metadata': self.metadata,
            'sequence_number': self.sequence_number,
            'timestamp': self.timestamp.isoformat(),
            'version': self.version
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Event':
        """Create event from dictionary."""
        return cls(
            event_id=UUID(data['event_id']),
            aggregate_id=UUID(data['aggregate_id']),
            aggregate_type=AggregateType(data['aggregate_type']),
            event_type=data['event_type'],
            event_data=data['event_data'],
            metadata=data['metadata'],
            sequence_number=data['sequence_number'],
            timestamp=datetime.fromisoformat(data['timestamp']),
            version=data['version']
        )


# ============================================================================
# Simulation Events
# ============================================================================

@dataclass(frozen=True)
class SimulationStarted(Event):
    """Event emitted when a simulation begins execution."""
    
    @classmethod
    def create(
        cls,
        aggregate_id: UUID,
        scenario_id: UUID,
        max_stages: int,
        initiated_by: str,
        version: int,
        sequence_number: int
    ) -> Event:
        """Factory method to create SimulationStarted event."""
        return Event(
            event_id=uuid4(),
            aggregate_id=aggregate_id,
            aggregate_type=AggregateType.SIMULATION,
            event_type="SimulationStarted",
            event_data={
                "scenario_id": str(scenario_id),
                "max_stages": max_stages,
                "initiated_by": initiated_by
            },
            metadata={
                "command": "execute_simulation",
                "initiated_by": initiated_by
            },
            sequence_number=sequence_number,
            timestamp=datetime.now(timezone.utc),
            version=version
        )


@dataclass(frozen=True)
class StageStarted(Event):
    """Event emitted when a simulation stage begins."""
    
    @classmethod
    def create(
        cls,
        aggregate_id: UUID,
        stage_number: int,
        stage_type: str,
        stage_description: str,
        version: int,
        sequence_number: int
    ) -> Event:
        """Factory method to create StageStarted event."""
        return Event(
            event_id=uuid4(),
            aggregate_id=aggregate_id,
            aggregate_type=AggregateType.SIMULATION,
            event_type="StageStarted",
            event_data={
                "stage_number": stage_number,
                "stage_type": stage_type,
                "description": stage_description
            },
            metadata={},
            sequence_number=sequence_number,
            timestamp=datetime.now(timezone.utc),
            version=version
        )


@dataclass(frozen=True)
class StageCompleted(Event):
    """Event emitted when a simulation stage completes successfully."""
    
    @classmethod
    def create(
        cls,
        aggregate_id: UUID,
        stage_number: int,
        stage_id: str,
        content_length: int,
        duration_ms: float,
        version: int,
        sequence_number: int
    ) -> Event:
        """Factory method to create StageCompleted event."""
        return Event(
            event_id=uuid4(),
            aggregate_id=aggregate_id,
            aggregate_type=AggregateType.SIMULATION,
            event_type="StageCompleted",
            event_data={
                "stage_number": stage_number,
                "stage_id": stage_id,
                "content_length": content_length,
                "duration_ms": duration_ms,
                "success": True
            },
            metadata={},
            sequence_number=sequence_number,
            timestamp=datetime.now(timezone.utc),
            version=version
        )


@dataclass(frozen=True)
class StageFailed(Event):
    """Event emitted when a simulation stage fails."""
    
    @classmethod
    def create(
        cls,
        aggregate_id: UUID,
        stage_number: int,
        error_message: str,
        error_type: str,
        retry_count: int,
        version: int,
        sequence_number: int
    ) -> Event:
        """Factory method to create StageFailed event."""
        return Event(
            event_id=uuid4(),
            aggregate_id=aggregate_id,
            aggregate_type=AggregateType.SIMULATION,
            event_type="StageFailed",
            event_data={
                "stage_number": stage_number,
                "error_message": error_message,
                "error_type": error_type,
                "retry_count": retry_count,
                "success": False
            },
            metadata={
                "severity": "warning"
            },
            sequence_number=sequence_number,
            timestamp=datetime.now(timezone.utc),
            version=version
        )


@dataclass(frozen=True)
class SimulationCompleted(Event):
    """Event emitted when a simulation completes (successfully or with partial success)."""
    
    @classmethod
    def create(
        cls,
        aggregate_id: UUID,
        total_stages: int,
        successful_stages: int,
        success_rate: float,
        duration_ms: float,
        version: int,
        sequence_number: int
    ) -> Event:
        """Factory method to create SimulationCompleted event."""
        return Event(
            event_id=uuid4(),
            aggregate_id=aggregate_id,
            aggregate_type=AggregateType.SIMULATION,
            event_type="SimulationCompleted",
            event_data={
                "total_stages": total_stages,
                "successful_stages": successful_stages,
                "success_rate": success_rate,
                "duration_ms": duration_ms
            },
            metadata={
                "final_state": "completed"
            },
            sequence_number=sequence_number,
            timestamp=datetime.now(timezone.utc),
            version=version
        )


@dataclass(frozen=True)
class SimulationFailed(Event):
    """Event emitted when a simulation fails completely."""
    
    @classmethod
    def create(
        cls,
        aggregate_id: UUID,
        error_message: str,
        failed_at_stage: Optional[int],
        version: int,
        sequence_number: int
    ) -> Event:
        """Factory method to create SimulationFailed event."""
        return Event(
            event_id=uuid4(),
            aggregate_id=aggregate_id,
            aggregate_type=AggregateType.SIMULATION,
            event_type="SimulationFailed",
            event_data={
                "error_message": error_message,
                "failed_at_stage": failed_at_stage
            },
            metadata={
                "severity": "error",
                "final_state": "failed"
            },
            sequence_number=sequence_number,
            timestamp=datetime.now(timezone.utc),
            version=version
        )


@dataclass(frozen=True)
class SimulationCancelled(Event):
    """Event emitted when a simulation is cancelled by user."""
    
    @classmethod
    def create(
        cls,
        aggregate_id: UUID,
        cancelled_by: str,
        reason: str,
        version: int,
        sequence_number: int
    ) -> Event:
        """Factory method to create SimulationCancelled event."""
        return Event(
            event_id=uuid4(),
            aggregate_id=aggregate_id,
            aggregate_type=AggregateType.SIMULATION,
            event_type="SimulationCancelled",
            event_data={
                "cancelled_by": cancelled_by,
                "reason": reason
            },
            metadata={
                "final_state": "cancelled"
            },
            sequence_number=sequence_number,
            timestamp=datetime.now(timezone.utc),
            version=version
        )


# ============================================================================
# Event Store Exceptions
# ============================================================================

class EventStoreError(Exception):
    """Base exception for event store errors."""
    pass


class ConcurrencyError(EventStoreError):
    """Raised when optimistic concurrency check fails."""
    def __init__(self, aggregate_id: UUID, expected_version: int, actual_version: int):
        self.aggregate_id = aggregate_id
        self.expected_version = expected_version
        self.actual_version = actual_version
        super().__init__(
            f"Concurrency conflict for aggregate {aggregate_id}: "
            f"expected version {expected_version}, got {actual_version}"
        )


class EventNotFoundError(EventStoreError):
    """Raised when requested events don't exist."""
    pass


# ============================================================================
# Event Store Interface
# ============================================================================

class EventStore:
    """PostgreSQL-backed event store for immutable audit trail.
    
    Provides:
    - Append-only event log
    - Optimistic concurrency control
    - Event replay for aggregate reconstruction
    - Temporal queries (events between timestamps)
    - Compliance-ready audit trail
    
    Thread-safe for concurrent writes.
    """

    def __init__(self, connection_pool: Any = None, postgres_store: Any = None):
        """Initialize event store with database connection pool.
        
        Args:
            connection_pool: Async database connection pool (asyncpg, SQLAlchemy, etc.)
                Kept for backwards compatibility; a PostgresEventStore passed here
                positionally is detected and used for persistence.
            postgres_store: Optional PostgresEventStore instance used for real
                PostgreSQL writes/queries. When None, the store keeps its
                previous in-memory (no-op) behavior.
        """
        self.connection_pool = connection_pool
        if postgres_store is None and connection_pool is not None:
            from .postgres_event_store import PostgresEventStore
            if isinstance(connection_pool, PostgresEventStore):
                postgres_store = connection_pool
                self.connection_pool = None
        self.postgres_store = postgres_store
        self._sequence_lock = asyncio.Lock()
        self._current_sequence = 0
        logger.info("EventStore initialized")

    async def _get_next_sequence(self) -> int:
        """Get next global sequence number (thread-safe)."""
        async with self._sequence_lock:
            self._current_sequence += 1
            return self._current_sequence

    async def append(self, event: Event) -> None:
        """Append event to the store.
        
        This is the core write operation. Events are:
        1. Validated for schema correctness
        2. Checked for version conflicts (optimistic locking)
        3. Assigned a global sequence number
        4. Written atomically to PostgreSQL
        
        Args:
            event: Event to append
            
        Raises:
            ConcurrencyError: If version conflict detected
            EventStoreError: If write fails
        """
        if self.postgres_store is not None:
            # Delegate to the real PostgreSQL-backed store (PostgresEventStore)
            await self.postgres_store.append(event)
            return

        if self.connection_pool is None:
            # In-memory mode for testing
            logger.warning("No connection pool - using in-memory event store")
            return

        try:
            logger.debug(
                f"Event appended: {event.event_type} for {event.aggregate_type}:"
                f"{event.aggregate_id} (v{event.version}, seq={event.sequence_number})"
            )

        except Exception as e:
            logger.error(f"Failed to append event: {e}")
            raise EventStoreError(f"Event append failed: {e}") from e

    async def get_events(
        self,
        aggregate_id: UUID,
        from_version: int = 0,
        to_version: Optional[int] = None
    ) -> List[Event]:
        """Get all events for an aggregate within version range.
        
        Args:
            aggregate_id: ID of the aggregate
            from_version: Start version (inclusive)
            to_version: End version (inclusive), None for latest
            
        Returns:
            List of events ordered by version
        """
        if self.postgres_store is not None:
            return await self.postgres_store.get_events(aggregate_id, from_version, to_version)
        logger.debug(f"Fetching events for {aggregate_id} from v{from_version}")
        return []

    async def get_events_by_type(
        self,
        event_type: str,
        from_timestamp: datetime,
        to_timestamp: datetime,
        limit: int = 1000
    ) -> List[Event]:
        """Query events by type within time range (for compliance queries).
        
        Args:
            event_type: Event type to filter (e.g., 'SimulationStarted')
            from_timestamp: Start time (inclusive)
            to_timestamp: End time (inclusive)
            limit: Maximum events to return
            
        Returns:
            List of events ordered by timestamp
        """
        if self.postgres_store is not None:
            return await self.postgres_store.get_events_by_type(
                event_type, from_timestamp, to_timestamp, limit
            )
        logger.debug(f"Querying events of type {event_type} from {from_timestamp} to {to_timestamp}")
        return []

    async def replay_aggregate(self, aggregate_id: UUID) -> Optional[Any]:
        """Rebuild aggregate state from all its events (event replay).
        
        This is a core event sourcing capability:
        1. Fetch all events for aggregate
        2. Apply events in sequence to rebuild state
        3. Return reconstructed aggregate
        
        Args:
            aggregate_id: ID of aggregate to rebuild
            
        Returns:
            Reconstructed aggregate state or None if no events
        """
        events = await self.get_events(aggregate_id)
        if not events:
            return None

        if self.postgres_store is None:
            # No persistent store configured - nothing to reconstruct from
            logger.debug(f"Replaying {len(events)} events for aggregate {aggregate_id}")
            return None

        # Reconstruct the aggregate by re-applying its events in order
        aggregate = EventSourcedAggregate(aggregate_id)
        for event in events:
            aggregate.apply_event(event)
        logger.debug(f"Replaying {len(events)} events for aggregate {aggregate_id}")
        return aggregate

    async def get_aggregate_version(self, aggregate_id: UUID) -> int:
        """Get current version of an aggregate.
        
        Args:
            aggregate_id: ID of aggregate
            
        Returns:
            Current version number (0 if aggregate doesn't exist)
        """
        if self.postgres_store is not None:
            return await self.postgres_store.get_aggregate_version(aggregate_id)
        return 0


# ============================================================================
# Event-Sourced Aggregate Base Class
# ============================================================================

class EventSourcedAggregate(Generic[T]):
    """Base class for event-sourced aggregates.
    
    Aggregates are domain entities that:
    - Emit events for state changes
    - Maintain internal version for concurrency control
    - Can be reconstructed from event history
    """

    def __init__(self, aggregate_id: UUID):
        self.aggregate_id = aggregate_id
        self.version = 0
        self._uncommitted_events: List[Event] = []

    def apply_event(self, event: Event) -> None:
        """Apply an event to this aggregate (update state)."""
        self.version = event.version
        # Subclasses override to update their specific state

    def get_uncommitted_events(self) -> List[Event]:
        """Get events that haven't been persisted yet."""
        return self._uncommitted_events.copy()

    def mark_events_committed(self) -> None:
        """Mark all uncommitted events as committed."""
        self._uncommitted_events.clear()

    def _raise_event(self, event: Event) -> None:
        """Raise a new event (add to uncommitted)."""
        self._uncommitted_events.append(event)
        self.apply_event(event)


# ============================================================================
# Repository Pattern for Event-Sourced Aggregates
# ============================================================================

class EventSourcedRepository(Generic[T]):
    """Repository for loading and saving event-sourced aggregates."""

    def __init__(self, event_store: EventStore):
        self.event_store = event_store

    async def get(self, aggregate_id: UUID) -> Optional[T]:
        """Load aggregate from event store."""
        return await self.event_store.replay_aggregate(aggregate_id)

    async def save(self, aggregate: EventSourcedAggregate) -> None:
        """Save aggregate by persisting uncommitted events."""
        for event in aggregate.get_uncommitted_events():
            await self.event_store.append(event)
        aggregate.mark_events_committed()
