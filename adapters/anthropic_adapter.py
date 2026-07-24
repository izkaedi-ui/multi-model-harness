"""
Anthropic adapter — fully implemented.

Supports:
  - Messages API (claude-opus-*, claude-sonnet-*, claude-haiku-*)
  - Tool / function calling
  - System messages
  - Content block normalisation (text + tool_use blocks)

Authentication: ANTHROPIC_API_KEY environment variable.
"""

from __future__ import annotations

import logging
from typing import Any

import anthropic
from anthropic.types import Message, TextBlock, ToolUseBlock

from adapters.auth import load_api_key
from adapters.base_adapter import BaseAdapter
from security_harness.clock import monotonic_ms
from security_harness.errors import (
    AuthenticationError,
    NonRetryableProviderError,
    RateLimitError,
    RetryableProviderError,
)
from security_harness.types import ModelRequest, ModelResponse, TokenUsage

log = logging.getLogger(__name__)

PROVIDER = "anthropic"
_ANTHROPIC_VERSION = "2023-06-01"


class AnthropicAdapter(BaseAdapter):
    """
    Provider adapter for the Anthropic Messages API.

    Maps Claude's content-block response format (TextBlock, ToolUseBlock)
    to the normalised ModelResponse interface.
    """

    provider_name = PROVIDER

    def __init__(
        self,
        api_key: str | None = None,
        retry_config: dict | None = None,
    ) -> None:
        super().__init__(retry_config=retry_config)
        key = api_key or load_api_key(PROVIDER, "ANTHROPIC_API_KEY")
        self._client = anthropic.AsyncAnthropic(api_key=key)
        log.info("AnthropicAdapter.init", extra={"provider": PROVIDER})

    # ------------------------------------------------------------------
    # Core implementation
    # ------------------------------------------------------------------

    async def _generate_raw(self, request: ModelRequest) -> ModelResponse:
        """Call the Anthropic Messages API and return a normalised ModelResponse."""
        t0 = monotonic_ms()

        kwargs: dict[str, Any] = {
            "model": request.model,
            "messages": list(request.messages),
            "temperature": request.temperature,
            "max_tokens": request.max_output_tokens,
        }

        if request.system_prompt:
            kwargs["system"] = request.system_prompt

        if request.tools:
            kwargs["tools"] = self._convert_tools(list(request.tools))

        try:
            message: Message = await self._client.messages.create(**kwargs)
        except anthropic.AuthenticationError as exc:
            raise AuthenticationError(PROVIDER) from exc
        except anthropic.RateLimitError as exc:
            raise RateLimitError(PROVIDER) from exc
        except anthropic.APIStatusError as exc:
            if exc.status_code in (500, 502, 503, 504, 529):
                raise RetryableProviderError(
                    PROVIDER, exc.status_code, str(exc)
                ) from exc
            raise NonRetryableProviderError(
                PROVIDER, exc.status_code, str(exc)
            ) from exc
        except anthropic.APIConnectionError as exc:
            raise RetryableProviderError(PROVIDER, None, str(exc)) from exc

        latency_ms = monotonic_ms() - t0
        return self._normalise(message, latency_ms)

    # ------------------------------------------------------------------
    # Normalisation helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _normalise(message: Message, latency_ms: int) -> ModelResponse:
        text_parts: list[str] = []
        tool_calls: list[dict[str, Any]] = []

        for block in message.content:
            if isinstance(block, TextBlock):
                text_parts.append(block.text)
            elif isinstance(block, ToolUseBlock):
                tool_calls.append(
                    {
                        "id": block.id,
                        "type": "function",
                        "function": {
                            "name": block.name,
                            "arguments": block.input,
                        },
                    }
                )

        # Map Anthropic stop_reason to a normalised finish_reason
        finish_reason = _map_stop_reason(message.stop_reason)

        usage = TokenUsage(
            input_tokens=message.usage.input_tokens,
            output_tokens=message.usage.output_tokens,
            total_tokens=message.usage.input_tokens + message.usage.output_tokens,
        )

        return ModelResponse(
            provider=PROVIDER,
            model=message.model,
            text="\n".join(text_parts),
            finish_reason=finish_reason,
            tool_calls=tuple(tool_calls),
            usage=usage,
            latency_ms=latency_ms,
            raw_response={
                "id": message.id,
                "type": message.type,
                "role": message.role,
                "content": [b.model_dump() for b in message.content],
                "model": message.model,
                "stop_reason": message.stop_reason,
                "stop_sequence": message.stop_sequence,
                "usage": message.usage.model_dump(),
            },
        )

    @staticmethod
    def _convert_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Convert OpenAI-style tool definitions to Anthropic format.

        OpenAI: {"type": "function", "function": {"name": ..., "description": ..., "parameters": ...}}
        Anthropic: {"name": ..., "description": ..., "input_schema": ...}
        """
        converted = []
        for tool in tools:
            fn = tool.get("function", tool)
            converted.append(
                {
                    "name": fn["name"],
                    "description": fn.get("description", ""),
                    "input_schema": fn.get("parameters", {"type": "object", "properties": {}}),
                }
            )
        return converted

    # ------------------------------------------------------------------
    # Health check
    # ------------------------------------------------------------------

    async def health_check(self) -> bool:
        """Send a minimal single-token request to verify credentials."""
        try:
            await self._client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=1,
                messages=[{"role": "user", "content": "hi"}],
            )
            return True
        except anthropic.AuthenticationError:
            log.error("health_check.auth_failure", extra={"provider": PROVIDER})
            return False
        except Exception as exc:
            log.warning(
                "health_check.failure",
                extra={"provider": PROVIDER, "error": str(exc)},
            )
            return False

    async def close(self) -> None:
        await self._client.close()
        log.info("AnthropicAdapter.closed", extra={"provider": PROVIDER})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _map_stop_reason(stop_reason: str | None) -> str | None:
    """Map Anthropic stop_reason values to normalised finish_reason strings."""
    mapping = {
        "end_turn": "stop",
        "max_tokens": "length",
        "stop_sequence": "stop",
        "tool_use": "tool_calls",
    }
    if stop_reason is None:
        return None
    return mapping.get(stop_reason, stop_reason)
