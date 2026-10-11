"""Unit tests for EventStore persistence delegation.

When a PostgresEventStore is configured, EventStore must perform real writes
and queries through it; without one, the previous in-memory (no-op) behavior
is preserved so existing callers and tests keep working.

Owner: Phase 0 item 4 - real event-sourcing audit trail
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from ciicerone.core.event_sourcing import AggregateType, Event, EventStore


class FakePostgresStore:
    """In-memory stand-in implementing the PostgresEventStore interface."""

    def __init__(self):
        self.appended = []

    async def append(self, event):
        self.appended.append(event)
        return event.sequence_number

    async def get_events(self, aggregate_id, from_version=0, to_version=None):
        events = [
            e
            for e in self.appended
            if e.aggregate_id == aggregate_id and e.version >= from_version
        ]
        if to_version is not None:
            events = [e for e in events if e.version <= to_version]
        return sorted(events, key=lambda e: e.version)

    async def get_events_by_type(self, event_type, from_timestamp, to_timestamp, limit=1000):
        return [
            e
            for e in self.appended
            if e.event_type == event_type and from_timestamp <= e.timestamp <= to_timestamp
        ][:limit]

    async def get_aggregate_version(self, aggregate_id):
        versions = [e.version for e in self.appended if e.aggregate_id == aggregate_id]
        return max(versions, default=0)


def make_event(aggregate_id, version, event_type="TestEvent", sequence_number=1):
    return Event(
        event_id=uuid4(),
        aggregate_id=aggregate_id,
        aggregate_type=AggregateType.SIMULATION,
        event_type=event_type,
        event_data={"version": version},
        metadata={},
        sequence_number=sequence_number,
        timestamp=datetime.now(timezone.utc),
        version=version,
    )


@pytest.fixture
def fake_store():
    return FakePostgresStore()


@pytest.fixture
def event_store(fake_store):
    return EventStore(postgres_store=fake_store)


class TestStoreDelegation:
    """EventStore delegates to the configured PostgresEventStore."""

    async def test_append_delegates_to_store(self, event_store, fake_store):
        event = make_event(uuid4(), version=1)
        await event_store.append(event)
        assert fake_store.appended == [event]

    async def test_get_events_delegates_and_orders_by_version(self, event_store):
        aggregate_id = uuid4()
        await event_store.append(make_event(aggregate_id, version=2, sequence_number=2))
        await event_store.append(make_event(aggregate_id, version=1, sequence_number=1))
        await event_store.append(make_event(uuid4(), version=1, sequence_number=3))

        events = await event_store.get_events(aggregate_id)

        assert [e.version for e in events] == [1, 2]

    async def test_get_events_respects_version_range(self, event_store):
        aggregate_id = uuid4()
        for version in (1, 2, 3):
            await event_store.append(make_event(aggregate_id, version=version, sequence_number=version))

        events = await event_store.get_events(aggregate_id, from_version=2, to_version=3)

        assert [e.version for e in events] == [2, 3]

    async def test_get_events_by_type_delegates(self, event_store):
        aggregate_id = uuid4()
        now = datetime.now(timezone.utc)
        await event_store.append(
            make_event(aggregate_id, version=1, event_type="SimulationStarted", sequence_number=1)
        )
        await event_store.append(
            make_event(aggregate_id, version=2, event_type="StageCompleted", sequence_number=2)
        )

        events = await event_store.get_events_by_type(
            "SimulationStarted", now - timedelta(minutes=1), now + timedelta(minutes=1)
        )

        assert len(events) == 1
        assert events[0].event_type == "SimulationStarted"

    async def test_get_aggregate_version_delegates(self, event_store):
        aggregate_id = uuid4()
        assert await event_store.get_aggregate_version(aggregate_id) == 0
        await event_store.append(make_event(aggregate_id, version=1, sequence_number=1))
        await event_store.append(make_event(aggregate_id, version=2, sequence_number=2))
        assert await event_store.get_aggregate_version(aggregate_id) == 2

    async def test_replay_aggregate_reconstructs_state(self, event_store):
        aggregate_id = uuid4()
        await event_store.append(make_event(aggregate_id, version=1, sequence_number=1))
        await event_store.append(make_event(aggregate_id, version=2, sequence_number=2))

        aggregate = await event_store.replay_aggregate(aggregate_id)

        assert aggregate is not None
        assert aggregate.aggregate_id == aggregate_id
        assert aggregate.version == 2

    async def test_replay_unknown_aggregate_returns_none(self, event_store):
        assert await event_store.replay_aggregate(uuid4()) is None

    def test_postgres_store_passed_positionally_is_detected(self):
        """A PostgresEventStore given as connection_pool is picked up."""
        from ciicerone.core.postgres_event_store import PostgresEventStore

        pg_store = PostgresEventStore(pool=object())  # never connects
        store = EventStore(connection_pool=pg_store)
        assert store.postgres_store is pg_store
        assert store.connection_pool is None


class TestInMemoryFallback:
    """Without a store, previous no-op behavior is preserved."""

    @pytest.fixture
    def in_memory_store(self):
        return EventStore(connection_pool=None)

    async def test_append_is_noop(self, in_memory_store):
        await in_memory_store.append(make_event(uuid4(), version=1))

    async def test_get_events_returns_empty_list(self, in_memory_store):
        assert await in_memory_store.get_events(uuid4()) == []

    async def test_get_events_by_type_returns_empty_list(self, in_memory_store):
        now = datetime.now(timezone.utc)
        events = await in_memory_store.get_events_by_type("TestEvent", now, now)
        assert events == []

    async def test_get_aggregate_version_returns_zero(self, in_memory_store):
        assert await in_memory_store.get_aggregate_version(uuid4()) == 0

    async def test_replay_aggregate_returns_none(self, in_memory_store):
        assert await in_memory_store.replay_aggregate(uuid4()) is None
