"""Unit tests for the API storage layer.

The repository is exercised against SQLite via aiosqlite: the table
definitions in ciicerone.api.storage use portable column types (sa.Uuid /
sa.JSON), so the same code path runs against PostgreSQL in production and
SQLite in tests.

Owner: Phase 0 item 4 - API persistence for scenarios and simulations
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from ciicerone.api.storage import ScenarioStorage
from ciicerone.core.models import (
    SimulationResult,
    SimulationStage,
    SimulationStatus,
    ThreatScenario,
    ThreatType,
)


@pytest.fixture
async def storage(tmp_path):
    """ScenarioStorage backed by a temporary SQLite database file."""
    store = await ScenarioStorage.create(
        f"sqlite+aiosqlite:///{tmp_path}/ciicerone-test.db",
        create_tables=True,
    )
    yield store
    await store.close()


def make_scenario(**overrides) -> ThreatScenario:
    """Build a ThreatScenario with sensible defaults."""
    kwargs = {
        "name": "Test Scenario",
        "threat_type": ThreatType.PHISHING,
        "description": "A test scenario",
        "severity": "high",
        "target_systems": ["email"],
        "attack_vectors": ["spear_phishing"],
        "metadata": {"origin": "unit-test"},
    }
    kwargs.update(overrides)
    return ThreatScenario(**kwargs)


def make_result(scenario_id: str) -> SimulationResult:
    """Build a completed SimulationResult for the given scenario."""
    start = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    end = datetime(2026, 1, 1, 12, 0, 30, tzinfo=timezone.utc)
    return SimulationResult(
        status=SimulationStatus.COMPLETED,
        scenario_id=scenario_id,
        stages=[
            SimulationStage(stage_type="reconnaissance", content="stage content"),
            SimulationStage(stage_type="delivery", content="more content", success=False),
        ],
        start_time=start,
        end_time=end,
    )


class TestScenarioStorage:
    """Scenario persistence round-trips."""

    async def test_create_and_get_scenario_round_trip(self, storage):
        scenario = make_scenario()
        await storage.create_scenario(scenario)

        loaded = await storage.get_scenario(scenario.scenario_id)

        assert loaded is not None
        assert loaded.scenario_id == scenario.scenario_id
        assert loaded.name == scenario.name
        assert loaded.threat_type == ThreatType.PHISHING
        assert loaded.description == "A test scenario"
        assert loaded.severity == "high"
        assert loaded.target_systems == ["email"]
        assert loaded.attack_vectors == ["spear_phishing"]
        assert loaded.metadata == {"origin": "unit-test"}

    async def test_get_unknown_scenario_returns_none(self, storage):
        assert await storage.get_scenario(str(uuid4())) is None

    async def test_get_scenario_with_invalid_id_returns_none(self, storage):
        assert await storage.get_scenario("not-a-uuid") is None

    async def test_created_at_is_preserved(self, storage):
        created_at = datetime(2026, 3, 1, 8, 30, 0, tzinfo=timezone.utc)
        scenario = make_scenario(created_at=created_at)
        await storage.create_scenario(scenario)

        loaded = await storage.get_scenario(scenario.scenario_id)

        assert loaded is not None
        assert loaded.created_at == created_at


class TestSimulationStorage:
    """Simulation record persistence."""

    async def test_create_and_get_simulation(self, storage):
        scenario = make_scenario()
        await storage.create_scenario(scenario)
        result = make_result(scenario.scenario_id)
        await storage.create_simulation(result)

        record = await storage.get_simulation(result.result_id)

        assert record is not None
        assert record["simulation_id"] == result.result_id
        assert record["scenario_id"] == scenario.scenario_id
        assert record["status"] == "completed"
        # SQLite drops timezone info on DateTime columns; PostgreSQL preserves it
        assert record["started_at"] == result.start_time.replace(tzinfo=None).isoformat()
        assert record["finished_at"] == result.end_time.replace(tzinfo=None).isoformat()
        assert record["result"]["stages_completed"] == 2
        assert record["result"]["successful_stages"] == 1
        assert record["result"]["success_rate"] == result.success_rate
        assert record["result"]["total_duration_seconds"] == 30.0

    async def test_list_simulations_returns_records(self, storage):
        scenario = make_scenario()
        await storage.create_scenario(scenario)
        first = make_result(scenario.scenario_id)
        second = make_result(scenario.scenario_id)
        await storage.create_simulation(first)
        await storage.create_simulation(second)

        records = await storage.list_simulations()

        assert len(records) == 2
        assert {r["simulation_id"] for r in records} == {first.result_id, second.result_id}

    async def test_get_unknown_simulation_returns_none(self, storage):
        assert await storage.get_simulation(str(uuid4())) is None

    async def test_get_simulation_with_invalid_id_returns_none(self, storage):
        assert await storage.get_simulation("not-a-uuid") is None
