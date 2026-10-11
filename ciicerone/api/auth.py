"""API key authentication middleware for the Ciicerone API.

Enforces a single shared API key (server-to-server style authentication) on
all HTTP requests unless the path is explicitly exempted (health checks, API
documentation) or authentication is disabled in the configuration.

The key is read from the configured header (default ``X-API-Key``) or from an
``Authorization: Bearer <key>`` header, and is compared in constant time.
"""

import hmac
import logging
from datetime import datetime
from typing import Iterable, Optional

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

logger = logging.getLogger(__name__)


class APIKeyAuthMiddleware:
    """Pure-ASGI API key authentication middleware.

    When ``enabled`` is False every request passes through untouched, which
    keeps the default local-development experience open as before.
    """

    def __init__(
        self,
        app: ASGIApp,
        api_key: Optional[str] = None,
        enabled: bool = False,
        exempt_paths: Iterable[str] = (),
        header_name: str = "X-API-Key",
    ):
        self.app = app
        self.api_key = api_key
        self.enabled = enabled
        self.exempt_paths = tuple(exempt_paths)
        self.header_name = header_name.lower()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not self.enabled:
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if self._is_exempt(path):
            await self.app(scope, receive, send)
            return

        provided_key = self._extract_key(scope)
        if provided_key is None or not self._key_matches(provided_key):
            logger.warning(f"Rejected unauthenticated request to {path}")
            response = JSONResponse(
                status_code=401,
                content={
                    "error": "Invalid or missing API key",
                    "status_code": 401,
                    "timestamp": datetime.utcnow().isoformat(),
                },
            )
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)

    def _is_exempt(self, path: str) -> bool:
        """Check if a path is exempt from authentication (exact match)."""
        return path in self.exempt_paths

    def _extract_key(self, scope: Scope) -> Optional[str]:
        """Extract the API key from the configured header or Bearer token."""
        for name, value in scope.get("headers", []):
            name_str = name.decode("latin-1").lower()
            value_str = value.decode("latin-1")
            if name_str == self.header_name:
                return value_str.strip()
            if name_str == "authorization" and value_str.lower().startswith("bearer "):
                return value_str[7:].strip()
        return None

    def _key_matches(self, provided_key: str) -> bool:
        """Constant-time comparison of the provided key against the configured key."""
        if not self.api_key:
            return False
        return hmac.compare_digest(provided_key.encode(), self.api_key.encode())
