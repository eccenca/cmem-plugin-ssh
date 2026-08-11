# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

`cmem-plugin-ssh` is a plugin for [eccenca Corporate Memory](https://documentation.eccenca.com) that enables file transfer and command execution via SSH/SFTP. Built on the `cmem-plugin-base` framework, it registers three workflow plugins: **Download**, **Upload**, and **List** (file operations) plus **Execute** (remote command execution).

## Codebase Structure

```
cmem_plugin_ssh/
  __init__.py              # Package marker
  download.py              # DownloadFiles plugin – downloads files from SSH to local temp dir
  upload.py                # UploadFiles plugin – uploads local files to SSH (auto-detects gzip, text/binary)
  list.py                  # ListFiles plugin – lists remote files with metadata (name, size, uid, gid, mode, atime, mtime)
  execute_commands.py      # ExecuteCommands plugin – runs arbitrary SSH commands (no_input / file_input, structured_output / file_output / no_output)
  retrieval.py             # SSHRetrieval class – recursive parallel file listing with thread-local SFTP clients, regex filtering, error handling modes
  autocompletion.py        # DirectoryParameterType – case-sensitive folder autocompletion for the CMem UI
  utils.py                 # Shared constants (AUTHENTICATION_CHOICES, ERROR_HANDLING_CHOICES), load_private_key (RSA/ECDSA/Ed25519 — DSS dropped in paramiko 5.x), generate_list_schema, preview_results
tests/
  conftest.py              # Test fixtures / SSH server via testcontainers
  fixtures.py              # Shared test helpers
  test_*.py                # One file per plugin module
```

### Key Architecture Notes

- Every workflow plugin extends `WorkflowPlugin` and is decorated with `@Plugin(label=..., plugin_id=..., parameters=[...])`. The decorator registers the plugin with CMem at runtime.
- SSH connections are established lazily in `_initialize_ssh_and_sftp_connections()` (creates `paramiko.SSHClient` + `SFTPClient`). Always call `cleanup_ssh_connections()` when done.
- `SSHRetrieval.list_files_parallel()` does recursive directory listing using `ThreadPoolExecutor`. It uses thread-local SFTP clients (`threading.local`) to avoid cross-thread sharing of paramiko connections. Subfolder recursion is parallelized by subdirectory.
- Autocompletion (`DirectoryParameterType.autocomplete()`) connects to the SSH server at query time; it depends on parameters 0–6 (hostname, port, username, private_key, password, authentication_method, path). Case sensitivity in `autocomplete_query` was a previous bugfix (see commit `658f0e1`).
- Auth: supports "password" and "key" methods. `load_private_key()` strips whitespace from PEM body and tries loaders (RSAKey → ECDSAKey → Ed25519Key) sequentially with optional passphrase; DSS/DSA keys are no longer supported (paramiko 5.x).

## Development Commands

All commands use `task` (Taskfile). Run `task` or `task --list` for the full list.

| Task | Description |
|------|-------------|
| `task check` | Full check suite: linters + pytest |
| `task check:linters` | ruff + mypy + deptry + trivy |
| `task check:ruff` | Lint and format check (exit 0 on lint) |
| `task check:mypy` | Type checking |
| `task check:deptry` | Unused/missing dependency check |
| `task check:trivy` | Vulnerability scan |
| `task check:pytest` | Run tests with coverage + HTML report |
| `task format:fix` | ruff format + auto-fix |
| `task format:fix-unsafe` | ruff format + unsafe auto-fixes too |
| `task build` | `poetry build` + export requirements.txt |
| `task install` | Build and install plugin in Corporate Memory (requires `cmemc`) |
| `task uninstall` | Uninstall plugin from Corporate Memory |
| `task clean` | Remove dist, pyc, caches |

**Custom tasks:** Add new tasks to `TaskfileCustom.yaml` (optionally included by the base `Taskfile.yaml`).

**Running a single test:**
```
poetry run pytest tests/test_download.py -v
```

## Dependencies

- **Runtime**: `paramiko 5.x` (DSS/DSA removed), `cmem-plugin-base ^4.19.0`
- **Dev**: ruff, mypy, deptry, pytest (+cov, dotenv, html, memray), trivy-py-ecc, testcontainers
- **Python**: 3.13 (see `.python-version`)

## Configuration Highlights

- `ruff`: line-length=100, target=py313, selects ALL rules with specific ignores (see `pyproject.toml` `[tool.ruff.lint]`).
- `mypy`: `warn_return_any = true`, `ignore_missing_imports = true`.
- `.pre-commit-config.yaml`: runs `task check:ruff`, `poetry check`, `poetry lock`, `poetry install`, `task check:trivy` on changed files.

## CI

- GitHub Actions: `.github/workflows/check.yml` (CI), `.github/workflows/publish.yml` (PyPI publish).
- GitLab CI: `.gitlab-ci.yml`.