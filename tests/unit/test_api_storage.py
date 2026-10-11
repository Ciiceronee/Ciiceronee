"""Tests for API persistence wiring.

Covers: POST /simulations fallback when storage is disabled, unknown scenario
404 when storage is enabled, scenario persistence on POST /scenarios, and the
storage-backed simulation query endpoints.

Like test_api_security.py, these tests override the simulator dependency and
do not enter the app lifespan; the storage global is replaced with a fake.

Owner: Phase 0 item 4 - API persistence for scenarios and simulations
"""

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from ciicerone.api import main as api_main
from ciicerone.api.main import create_app
from ciicerone.config.loader import CiiceroneConfig
from ciicerone.core.models import (
    SimulationResult,
    SimulationStatus,
    ThreatScenario,
    ThreatType,
)

SCENARIO_ID = "11111111-1111-1111-1111-111111111111"


def make_config() -> CiiceroneConfig:
    """Config with authentication disabled for endpoint testing."""
    config = CiiceroneConfig()
    config.api.authentication.enabled = False
    return config


class _FakeSimulator:
    """Simulator stand-in recording the scenario it was asked to run."""

    def __init__(self):
        self.received_scenarios = []

    async def execute_simulation(self, scenario):
        self.received_scenarios.append(scenario)
        return SimulationResult(
            status=SimulationStatus.COMPLETED,
            scenario_id=scenario.scenario_id,
            start_time=datetime(2026, 1, 1, tzinfo=timezone.utc),
            end_time=datetime(2026, 1, 1, 0, 1, tzinfo=timezone.utc),
        )


class _FakeStorage:
    """In-memory stand-in with the ScenarioStorage interface."""

    def __init__(self, scenarios=None):
        self.scenarios = dict(scenarios or {})
        self.records = {}

    async def create_scenario(self, scenario):
        self.scenarios[scenario.scenario_id] = scenario

    async def get_scenario(self, scenario_id):
        return self.scenarios.get(scenario_id)

    async def create_simulation(self, result):
        self.records[result.result_id] = {
            "simulation_id": result.result_id,
            "scenario_id": str(result.scenario_id),
            "status": "completed",
            "started_at": result.start_time.isoformat(),
            "finished_at": result.end_time.isoformat(),
            "result": {"stages_completed": len(result.stages)},
        }

    async def get_simulation(self, simulation_id):
        return self.records.get(simulation_id)

    async def list_simulations(self, limit=100):
        return list(self.records.values())[:limit]


def make_client(simulator, storage=None):
    """TestClient with simulator and (optionally) storage overridden."""
    app = create_app(make_config())
    app.dependency_overrides[api_main.get_simulator] = lambda: simulator
    if storage is not None:
        api_main.storage = storage
    return TestClient(app)


SCENARIO_PAYLOAD = {
    "name": "Persisted Scenario",
    "threat_type": "phishing",
    "description": "stored scenario",
    "severity": "high",
    "target_systems": ["email"],
    "attack_vectors": ["spear_phishing"],
    "metadata": {"origin": "test"},
}


class TestRunSimulationStorageDisabled:
    """Fallback behavior when storage is disabled must be preserved."""

    async def test_falls_back_to_fabricated_scenario(self, monkeypatch):
        monkeypatch.setattr(api_main, "storage", None)
        simulator = _FakeSimulator()
        client = make_client(simulator)

        response = client.post("/simulations", json={"scenario_id": "some-scenario-id"})

        assert response.status_code == 202
        assert len(simulator.received_scenarios) == 1
        scenario = simulator.received_scenarios[0]
        assert scenario.name == "Scenario_some-scenario-id"
        assert scenario.threat_type == ThreatType.CUSTOM

    async def test_does_not_persist_anything(self, monkeypatch):
        monkeypatch.setattr(api_main, "storage", None)
        client = make_client(_FakeSimulator())

        response = client.post("/simulations", json={"scenario_id": "some-scenario-id"})

        assert response.status_code == 202
        assert response.json()["status"] == "completed"


class TestRunSimulationStorageEnabled:
    """Scenario lookup and persistence when storage is enabled."""

    async def test_unknown_scenario_returns_404(self, monkeypatch):
        storage = _FakeStorage()
        monkeypatch.setattr(api_main, "storage", storage)
        simulator = _FakeSimulator()
        client = make_client(simulator, storage)

        response = client.post("/simulations", json={"scenario_id": SCENARIO_ID})

        assert response.status_code == 404
        assert simulator.received_scenarios == []

    async def test_persisted_scenario_is_loaded_and_result_saved(self, monkeypatch):
        scenario = ThreatScenario(
            name="Persisted Scenario",
            threat_type=ThreatType.PHISHING,
            scenario_id=SCENARIO_ID,
        )
        storage = _FakeStorage(scenarios={SCENARIO_ID: scenario})
        monkeypatch.setattr(api_main, "storage", storage)
        simulator = _FakeSimulator()
        client = make_client(simulator, storage)

        response = client.post("/simulations", json={"scenario_id": SCENARIO_ID})

        assert response.status_code == 202
        assert simulator.received_scenarios == [scenario]
        assert len(storage.records) == 1


class TestCreateScenarioPersistence:
    """POST /scenarios persists the scenario when storage is enabled."""

    async def test_scenario_persisted_when_storage_enabled(self, monkeypatch):
        storage = _FakeStorage()
        monkeypatch.setattr(api_main, "storage", storage)
        client = make_client(_FakeSimulator(), storage)

        response = client.post("/scenarios", json=SCENARIO_PAYLOAD)

        assert response.status_code == 201
        scenario_id = response.json()["scenario_id"]
        assert scenario_id in storage.scenarios
        assert storage.scenarios[scenario_id].name == "Persisted Scenario"

    async def test_scenario_returned_when_storage_disabled(self, monkeypatch):
        monkeypatch.setattr(api_main, "storage", None)
        client = make_client(_FakeSimulator())

        response = client.post("/scenarios", json=SCENARIO_PAYLOAD)

        assert response.status_code == 201
        assert response.json()["name"] == "Persisted Scenario"


class TestSimulationQueryEndpoints:
    """GET endpoints read from storage when enabled."""

    async def test_list_returns_503_when_storage_disabled(self, monkeypatch):
        monkeypatch.setattr(api_main, "storage", None)
        client = make_client(_FakeSimulator())

        response = client.get("/simulations")

        assert response.status_code == 503

    async def test_list_returns_records_from_storage(self, monkeypatch):
        storage = _FakeStorage()
        monkeypatch.setattr(api_main, "storage", storage)
        simulator = _FakeSimulator()
        client = make_client(simulator, storage)
        # Persist a record directly, then list it
        result = make_result()
        storage.records[result.result_id] = {
            "simulation_id": result.result_id,
            "scenario_id": SCENARIO_ID,
            "status": "completed",
            "started_at": result.start_time.isoformat(),
            "finished_at": None,
            "result": {"stages_completed": 0},
        }

        response = client.get("/simulations")

        assert response.status_code == 200
        body = response.json()
        assert len(body["simulations"]) == 1
        assert body["simulations"][0]["simulation_id"] == result.result_id

    async def test_get_by_id_404_for_unknown_simulation(self, monkeypatch):
        storage = _FakeStorage()
        monkeypatch.setattr(api_main, "storage", storage)
        client = make_client(_FakeSimulator(), storage)

        response = client.get(f"/simulations/{SCENARIO_ID}")

        assert response.status_code == 404

    async def test_get_by_id_returns_record(self, monkeypatch):
        storage = _FakeStorage()
        monkeypatch.setattr(api_main, "storage", storage)
        client = make_client(_FakeSimulator(), storage)
        result = make_result()
        storage.records[result.result_id] = {
            "simulation_id": result.result_id,
            "scenario_id": SCENARIO_ID,
            "status": "completed",
            "started_at": result.start_time.isoformat(),
            "finished_at": None,
            "result": {},
        }

        response = client.get(f"/simulations/{result.result_id}")

        assert response.status_code == 200
        assert response.json()["simulation_id"] == result.result_id

    async def test_get_by_id_503_when_storage_disabled(self, monkeypatch):
        monkeypatch.setattr(api_main, "storage", None)
        client = make_client(_FakeSimulator())

        response = client.get(f"/simulations/{SCENARIO_ID}")

        assert response.status_code == 503


def make_result() -> SimulationResult:
    """Build a canned SimulationResult (synchronous test helper)."""
    return SimulationResult(
        status=SimulationStatus.COMPLETED,
        scenario_id=SCENARIO_ID,
        start_time=datetime(2026, 1, 1, tzinfo=timezone.utc),
        end_time=datetime(2026, 1, 1, 0, 1, tzinfo=timezone.utc),
    )
