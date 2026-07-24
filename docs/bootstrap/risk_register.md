# Omega Supreme Bootstrap — Risk Register

| Risk ID | Category | Risk Description | Mitigation Strategy | Status |
| :--- | :--- | :--- | :--- | :---: |
| **RISK-001** | Compatibility | Dynamic plugin loading destabilizes default static provider construction | Maintain `provider_factory.py` static map as fallback default | Controlled |
| **RISK-002** | Output Purity | CLI log contamination breaks `release-check --format json` purity | Use `_write_json_stdout` unhooked stream + context logger suppression | Mitigated |
| **RISK-003** | Test Isolation | Unit tests invoking `release-check` cause recursive test loop | Exclude self-referencing tests & mock `_collect_release_checks` | Mitigated |
| **RISK-004** | Windows OS | `click.echo` triggers Colorama `AnsiToWin32` handle crash (`OSError: 6`) | Direct `sys.stdout.write` with `ensure_ascii=True` | Mitigated |
| **RISK-005** | Security | Secret leakage in dynamic plugin metadata or logs | Enforce `SecretRedactor` on all trace attributes and plugin manifests | Active |
