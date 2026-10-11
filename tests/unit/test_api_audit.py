"""Tests for simulation audit-trail emission.

Covers: SimulationStarted/SimulationCompleted emission on success,
SimulationFailed on simulator error, audit failures never failing the request,
and the GET /audit/events/{aggregate_id} read endpoint.

Like test_api_storage.py, these tests override the simulator dependency and
do not enter the app lifespan; the event_store global is replaced with a fake.

Owner: simulator -> event store wiring (audit trail)
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
    """Simulator stand-in; optionally raises to simulate a failed run."""

    def __init__(self, fail_with: Exception | None = None):
        self.fail_with = fail_with

    async def execute_simulation(self, scenario):
        if self.fail_with is not None:
            raise self.fail_with
        return SimulationResult(
            status=SimulationStatus.COMPLETED,
            scenario_id=scenario.scenario_id,
            start_time=datetime(2026, 1, 1, tzinfo=timezone.utc),
            end_time=datetime(2026, 1, 1, 0, 1, tzinfo=timezone.utc),
        )


class _FakeEventStore:
    """Records appended events and serves them back by aggregate."""

    def __init__(self, fail_with: Exception | None = None):
        self.fail_with = fail_with
        self.appended = []

    async def append(self, event):
        if self.fail_with is not None:
            raise self.fail_with
        self.appended.append(event)

    async def get_events(self, aggregate_id, from_version=0, to_version=None):
        return [e for e in self.appended if e.aggregate_id == aggregate_id]


def make_client(simulator, event_store):
    """TestClient with simulator overridden and the event_store global faked."""
    app = create_app(make_config())
    app.dependency_overrides[api_main.get_simulator] = lambda: simulator
    api_main.event_store = event_store
    return TestClient(app)


class TestAuditEmission:
    async def test_success_emits_started_and_completed(self, monkeypatch):
        store = _FakeEventStore()
        monkeypatch.setattr(api_main, "event_store", store)
        monkeypatch.setattr(api_main, "storage", None)
        client = make_client(_FakeSimulator(), store)

        response = client.post("/simulations", json={"scenario_id": "any-id"})

        assert response.status_code == 202
        audit_trail_id = response.json()["audit_trail_id"]
        event_types = [e.event_type for e in store.appended]
        assert event_types == ["SimulationStarted", "SimulationCompleted"]
        started, completed = store.appended
        assert str(started.aggregate_id) == audit_trail_id
        assert started.version == 1
        assert completed.version == 2
        assert completed.event_data["status"] == "completed"

    async def test_failure_emits_started_and_failed(self, monkeypatch):
        store = _FakeEventStore()
        monkeypatch.setattr(api_main, "event_store", store)
        monkeypatch.setattr(api_main, "storage", None)
        client = make_client(_FakeSimulator(RuntimeError("boom")), store)

        response = client.post("/simulations", json={"scenario_id": "any-id"})

        assert response.status_code == 500
        event_types = [e.event_type for e in store.appended]
        assert event_types == ["SimulationStarted", "SimulationFailed"]
        assert store.appended[1].event_data["error"] == "boom"

    async def test_audit_failure_does_not_fail_request(self, monkeypatch):
        store = _FakeEventStore(fail_with=RuntimeError("db down"))
        monkeypatch.setattr(api_main, "event_store", store)
        monkeypatch.setattr(api_main, "storage", None)
        client = make_client(_FakeSimulator(), store)

        response = client.post("/simulations", json={"scenario_id": "any-id"})

        assert response.status_code == 202

    async def test_no_event_store_is_silent_noop(self, monkeypatch):
        monkeypatch.setattr(api_main, "event_store", None)
        monkeypatch.setattr(api_main, "storage", None)
        client = make_client(_FakeSimulator(), None)

        response = client.post("/simulations", json={"scenario_id": "any-id"})

        assert response.status_code == 202


class TestAuditTrailEndpoint:
    async def test_returns_events_for_aggregate(self, monkeypatch):
        store = _FakeEventStore()
        monkeypatch.setattr(api_main, "event_store", store)
        monkeypatch.setattr(api_main, "storage", None)
        client = make_client(_FakeSimulator(), store)

        run = client.post("/simulations", json={"scenario_id": "any-id"})
        trail_id = run.json()["audit_trail_id"]

        response = client.get(f"/audit/events/{trail_id}")

        assert response.status_code == 200
        body = response.json()
        assert body["event_count"] == 2
        assert [e["event_type"] for e in body["events"]] == [
            "SimulationStarted",
            "SimulationCompleted",
        ]

    async def test_disabled_returns_503(self, monkeypatch):
        monkeypatch.setattr(api_main, "event_store", None)
        client = make_client(_FakeSimulator(), None)

        response = client.get("/audit/events/11111111-1111-1111-1111-111111111111")

        assert response.status_code == 503

    async def test_invalid_uuid_returns_400(self, monkeypatch):
        store = _FakeEventStore()
        monkeypatch.setattr(api_main, "event_store", store)
        client = make_client(_FakeSimulator(), store)

        response = client.get("/audit/events/not-a-uuid")

        assert response.status_code == 400


class TestScenarioEvents:
    async def test_started_event_carries_scenario_context(self, monkeypatch):
        store = _FakeEventStore()
        monkeypatch.setattr(api_main, "event_store", store)
        monkeypatch.setattr(api_main, "storage", None)
        client = make_client(_FakeSimulator(), store)

        response = client.post("/simulations", json={"scenario_id": "any-id"})

        assert response.status_code == 202
        started = store.appended[0]
        assert started.aggregate_type.value == "simulation"
        assert started.event_data["threat_type"] == ThreatType.CUSTOM.value
        assert started.event_data["storage_backed"] is False
