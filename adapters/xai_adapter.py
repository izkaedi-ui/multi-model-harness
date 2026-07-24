"""
xAI / Grok adapter — stub.

xAI exposes an OpenAI-compatible API, so this adapter can be implemented
by subclassing OpenAIAdapter with a custom base_url.

Authentication: XAI_API_KEY environment variable.
"""

from __future__ import annotations

import logging

import openai

from adapters.auth import load_api_key
from adapters.openai_adapter import OpenAIAdapter

log = logging.getLogger(__name__)

PROVIDER = "xai"
_XAI_BASE_URL = "https://api.x.ai/v1"


class XAIAdapter(OpenAIAdapter):
    """
    Provider adapter for the xAI Grok API.

    Leverages xAI's OpenAI-compatible endpoint interface.
    """

    provider_name = PROVIDER

    def __init__(
        self,
        api_key: str | None = None,
        retry_config: dict | None = None,
    ) -> None:
        super().__init__(api_key=api_key, retry_config=retry_config)
        key = api_key or load_api_key(PROVIDER, "XAI_API_KEY")
        self._client = openai.AsyncOpenAI(
            api_key=key,
            base_url=_XAI_BASE_URL,
            max_retries=0,
            timeout=self._timeout,
        )
        log.info("XAIAdapter.init", extra={"provider": PROVIDER, "base_url": _XAI_BASE_URL})


    async def close(self) -> None:
        pass
