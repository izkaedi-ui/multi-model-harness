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



def load_api_key(provider: str, env_var: str | list[str]) -> str:
    """
    Load an API key from environment variable(s).

    Args:
        provider: Human-readable provider name (e.g., "openai"). Used in error messages only.
        env_var:  Single env var name or ordered list of fallback env var names.

    Returns:
        The API key value.

    Raises:
        MissingApiKeyError: If no specified environment variable is set or non-empty.
    """
    vars_to_check = [env_var] if isinstance(env_var, str) else env_var
    for var in vars_to_check:
        value = os.environ.get(var, "").strip()
        if value:
            return value
    raise MissingApiKeyError(provider=provider, env_var=" / ".join(vars_to_check))


def has_api_key(env_var: str | list[str]) -> bool:
    """Return True if any of the specified environment variables is set and non-empty."""
    vars_to_check = [env_var] if isinstance(env_var, str) else env_var
    return any(bool(os.environ.get(v, "").strip()) for v in vars_to_check)


def available_providers() -> list[str]:
    """
    Return a list of provider names whose API keys are currently set.

    Useful for skipping providers that have no credentials configured.
    """
    checks: dict[str, str | list[str]] = {
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "google": ["GOOGLE_API_KEY", "GEMINI_API_KEY"],
        "xai": "XAI_API_KEY",
    }
    return [name for name, var in checks.items() if has_api_key(var)]

