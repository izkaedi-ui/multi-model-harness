"""
Exception hierarchy for the security test harness.

Design rules:
- HarnessError is the base for all harness-specific exceptions.
- Retryable vs. non-retryable distinction is captured in the type, not a flag.
- Never catch bare Exception at module level; always catch specific subclasses.
"""

from __future__ import annotations


class HarnessError(Exception):
    """Base class for all harness-specific exceptions."""


# ---------------------------------------------------------------------------
# Configuration errors
# ---------------------------------------------------------------------------


class ConfigurationError(HarnessError):
    """Raised when a required configuration value is missing or invalid."""


class MissingApiKeyError(ConfigurationError):
    """Raised when a required API key is not set in the environment."""

    def __init__(self, provider: str, env_var: str) -> None:
        self.provider = provider
        self.env_var = env_var
        super().__init__(
            f"API key for provider {provider!r} not found. "
            f"Set the {env_var!r} environment variable."
        )


class InvalidConfigurationError(ConfigurationError):
    """Raised when a config file is present but its values fail validation."""

    def __init__(self, file: str, detail: str) -> None:
        self.file = file
        self.detail = detail
        super().__init__(f"Invalid configuration in {file!r}: {detail}")


# ---------------------------------------------------------------------------
# Budget errors
# ---------------------------------------------------------------------------


class BudgetExceeded(HarnessError):
    """
    Raised before dispatching a request that would exceed a spending cap.

    This is a hard stop — the request is never sent.
    """

    def __init__(
        self,
        provider: str,
        estimated_cost_usd: float,
        cap_usd: float,
        current_spend_usd: float,
    ) -> None:
        self.provider = provider
        self.estimated_cost_usd = estimated_cost_usd
        self.cap_usd = cap_usd
        self.current_spend_usd = current_spend_usd
        super().__init__(
            f"Budget cap exceeded for provider {provider!r}. "
            f"Estimated cost ${estimated_cost_usd:.4f}, "
            f"current spend ${current_spend_usd:.4f}, "
            f"cap ${cap_usd:.4f}."
        )


class GlobalBudgetExceeded(BudgetExceeded):
    """Raised when the global (cross-provider) budget cap would be exceeded."""


# ---------------------------------------------------------------------------
# Provider / adapter errors
# ---------------------------------------------------------------------------


class ProviderError(HarnessError):
    """Base class for errors originating from provider APIs."""

    def __init__(
        self,
        provider: str,
        status_code: int | None,
        message: str,
    ) -> None:
        self.provider = provider
        self.status_code = status_code
        super().__init__(
            f"Provider {provider!r} error "
            f"(HTTP {status_code}): {message}"
        )


class RetryableProviderError(ProviderError):
    """
    A transient provider error that may succeed on retry.

    Examples: HTTP 429, 503, connection reset.
    """


class NonRetryableProviderError(ProviderError):
    """
    A definitive provider error that will not improve on retry.

    Examples: HTTP 400, 401, 403, invalid model name.
    """


class ProviderTimeoutError(RetryableProviderError):
    """Request exceeded the configured per-request timeout."""

    def __init__(self, provider: str, timeout_seconds: float) -> None:
        self.timeout_seconds = timeout_seconds
        super().__init__(
            provider=provider,
            status_code=408,
            message=f"Request timed out after {timeout_seconds:.1f}s",
        )


class RateLimitError(RetryableProviderError):
    """HTTP 429 — rate limit exceeded."""

    def __init__(self, provider: str, retry_after_seconds: float | None = None) -> None:
        self.retry_after_seconds = retry_after_seconds
        super().__init__(
            provider=provider,
            status_code=429,
            message=(
                f"Rate limit exceeded"
                + (f"; retry after {retry_after_seconds:.1f}s" if retry_after_seconds else "")
            ),
        )


class AuthenticationError(NonRetryableProviderError):
    """HTTP 401 — invalid or missing API key."""

    def __init__(self, provider: str) -> None:
        super().__init__(
            provider=provider,
            status_code=401,
            message="Authentication failed. Check your API key.",
        )


# ---------------------------------------------------------------------------
# Test case / schema errors
# ---------------------------------------------------------------------------


class TestCaseError(HarnessError):
    """Raised when a test case file fails schema validation."""

    def __init__(self, case_id: str, detail: str) -> None:
        self.case_id = case_id
        super().__init__(f"Test case {case_id!r} is invalid: {detail}")


class EvaluationError(HarnessError):
    """Raised when an evaluator encounters an unexpected error."""

    def __init__(self, evaluator: str, case_id: str, detail: str) -> None:
        self.evaluator = evaluator
        self.case_id = case_id
        super().__init__(
            f"Evaluator {evaluator!r} failed on case {case_id!r}: {detail}"
        )


# ---------------------------------------------------------------------------
# Database errors
# ---------------------------------------------------------------------------


class DatabaseError(HarnessError):
    """Base class for database-layer errors."""


class MigrationError(DatabaseError):
    """Raised when a database migration fails."""

    def __init__(self, migration: str, detail: str) -> None:
        self.migration = migration
        super().__init__(f"Migration {migration!r} failed: {detail}")


# ---------------------------------------------------------------------------
# Security / redaction errors
# ---------------------------------------------------------------------------


class RedactionError(HarnessError):
    """Raised when the redactor detects an unresolvable secret pattern."""


class SecretLeakDetected(HarnessError):
    """
    Raised when the artifact scanner finds a potential secret in an output file.

    The file should be quarantined and not exported.
    """

    def __init__(self, path: str, pattern: str) -> None:
        self.path = path
        self.pattern = pattern
        super().__init__(
            f"Potential secret detected in {path!r} matching pattern {pattern!r}. "
            "File quarantined — do not export."
        )
