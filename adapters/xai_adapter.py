"""
xAI / Grok adapter — stub.

xAI exposes an OpenAI-compatible API, so this adapter can be implemented
by subclassing OpenAIAdapter with a custom base_url.

Authentication: XAI_API_KEY environment variable.
"""

from __future__ import annotations

import logging

from adapters.base_adapter import BaseAdapter
from adapters.auth import load_api_key
from security_harness.types import ModelRequest, ModelResponse

log = logging.getLogger(__name__)

PROVIDER = "xai"
_XAI_BASE_URL = "https://api.x.ai/v1"


class XAIAdapter(BaseAdapter):
    """
    Provider adapter for the xAI Grok API.

    Status: STUB — implement _generate_raw() to enable.

    Implementation hint:
        xAI uses an OpenAI-compatible API. The simplest implementation is:

            from adapters.openai_adapter import OpenAIAdapter
            import openai

            class XAIAdapter(OpenAIAdapter):
                provider_name = "xai"

                def __init__(self, api_key=None, retry_config=None):
                    super().__init__(api_key=api_key, retry_config=retry_config)
                    key = api_key or load_api_key("xai", "XAI_API_KEY")
                    self._client = openai.AsyncOpenAI(
                        api_key=key,
                        base_url="https://api.x.ai/v1",
                    )

    References:
        https://docs.x.ai/docs
    """

    provider_name = PROVIDER

    def __init__(
        self,
        api_key: str | None = None,
        retry_config: dict | None = None,
    ) -> None:
        super().__init__(retry_config=retry_config)
        self._api_key = api_key or load_api_key(PROVIDER, "XAI_API_KEY")
        log.info("XAIAdapter.init (stub)", extra={"provider": PROVIDER})

    async def _generate_raw(self, request: ModelRequest) -> ModelResponse:
        # TODO: Implement using openai.AsyncOpenAI(base_url=_XAI_BASE_URL)
        raise NotImplementedError(
            "XAIAdapter is a stub. "
            "See the docstring for the recommended OpenAI-compatible implementation."
        )

    async def health_check(self) -> bool:
        log.warning("XAIAdapter.health_check: stub — returning False")
        return False

    async def close(self) -> None:
        pass
