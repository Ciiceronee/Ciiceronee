"""
Tests for API security hardening: API key authentication, CORS lockdown,
and safety filter enforcement on the LLM generation endpoint.

Phase 0 security hardening - Issue: unauthenticated API, unwired safety
filter, wildcard CORS.

Note: tests override the LLM manager dependency and do not enter the app
lifespan, because LLMManager's fire-and-forget Ollama auto-detection
leaks an unawaited coroutine that pytest's unraisable-exception check
(filterwarnings = error) rejects.
"""

import pytest
from fastapi.testclient import TestClient

from ciicerone.api import main as api_main
from ciicerone.api.main import create_app
from ciicerone.config.loader import (
    AuthenticationConfig,
    CiiceroneConfig,
    CORSConfig,
)

TEST_API_KEY = "test-secret-key"

MALICIOUS_PROMPT = "import subprocess and run it with shell=True please"
MALICIOUS_OUTPUT = "import subprocess; subprocess.call('id', shell=True)"
SAFE_PROMPT = "Write a benign phishing-awareness training email for employees."
SAFE_OUTPUT = "This is a safe simulated phishing awareness training email."


def make_config(
    auth_enabled: bool = True,
    api_key: str = TEST_API_KEY,
    exempt_paths=None,
    cors: CORSConfig = None,
) -> CiiceroneConfig:
    """Build a CiiceroneConfig with the given API security settings."""
    config = CiiceroneConfig()
    config.api.authentication = AuthenticationConfig(
        enabled=auth_enabled,
        api_key=api_key if auth_enabled else (api_key or None),
        exempt_paths=(
            exempt_paths
            if exempt_paths is not None
            else AuthenticationConfig().exempt_paths
        ),
    )
    if cors is not None:
        config.api.cors = cors
    return config


class _FakeUsage:
    total_tokens = 42


class _FakeLLMResponse:
    def __init__(self, content: str):
        self.content = content
        self.provider = "mock"
        self.model = "mock-model"
        self.usage = _FakeUsage()
        self.safety_score = 1.0
        self.metadata = {}


class _FakeLLMManager:
    """Minimal LLM manager stand-in returning canned content."""

    def __init__(self, content: str = SAFE_OUTPUT):
        self._content = content

    async def generate_content(self, **kwargs):
        return _FakeLLMResponse(self._content)

    def get_available_providers(self):
        return ["mock"]

    def get_default_provider(self):
        return "mock"


def make_client(config: CiiceroneConfig, llm_content: str = SAFE_OUTPUT) -> TestClient:
    """Create a TestClient with the LLM manager dependency replaced.

    The lifespan is intentionally not entered (no ``with`` block).
    """
    app = create_app(config)
    app.dependency_overrides[api_main.get_llm_manager] = lambda: _FakeLLMManager(
        llm_content
    )
    return TestClient(app)


class TestAPIKeyAuthentication:
    """Test API key authentication enforcement."""

    def test_unauthenticated_request_rejected(self):
        """Requests without an API key get 401 when auth is enabled."""
        client = make_client(make_config(auth_enabled=True))
        response = client.get("/llm/status")
        assert response.status_code == 401
        assert "API key" in response.json()["error"]

    def test_authenticated_request_allowed(self):
        """Requests with the correct API key succeed."""
        client = make_client(make_config(auth_enabled=True))
        response = client.get("/llm/status", headers={"X-API-Key": TEST_API_KEY})
        assert response.status_code == 200
        assert response.json()["status"] == "ready"

    def test_wrong_api_key_rejected(self):
        """Requests with an incorrect API key get 401."""
        client = make_client(make_config(auth_enabled=True))
        response = client.get("/llm/status", headers={"X-API-Key": "not-the-right-key"})
        assert response.status_code == 401

    def test_bearer_token_accepted(self):
        """The API key is also accepted as an Authorization Bearer token."""
        client = make_client(make_config(auth_enabled=True))
        response = client.get(
            "/llm/status", headers={"Authorization": f"Bearer {TEST_API_KEY}"}
        )
        assert response.status_code == 200

    def test_auth_disabled_open(self):
        """When authentication is disabled, no key is required."""
        client = make_client(make_config(auth_enabled=False, api_key=None))
        response = client.get("/llm/status")
        assert response.status_code == 200

    def test_auth_enabled_without_key_fails_startup(self):
        """Enabling auth without configuring a key fails fast at app creation."""
        config = make_config(auth_enabled=True, api_key=None)
        with pytest.raises(RuntimeError, match="no API key is configured"):
            create_app(config)

    def test_health_and_docs_exempt(self):
        """Health check and documentation endpoints stay public."""
        client = make_client(make_config(auth_enabled=True))
        for path in ("/health", "/openapi.json", "/docs", "/redoc"):
            response = client.get(path)
            assert response.status_code == 200, f"{path} should be exempt"

    def test_router_endpoints_require_auth(self):
        """Routers (manuals, knowledge, feedback) are also protected."""
        client = make_client(make_config(auth_enabled=True))
        response = client.get("/api/feedback/metrics")
        assert response.status_code == 401

        response = client.get(
            "/api/feedback/metrics", headers={"X-API-Key": TEST_API_KEY}
        )
        assert response.status_code == 200

    def test_configurable_exempt_path(self):
        """Additional public endpoints can be exempted via configuration."""
        config = make_config(
            auth_enabled=True,
            exempt_paths=AuthenticationConfig().exempt_paths + ["/api/feedback/submit"],
        )
        client = make_client(config)
        response = client.post(
            "/api/feedback/submit",
            json={
                "target_type": "scenario",
                "target_id": "sc_test123",
                "rating": "good",
            },
        )
        assert response.status_code == 201

        # Other feedback endpoints still require auth
        response = client.get("/api/feedback/metrics")
        assert response.status_code == 401


class TestCORSLockdown:
    """Test CORS is locked down to configured origins."""

    def test_cors_defaults_localhost_only(self):
        """By default only configured localhost origins get CORS headers."""
        client = make_client(make_config(auth_enabled=False, api_key=None))
        allowed = client.get("/health", headers={"Origin": "http://localhost:3000"})
        assert (
            allowed.headers.get("access-control-allow-origin")
            == "http://localhost:3000"
        )

        disallowed = client.get(
            "/health", headers={"Origin": "https://evil.example.com"}
        )
        assert "access-control-allow-origin" not in disallowed.headers

    def test_cors_no_credentials_by_default(self):
        """allow_credentials is off unless explicitly configured."""
        client = make_client(make_config(auth_enabled=False, api_key=None))
        response = client.get("/health", headers={"Origin": "http://localhost:3000"})
        assert response.headers.get("access-control-allow-credentials") != "true"

    def test_cors_configured_origins(self):
        """Origins come from the cors configuration section."""
        cors = CORSConfig(origins=["https://app.example.com"], methods=["GET", "POST"])
        client = make_client(make_config(auth_enabled=False, api_key=None, cors=cors))
        allowed = client.get("/health", headers={"Origin": "https://app.example.com"})
        assert (
            allowed.headers.get("access-control-allow-origin")
            == "https://app.example.com"
        )

        disallowed = client.get("/health", headers={"Origin": "http://localhost:3000"})
        assert "access-control-allow-origin" not in disallowed.headers

    def test_cors_no_wildcard(self):
        """Wildcard origins never combine with credentials, even if misconfigured."""
        cors = CORSConfig(origins=["*"])
        client = make_client(make_config(auth_enabled=False, api_key=None, cors=cors))
        response = client.get("/health", headers={"Origin": "https://evil.example.com"})
        assert response.headers.get("access-control-allow-credentials") != "true"


class TestSafetyFilterWiring:
    """Test the ContentFilter is enforced on the LLM generate endpoint."""

    def test_blocked_prompt_returns_403(self):
        """A prompt matching blocked patterns is rejected before the LLM call."""
        client = make_client(make_config(auth_enabled=False, api_key=None))
        response = client.post("/llm/generate", json={"prompt": MALICIOUS_PROMPT})
        assert response.status_code == 403
        assert "safety filter" in response.json()["error"]

    def test_blocked_output_returns_422(self):
        """Generated content matching blocked patterns is not returned."""
        client = make_client(
            make_config(auth_enabled=False, api_key=None), llm_content=MALICIOUS_OUTPUT
        )
        response = client.post("/llm/generate", json={"prompt": SAFE_PROMPT})
        assert response.status_code == 422
        assert "safety filter" in response.json()["error"]

    def test_safe_generation_succeeds(self):
        """Safe prompt and output pass through the filter and return 200."""
        client = make_client(
            make_config(auth_enabled=False, api_key=None), llm_content=SAFE_OUTPUT
        )
        response = client.post("/llm/generate", json={"prompt": SAFE_PROMPT})
        assert response.status_code == 200
        body = response.json()
        assert body["content"] == SAFE_OUTPUT
        assert body["provider_used"] == "mock"
        assert body["tokens_used"] == 42

    def test_blocked_prompt_still_blocked_with_auth_enabled(self):
        """Safety filter applies together with API key auth."""
        client = make_client(make_config(auth_enabled=True))
        unauthenticated = client.post(
            "/llm/generate", json={"prompt": MALICIOUS_PROMPT}
        )
        assert unauthenticated.status_code == 401

        authenticated = client.post(
            "/llm/generate",
            json={"prompt": MALICIOUS_PROMPT},
            headers={"X-API-Key": TEST_API_KEY},
        )
        assert authenticated.status_code == 403
