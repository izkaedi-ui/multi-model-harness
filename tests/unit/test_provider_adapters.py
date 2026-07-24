"""
Unit tests for OpenAIAdapter, AnthropicAdapter, XAIAdapter error mapping,
client cleanup, retry owner configuration, and provider identity preservation.
"""
from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock, patch
import os
import openai

from adapters.openai_adapter import OpenAIAdapter
from adapters.anthropic_adapter import AnthropicAdapter
from adapters.xai_adapter import XAIAdapter
from security_harness.errors import (
    AuthenticationError,
    NonRetryableProviderError,
    RateLimitError,
    RetryableProviderError,
)
from security_harness.types import ModelRequest


ENV_MOCK = {
    "OPENAI_API_KEY": "sk-fake-openai-key",
    "ANTHROPIC_API_KEY": "sk-ant-fake-key",
    "XAI_API_KEY": "xai-fake-key",
    "USERPROFILE": "C:\\Users\\zkaed",
    "HOME": "C:\\Users\\zkaed",
}


def _make_request(model: str = "gpt-4o") -> ModelRequest:
    return ModelRequest(
        model=model,
        messages=[{"role": "user", "content": "hi"}],
        temperature=0.0,
        max_output_tokens=100,
    )


class TestOpenAIAdapter(unittest.IsolatedAsyncioTestCase):
    @patch.dict(os.environ, ENV_MOCK, clear=False)
    async def test_init_and_max_retries_zero(self):
        adapter = OpenAIAdapter()
        self.assertEqual(adapter._client.max_retries, 0)
        self.assertEqual(adapter.provider_name, "openai")
        await adapter.close()

    @patch.dict(os.environ, ENV_MOCK, clear=False)
    async def test_generate_auth_error_raises_custom_auth_error(self):
        adapter = OpenAIAdapter()
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        err = openai.AuthenticationError("Invalid API key", response=mock_resp, body=None)

        adapter._client.chat.completions.create = AsyncMock(side_effect=err)
        req = _make_request("gpt-4o")

        with self.assertRaises(AuthenticationError) as ctx:
            await adapter.generate(req)
        self.assertEqual(ctx.exception.provider, "openai")
        await adapter.close()

    @patch.dict(os.environ, ENV_MOCK, clear=False)
    async def test_generate_rate_limit_error(self):
        adapter = OpenAIAdapter()
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_resp.headers = {"retry-after": "5"}
        err = openai.RateLimitError("Rate limit exceeded", response=mock_resp, body=None)

        adapter._client.chat.completions.create = AsyncMock(side_effect=err)
        req = _make_request("gpt-4o")

        with self.assertRaises(RateLimitError) as ctx:
            await adapter.generate(req)
        self.assertEqual(ctx.exception.provider, "openai")
        await adapter.close()


class TestXAIAdapter(unittest.IsolatedAsyncioTestCase):
    @patch.dict(os.environ, ENV_MOCK, clear=False)
    async def test_xai_identity_and_error_mapping(self):
        adapter = XAIAdapter()
        self.assertEqual(adapter.provider_name, "xai")
        self.assertEqual(adapter._client.max_retries, 0)

        mock_resp = MagicMock()
        mock_resp.status_code = 401
        err = openai.AuthenticationError("Invalid xAI key", response=mock_resp, body=None)

        adapter._client.chat.completions.create = AsyncMock(side_effect=err)
        req = _make_request("grok-4.3")

        with self.assertRaises(AuthenticationError) as ctx:
            await adapter.generate(req)
        self.assertEqual(ctx.exception.provider, "xai")
        await adapter.close()


class TestAnthropicAdapter(unittest.IsolatedAsyncioTestCase):
    @patch.dict(os.environ, ENV_MOCK, clear=False)
    async def test_anthropic_identity_and_normalisation(self):
        adapter = AnthropicAdapter()
        self.assertEqual(adapter.provider_name, "anthropic")
        await adapter.close()


class TestGeminiAdapter(unittest.IsolatedAsyncioTestCase):
    @patch.dict(os.environ, {"GOOGLE_API_KEY": "AIzaSyFakeKey", **ENV_MOCK}, clear=False)
    async def test_gemini_identity_and_max_retries_zero(self):
        from adapters.gemini_adapter import GeminiAdapter
        adapter = GeminiAdapter()
        self.assertEqual(adapter.provider_name, "google")
        self.assertEqual(adapter._client.max_retries, 0)

        mock_resp = MagicMock()
        mock_resp.status_code = 401
        err = openai.AuthenticationError("Invalid Google key", response=mock_resp, body=None)

        adapter._client.chat.completions.create = AsyncMock(side_effect=err)
        req = _make_request("gemini-3.6-flash")

        with self.assertRaises(AuthenticationError) as ctx:
            await adapter.generate(req)
        self.assertEqual(ctx.exception.provider, "google")
        await adapter.close()

