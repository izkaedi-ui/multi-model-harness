"""
Google Gemini adapter using the Gemini OpenAI-compatible endpoint.

Authentication:
    GOOGLE_API_KEY or GEMINI_API_KEY

Endpoint:
    https://generativelanguage.googleapis.com/v1beta/openai/
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

PROVIDER = "google"
BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"


class GeminiAdapter(BaseAdapter):
    """Provider adapter for Gemini through Google's OpenAI-compatible API."""

    provider_name = PROVIDER

    def __init__(
        self,
        api_key: str | None = None,
        retry_config: dict | None = None,
    ) -> None:
        super().__init__(retry_config=retry_config)

        key = api_key or load_api_key(PROVIDER, ["GOOGLE_API_KEY", "GEMINI_API_KEY"])


        self._client = openai.AsyncOpenAI(
            api_key=key,
            base_url=BASE_URL,
            max_retries=0,  # BaseAdapter is the single retry owner.
            timeout=self._timeout,
        )

        log.info(
            "GeminiAdapter.init",
            extra={"provider": PROVIDER, "base_url": BASE_URL},
        )

    async def _generate_raw(self, request: ModelRequest) -> ModelResponse:
        """Generate one normalized Gemini response."""
        started_ms = monotonic_ms()

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
            completion: ChatCompletion = (
                await self._client.chat.completions.create(**kwargs)
            )
        except openai.AuthenticationError as exc:
            raise AuthenticationError(PROVIDER) from exc
        except openai.RateLimitError as exc:
            raise RateLimitError(
                PROVIDER,
                self._extract_retry_after(exc),
            ) from exc
        except openai.APIStatusError as exc:
            if exc.status_code in (408, 429, 500, 502, 503, 504):
                raise RetryableProviderError(
                    PROVIDER,
                    exc.status_code,
                    str(exc),
                ) from exc

            raise NonRetryableProviderError(
                PROVIDER,
                exc.status_code,
                str(exc),
            ) from exc
        except openai.APIConnectionError as exc:
            cause = exc.__cause__
            cause_text = (
                f"{type(cause).__name__}: {cause}"
                if cause is not None
                else "underlying cause unavailable"
            )

            raise RetryableProviderError(
                PROVIDER,
                None,
                f"{exc}; cause={cause_text}",
            ) from exc

        latency_ms = monotonic_ms() - started_ms
        return self._normalise(completion, latency_ms)

    @staticmethod
    def _build_messages(request: ModelRequest) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = []

        if request.system_prompt:
            messages.append(
                {
                    "role": "system",
                    "content": request.system_prompt,
                }
            )

        messages.extend(request.messages)
        return messages

    @staticmethod
    def _normalise(
        completion: ChatCompletion,
        latency_ms: int,
    ) -> ModelResponse:
        if not completion.choices:
            raise NonRetryableProviderError(
                PROVIDER,
                None,
                "Gemini returned no completion choices.",
            )

        choice = completion.choices[0]
        message = choice.message

        tool_calls: list[dict[str, Any]] = []

        if message.tool_calls:
            for tool_call in message.tool_calls:
                tool_calls.append(
                    {
                        "id": tool_call.id,
                        "type": tool_call.type,
                        "function": {
                            "name": tool_call.function.name,
                            "arguments": tool_call.function.arguments,
                        },
                    }
                )

        usage = TokenUsage(
            input_tokens=(
                completion.usage.prompt_tokens
                if completion.usage
                else 0
            ),
            output_tokens=(
                completion.usage.completion_tokens
                if completion.usage
                else 0
            ),
            total_tokens=(
                completion.usage.total_tokens
                if completion.usage
                else 0
            ),
        )

        text = GeminiAdapter._extract_text(message.content)


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
    def _extract_text(content: object) -> str:
        """Extract clean text content from string, None, or structured content lists."""
        if content is None:
            return ""
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict) and "text" in item:
                    parts.append(str(item["text"]))
            return "".join(parts)
        return ""


    @staticmethod
    def _extract_retry_after(
        exc: openai.RateLimitError,
    ) -> float | None:
        try:
            headers = exc.response.headers
            value = (
                headers.get("retry-after")
                or headers.get("x-ratelimit-reset-requests")
            )
            return float(value) if value else None
        except Exception:
            return None

    async def health_check(self) -> bool:
        """Verify Gemini connectivity and authentication."""
        try:
            await self._client.models.list()
            return True
        except openai.AuthenticationError:
            log.error(
                "health_check.auth_failure",
                extra={"provider": PROVIDER},
            )
            return False
        except Exception as exc:
            log.warning(
                "health_check.failure",
                extra={
                    "provider": PROVIDER,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                },
            )
            return False

    async def close(self) -> None:
        await self._client.close()
        log.info(
            "GeminiAdapter.closed",
            extra={"provider": PROVIDER},
        )
