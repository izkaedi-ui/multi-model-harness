"""
Unit and mock integration tests for GeminiAdapter and Google/Gemini alias normalization.
"""
from __future__ import annotations

import os
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from adapters.auth import available_providers, has_api_key, load_api_key
from adapters.gemini_adapter import GeminiAdapter
from security_harness.errors import MissingApiKeyError
from security_harness.types import ModelRequest


class TestGeminiAuth(unittest.TestCase):
    @patch.dict(os.environ, {"GOOGLE_API_KEY": "AIzaSyFakeGoogleKey"}, clear=True)
    def test_google_api_key_primary(self):
        key = load_api_key("google", ["GOOGLE_API_KEY", "GEMINI_API_KEY"])
        self.assertEqual(key, "AIzaSyFakeGoogleKey")
        self.assertTrue(has_api_key(["GOOGLE_API_KEY", "GEMINI_API_KEY"]))
        self.assertIn("google", available_providers())

    @patch.dict(os.environ, {"GEMINI_API_KEY": "AIzaSyFakeGeminiKey"}, clear=True)
    def test_gemini_api_key_fallback(self):
        key = load_api_key("google", ["GOOGLE_API_KEY", "GEMINI_API_KEY"])
        self.assertEqual(key, "AIzaSyFakeGeminiKey")
        self.assertTrue(has_api_key(["GOOGLE_API_KEY", "GEMINI_API_KEY"]))
        self.assertIn("google", available_providers())

    @patch.dict(os.environ, {"GOOGLE_API_KEY": "Primary", "GEMINI_API_KEY": "Fallback"}, clear=True)
    def test_both_keys_precedence(self):
        key = load_api_key("google", ["GOOGLE_API_KEY", "GEMINI_API_KEY"])
        self.assertEqual(key, "Primary")

    @patch.dict(os.environ, {}, clear=True)
    def test_neither_key_raises(self):
        with self.assertRaises(MissingApiKeyError):
            load_api_key("google", ["GOOGLE_API_KEY", "GEMINI_API_KEY"])
        self.assertFalse(has_api_key(["GOOGLE_API_KEY", "GEMINI_API_KEY"]))
        self.assertNotIn("google", available_providers())


class TestGeminiTextExtractor(unittest.TestCase):
    def test_extract_string(self):
        self.assertEqual(GeminiAdapter._extract_text("Hello World"), "Hello World")

    def test_extract_none(self):
        self.assertEqual(GeminiAdapter._extract_text(None), "")

    def test_extract_structured_list(self):
        content = [
            {"type": "text", "text": "Part 1 "},
            {"type": "text", "text": "Part 2"},
        ]
        self.assertEqual(GeminiAdapter._extract_text(content), "Part 1 Part 2")

    def test_extract_mixed_list(self):
        content = ["Direct string ", {"text": "Dict string"}]
        self.assertEqual(GeminiAdapter._extract_text(content), "Direct string Dict string")

    def test_extract_unexpected_structure(self):
        self.assertEqual(GeminiAdapter._extract_text(12345), "")


class TestGeminiMockIntegration(unittest.IsolatedAsyncioTestCase):
    @patch.dict(os.environ, {"GOOGLE_API_KEY": "AIzaSyTestKey"})
    async def test_mock_chat_completion_success(self):
        adapter = GeminiAdapter()

        mock_completion = MagicMock()
        mock_completion.model = "gemini-3.6-flash"
        mock_choice = MagicMock()
        mock_choice.finish_reason = "stop"
        mock_choice.message.content = "GEMINI_OK"
        mock_choice.message.tool_calls = None
        mock_completion.choices = [mock_choice]
        mock_completion.usage.prompt_tokens = 5
        mock_completion.usage.completion_tokens = 10
        mock_completion.usage.total_tokens = 15
        mock_completion.model_dump.return_value = {"id": "gen-123"}

        adapter._client.chat.completions.create = AsyncMock(return_value=mock_completion)

        req = ModelRequest(
            model="gemini-3.6-flash",
            messages=[{"role": "user", "content": "Test"}],
            temperature=0.0,
            max_output_tokens=100,
        )

        resp = await adapter.generate(req)
        self.assertEqual(resp.provider, "google")
        self.assertEqual(resp.model, "gemini-3.6-flash")
        self.assertEqual(resp.text, "GEMINI_OK")
        self.assertEqual(resp.usage.input_tokens, 5)
        self.assertEqual(resp.usage.output_tokens, 10)
        self.assertEqual(resp.usage.total_tokens, 15)

        await adapter.close()


if __name__ == "__main__":
    unittest.main()
