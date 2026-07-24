"""
API key loading — strict environment-variable-only policy.

Rules enforced here:
1. Keys are loaded only from environment variables.
2. Values are never logged.
3. Empty strings are treated as missing.
4. The calling code receives a MissingApiKeyError, never a raw KeyError.
"""

from __future__ import annotations

import os
from dotenv import load_dotenv

from security_harness.errors import MissingApiKeyError

# Load .env file automatically if present
load_dotenv()



def load_api_key(provider: str, env_var: str) -> str:
    """
    Load an API key from an environment variable.

    Args:
        provider: Human-readable provider name (e.g., "openai"). Used in error messages only.
        env_var:  Name of the environment variable (e.g., "OPENAI_API_KEY").

    Returns:
        The API key value.

    Raises:
        MissingApiKeyError: If the environment variable is unset or empty.
    """
    value = os.environ.get(env_var, "").strip()
    if not value:
        raise MissingApiKeyError(provider=provider, env_var=env_var)
    return value


def has_api_key(env_var: str) -> bool:
    """Return True if the environment variable is set and non-empty."""
    return bool(os.environ.get(env_var, "").strip())


def available_providers() -> list[str]:
    """
    Return a list of provider names whose API keys are currently set.

    Useful for skipping providers that have no credentials configured.
    """
    checks = {
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "google": "GOOGLE_API_KEY",
        "xai": "XAI_API_KEY",
    }
    return [name for name, var in checks.items() if has_api_key(var)]
