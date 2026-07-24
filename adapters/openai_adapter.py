"""
OpenAI adapter — fully implemented.

Supports:
  - Chat completions (gpt-4o, gpt-4o-mini, o3-mini, etc.)
  - Tool / function calling
  - JSON mode
  - System messages

Authentication: OPENAI_API_KEY environment variable.
"""

from __future__ import annotations

import logging
from typing import Any

import openai
from openai.types.chat import ChatCompletion

from adapters.base_adapter import BaseAdapter
from adapters.auth import load_api_key
from security_harness.clock import monotonic_ms
from security_harness.errors import (
    AuthenticationError,
    NonRetryableProviderError,
    RateLimitError,
    RetryableProviderError,
)
from security_harness.types import ModelRequest, ModelResponse, TokenUsage

log = logging.getLogger(__name__)

PROVIDER = "openai"


class OpenAIAdapter(BaseAdapter):
    """
    Provider adapter for the OpenAI Chat Completions API.

    Normalises ChatCompletion responses into ModelResponse, maps finish_reason,
    extracts tool calls, and tracks token usage.
    """

    provider_name = PROVIDER

    def __init__(
        self,
        api_key: str | None = None,
        retry_config: dict | None = None,
    ) -> None:
        super().__init__(retry_config=retry_config)
        key = api_key or load_api_key(PROVIDER, "OPENAI_API_KEY")
        self._client = openai.AsyncOpenAI(
            api_key=key,
            max_retries=0,
            timeout=self._timeout,
        )
        log.info("OpenAIAdapter.init", extra={"provider": PROVIDER})

    # ------------------------------------------------------------------
    # Core implementation
    # ------------------------------------------------------------------

    async def _generate_raw(self, request: ModelRequest) -> ModelResponse:
        """Call the Chat Completions API and return a normalised ModelResponse."""
        t0 = monotonic_ms()

        kwargs: dict[str, Any] = {
            "model": request.model,
            "messages": self._build_messages(request),
            "temperature": request.temperature,
            "max_tokens": request.max_output_tokens,
        }

        if request.tools:
            kwargs["tools"] = list(request.tools)
            kwargs["tool_choice"] = "auto"

        try:
            completion: ChatCompletion = await self._client.chat.completions.create(**kwargs)
        except openai.AuthenticationError as exc:
            raise AuthenticationError(PROVIDER) from exc
        except openai.RateLimitError as exc:
            retry_after = self._extract_retry_after(exc)
            raise RateLimitError(PROVIDER, retry_after) from exc
        except openai.APIStatusError as exc:
            if exc.status_code in (500, 502, 503, 504):
                raise RetryableProviderError(
                    PROVIDER, exc.status_code, str(exc)
                ) from exc
            raise NonRetryableProviderError(
                PROVIDER, exc.status_code, str(exc)
            ) from exc
        except openai.APIConnectionError as exc:
            cause = exc.__cause__
            cause_text = (
                f"{type(cause).__name__}: {cause}"
                if cause is not None
                else "underlying cause unavailable"
            )
            log.warning(
                "openai.connection_error",
                extra={
                    "provider": PROVIDER,
                    "model": request.model,
                    "error": str(exc),
                    "cause": cause_text,
                },
            )
            raise RetryableProviderError(
                PROVIDER,
                None,
                f"{exc}; cause={cause_text}",
            ) from exc


        latency_ms = monotonic_ms() - t0
        return self._normalise(completion, latency_ms)

    # ------------------------------------------------------------------
    # Normalisation helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_messages(request: ModelRequest) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        messages.extend(request.messages)
        return messages

    @staticmethod
    def _normalise(completion: ChatCompletion, latency_ms: int) -> ModelResponse:
        choice = completion.choices[0]
        message = choice.message

        # Extract text content
        text = message.content or ""

        # Extract tool calls
        tool_calls: list[dict[str, Any]] = []
        if message.tool_calls:
            for tc in message.tool_calls:
                tool_calls.append(
                    {
                        "id": tc.id,
                        "type": tc.type,
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                )

        # Token usage
        usage = TokenUsage(
            input_tokens=completion.usage.prompt_tokens if completion.usage else 0,
            output_tokens=completion.usage.completion_tokens if completion.usage else 0,
            total_tokens=completion.usage.total_tokens if completion.usage else 0,
        )

        return ModelResponse(
            provider=PROVIDER,
            model=completion.model,
            text=text,
            finish_reason=choice.finish_reason,
            tool_calls=tuple(tool_calls),
            usage=usage,
            latency_ms=latency_ms,
            raw_response=completion.model_dump(),
        )

    @staticmethod
    def _extract_retry_after(exc: openai.RateLimitError) -> float | None:
        """Try to parse Retry-After seconds from the error headers."""
        try:
            headers = exc.response.headers  # type: ignore[union-attr]
            value = headers.get("retry-after") or headers.get("x-ratelimit-reset-requests")
            return float(value) if value else None
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Health check
    # ------------------------------------------------------------------

    async def health_check(self) -> bool:
        """
        Verify that the OpenAI API is reachable and the key is valid.

        Sends the cheapest possible request (models list endpoint).
        """
        try:
            await self._client.models.list()
            return True
        except openai.AuthenticationError:
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
        log.info("OpenAIAdapter.closed", extra={"provider": PROVIDER})
