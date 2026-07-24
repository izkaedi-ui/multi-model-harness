"""
Artifact scanner — scans generated files for accidental secret leakage
before they are exported or shared.
"""
from __future__ import annotations
import pathlib
from security_harness.errors import SecretLeakDetected
from security_harness.security.secret_redactor import SecretRedactor  # type: ignore[import]

def scan_artifact(path: pathlib.Path, redactor: SecretRedactor | None = None) -> None:
    """
    Scan a file for potential secrets. Raises SecretLeakDetected if found.

    Args:
        path:     Path to the file to scan.
        redactor: Optional redactor; loads default if None.
    """
    if redactor is None:
        redactor = SecretRedactor.default()
    text = path.read_text(encoding="utf-8", errors="replace")
    for pat in redactor._patterns:
        m = pat.regex.search(text)
        if m:
            raise SecretLeakDetected(path=str(path), pattern=pat.regex.pattern)


def scan_directory(directory: pathlib.Path, extensions: list[str] | None = None) -> list[str]:
    """
    Scan all files in a directory for secret leakage.

    Returns list of paths with detected secrets.
    """
    redactor = SecretRedactor.default()
    if extensions is None:
        extensions = [".json", ".jsonl", ".yaml", ".yml", ".txt", ".log", ".md", ".html"]
    issues: list[str] = []
    for path in directory.rglob("*"):
        if path.is_file() and path.suffix in extensions:
            try:
                scan_artifact(path, redactor)
            except SecretLeakDetected as exc:
                issues.append(str(exc))
    return issues
