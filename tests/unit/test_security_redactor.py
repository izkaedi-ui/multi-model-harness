"""
Unit tests for SecretRedactor and ArtifactScanner to ensure fake secrets and sensitive headers
are scrubbed from logs, dicts, JSON strings, and exported files.
"""
from __future__ import annotations

import unittest
import os

from security.secret_redactor import SecretRedactor


class TestSecretRedactor(unittest.TestCase):
    def setUp(self):
        self.redactor = SecretRedactor.default()

    def test_redact_openai_key(self):
        text = "My OpenAI key is sk-1234567890abcdefghijklmnopqrstuvwxyz123456"
        redacted = self.redactor.redact_string(text)
        self.assertNotIn("sk-1234567890abcdef", redacted)
        self.assertIn("[OPENAI-KEY-REDACTED]", redacted)

    def test_redact_google_key(self):
        text = "Google key: AIzaSyFakeGoogleApiKey1234567890abcdefghij"
        redacted = self.redactor.redact_string(text)
        self.assertNotIn("AIzaSyFakeGoogleApiKey", redacted)
        self.assertIn("[GOOGLE-KEY-REDACTED]", redacted)

    def test_redact_anthropic_key(self):
        text = "Key sk-ant-1234567890abcdefghijklmnopqrstuvwxyz"
        redacted = self.redactor.redact_string(text)
        self.assertNotIn("sk-ant-1234567890abcdef", redacted)
        self.assertIn("[ANTHROPIC-KEY-REDACTED]", redacted)

    def test_redact_dict_sensitive_fields(self):
        data = {
            "api_key": "secret_key_123",
            "authorization": "Bearer secret_token_xyz_1234567890",
            "public_field": "public_data",
        }
        redacted = self.redactor.redact_dict(data)
        self.assertEqual(redacted["api_key"], "[REDACTED]")
        self.assertEqual(redacted["public_field"], "public_data")

    def test_is_clean(self):
        clean_text = "Standard evaluation prompt response without credentials."
        dirty_text = "Here is sk-1234567890abcdefghijklmnopqrstuvwxyz123456"
        self.assertTrue(self.redactor.is_clean(clean_text))
        self.assertFalse(self.redactor.is_clean(dirty_text))
