"""
Google Gemini adapter — stub.

Install: pip install google-generativeai
Implement: _generate_raw() using the GenerativeModel.generate_content_async() method.

Authentication: GOOGLE_API_KEY environment variable.
"""

from __future__ import annotations

import logging

from adapters.base_adapter import BaseAdapter
from adapters.auth import load_api_key
from security_harness.types import ModelRequest, ModelResponse

log = logging.getLogger(__name__)

PROVIDER = "google"


class GeminiAdapter(BaseAdapter):
    """
    Provider adapter for the Google Gemini API.

    Status: STUB — implement _generate_raw() to enable.

    References:
        https://ai.google.dev/api/python/google/generativeai
    """

    provider_name = PROVIDER

    def __init__(
        self,
        api_key: str | None = None,
        retry_config: dict | None = None,
    ) -> None:
        super().__init__(retry_config=retry_config)
        self._api_key = api_key or load_api_key(PROVIDER, "GOOGLE_API_KEY")
        log.info("GeminiAdapter.init (stub)", extra={"provider": PROVIDER})

    async def _generate_raw(self, request: ModelRequest) -> ModelResponse:
        # TODO: Install google-generativeai and implement.
        # import google.generativeai as genai
        # genai.configure(api_key=self._api_key)
        # model = genai.GenerativeModel(request.model)
        # response = await model.generate_content_async(...)
        raise NotImplementedError(
            "GeminiAdapter is a stub. "
            "Install google-generativeai and implement _generate_raw()."
        )

    async def health_check(self) -> bool:
        log.warning("GeminiAdapter.health_check: stub — returning False")
        return False

    async def close(self) -> None:
        pass
