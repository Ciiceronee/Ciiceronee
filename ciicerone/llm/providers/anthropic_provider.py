"""Anthropic provider implementation for Ciicerone."""

import asyncio
import logging
from typing import Dict, Any, Optional
from datetime import datetime

from ..base import BaseLLMProvider, LLMResponse

logger = logging.getLogger(__name__)


class AnthropicProvider(BaseLLMProvider):
    """Anthropic Claude LLM provider implementation."""

    def __init__(self, config: Dict[str, Any]):
        """Initialize Anthropic provider.

        Args:
            config: Configuration dictionary with Anthropic settings
        """
        super().__init__(config)
        self.api_key = config.get('api_key')
        self.model = config.get('model', 'claude-3-5-sonnet-20241022')
        self.base_url = config.get('base_url', 'https://api.anthropic.com')
        self._client = None

        if not self.api_key:
            raise ValueError("Anthropic API key is required")

    def _get_client(self):
        """Get or create Anthropic client."""
        if self._client is None:
            try:
                import anthropic
                self._client = anthropic.Anthropic(api_key=self.api_key)
            except ImportError:
                raise ImportError(
                    "Anthropic SDK not installed. Install with: pip install anthropic"
                )
        return self._client

    async def generate_content(
        self,
        prompt: str,
        max_tokens: int = 1000,
        temperature: float = 0.7,
        **kwargs
    ) -> LLMResponse:
        """Generate content using Anthropic API.

        Args:
            prompt: The prompt to send to Anthropic
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            **kwargs: Additional parameters

        Returns:
            LLMResponse with generated content
        """
        try:
            client = self._get_client()

            # Build system message
            system_message = kwargs.get('system_message',
                "You are a cybersecurity expert assistant for threat simulation and security training."
            )

            # Make API call using asyncio.to_thread for sync client
            response = await asyncio.to_thread(
                client.messages.create,
                model=self.model,
                max_tokens=max_tokens,
                system=system_message,
                messages=[{"role": "user", "content": prompt}]
            )

            content = response.content[0].text

            llm_response = LLMResponse(
                content=content,
                provider="anthropic",
                model=self.model,
            )
            llm_response.timestamp = datetime.utcnow()
            llm_response.metadata = {
                "temperature": temperature,
                "max_tokens": max_tokens,
                "prompt_length": len(prompt),
                "stop_reason": response.stop_reason,
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
                "tokens_used": response.usage.input_tokens + response.usage.output_tokens,
            }
            llm_response.is_real_ai = True
            llm_response.usage = {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens
            }

            logger.info(f"Anthropic API response received: {len(content)} chars")
            return llm_response

        except ImportError as e:
            logger.error(f"Anthropic SDK not available: {e}")
            raise
        except Exception as e:
            logger.error(f"Anthropic content generation failed: {e}")
            raise

    async def validate_connection(self) -> bool:
        """Validate connection to Anthropic API."""
        try:
            client = self._get_client()

            # Make a minimal API call to validate
            response = await asyncio.to_thread(
                client.messages.create,
                model=self.model,
                max_tokens=10,
                messages=[{"role": "user", "content": "test"}]
            )

            return response.content[0].text is not None

        except Exception as e:
            logger.error(f"Anthropic connection validation failed: {e}")
            return False

    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the current model."""
        return {
            "provider": "anthropic",
            "model": self.model,
            "base_url": self.base_url,
            "configured": bool(self.api_key)
        }
