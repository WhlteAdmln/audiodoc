# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Fixed

- `audiodoc doctor` no longer reports the API port as failed while the audiodoc service runs on it: when the port is in use, doctor asks `/health` on that address and reports the port as used by the running service if audiodoc answers.
- `install.sh --upgrade` points the staged environment at `.venv` before the swap, so scripts, `activate`, `pyvenv.cfg` and bytecode no longer refer to `.venv.new` and the systemd service starts after an upgrade.

## [0.3.0] - 2026-11-24

Deprecated functionality is not supported starting with 0.3.0.

### Added

- pylint with every message enabled and all stable extensions (pinned to 4.1.4), next to ruff and mypy, for the package, the scripts and every test module.
- `AGENTS.md` and `CLAUDE.md` with the rules for LLM agents, and `ROADMAP.md` with the planned work; `CONTRIBUTING.md` links them.
- Checks shared with bot-obormot: `scripts/check_test_layout.py` (unit tests mirror the production unit they cover), `scripts/check_test_rules.py` (no mocks, no classes inside test functions, no `tempfile` or `time.sleep`, no comments in tests; strict files need one assert with a message per test), `scripts/check_changelog.py` (section order) and `scripts/coverage_gaps.py`.
- `make lock` generates `requirements-lock.txt` with `uv pip compile` and skips releases younger than 14 days unless `LOCK_MIN_RELEASE_AGE_DAYS=0` is passed.
- `make check` runs every local CI gate, including `pip check`, `make audit`, `make test-no-skips` and `make release-check`.
- The `test` extra holds the test dependencies; the `dev` extra includes it.
- `audiodoc.errors.djvu` and `audiodoc.errors.images` hold the client-safe DJVU and OCR errors as public classes; messages, codes and HTTP statuses are unchanged.
- `audiodoc.transcription.temp_files.temp_dir()` returns the private audio directory from the current settings.
- Python 3.14 classifiers and a Python 3.14 CI job.

### Changed

- Python 3.11.5 or newer is required: `requires-python`, the installer and `audiodoc doctor` check it, and `audiodoc doctor` reports the full Python version.
- Renovate replaces Dependabot version updates. It refreshes the lock monthly, updates coupled packages together and leaves major, `0.x`, GitHub Actions, pre-commit, build tooling and parser or network minor updates to a human. Dependabot alerts stay enabled.
- CI runs the type, dependency, dead-code and import-contract gates; the job with the latest allowed dependencies installs the `test` extra.
- `audiodoc/cli.py` is split into the `audiodoc.cli` package with one module per command; `audiodoc.cli.main`, the now public `build_parser`, the console script and the CLI output are unchanged.
- `scripts/check_docs.py` is split into `scripts/docs_checks/`; `CONTRIBUTING.md` describes how the copies in both repositories differ.
- `scripts/check_vendored.py` compares only the shared lint tables and the files that are really shared; `get_home_dir()` derives the home variable from the package name.
- Stricter lint: `max-try-statements = 1`, magic values as named constants, long functions split, no vulture whitelist, and the ruff ignores `FBT`, `TD002`, `TD003`, `FIX002`, `ANN`, `ARG`, `PLR2004` and `SLF001` are gone. Minimal stubs in `typings/` replace `Any` casts for `odf` and `pymupdf`; `transcribe_file` returns a `TranscriptionResult` typed dictionary. Behavior is unchanged.
- `audiodoc.transcription.temp_files` resolves the temporary directory when it is used, so importing it no longer loads the settings.
- Tests follow the general test rules: one file per production unit, fakes in `tests/support/` instead of `unittest.mock`, public entry points only, function-scoped fixtures, typed empty literals, no sleeping. Test functions and modules still need no docstring; a later release removes this exemption.
- The security tests of the API, common utilities, document engine, log filters, temporary files, installer, application factory, settings, diagnostics, document pipeline and Docker image have one assert with a message per test, cover hostile inputs and are listed in `tests/strict_test_files.txt`.

### Fixed

- The installer reads the latest release metadata from GitHub again, and a broken URL in one installer error message is corrected.
- The source checkout instructions install audiodoc itself with `pip install --constraint requirements-lock.txt .` instead of only its dependencies.

### Removed

- The `WHISPER_API_KEY` and `DOCUMENT_API_KEY` environment variables. Use `AUDIODOC_AUDIO_KEY` and `AUDIODOC_DOCUMENT_KEY`.
- The `app.py` module and the `uvicorn app:app` entry point. Use `audiodoc run`.
- The duplicate modules `audiodoc.common.logging_setup`, `audiodoc.common.log_filters` and `audiodoc.config.env`. Import `audiodoc.logging_setup`, `audiodoc.log_filters` and `audiodoc.env_readers` instead.
- `TEMP_DIR` and `DEFAULT_TEMP_DIR` in `audiodoc.transcription.temp_files`. Call `temp_dir()` or set `BACKEND_TEMP_DIR`.
- The 0.1.x migration in `install.sh` and its CI job.

### Security

- The lock resolves for Python 3.11.5 or newer and pins `soupsieve` 4.x, which fixes GHSA-mmhr-3c5m-f64f (denial of service in the descendant combinator).

## [0.2.0] - 2026-11-12

### Added (CLI, Docker, and API errors)

- Added a command-line interface for application management.
- Added Docker and Docker Compose deployment.
- Added a stable `code` field to API error responses.
- Added CI smoke coverage for release-wheel installation and virtual environment upgrades.
- Added installer tests for HTTP release assets, version changes, and rollback after a failed offline doctor check.

### Changed

- Renamed the Python package and import namespace from `backend` to `audiodoc`.
- Renamed API key settings to `AUDIODOC_AUDIO_KEY` and `AUDIODOC_DOCUMENT_KEY`.
- Replaced the legacy installer interface with verified release-wheel installation and staged `--upgrade`.
- Replaced the `AUDIODOC_INSTALL_DIR` environment variable with `AUDIODOC_HOME`.
- Documented the legacy 0.1.0 directory upgrade path and rollback behavior.

### Deprecated

- Deprecated `WHISPER_API_KEY`; use `AUDIODOC_AUDIO_KEY` instead.
- Deprecated `DOCUMENT_API_KEY`; use `AUDIODOC_DOCUMENT_KEY` instead.
- Deprecated `uvicorn app:app`; use `audiodoc run` instead.

### Removed

- Removed the legacy installer flags `--latest`, `--nightly`, and `--yes`. The installer selects the latest stable release automatically.

## [0.1.0] - 2026-11-06

### Added

- FastAPI service for audio transcription and document text extraction.
- Authenticated transcription and document-processing endpoints.
- Bounded processing queues, readiness checks, and request-ID logging.
- audiodoc deployment examples, bot connection guide, and release installer.

### Fixed

- Document truncation reporting at exact text-budget boundaries and across extractors.
