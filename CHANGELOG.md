# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Each entry is one short sentence that starts with a link to its issue or pull request; the details stay there.

## [Unreleased]

### Added

- [#130](https://github.com/WhlteAdmln/audiodoc/issues/130) CI reports the number of changed lines of a pull request against the 256-line limit without failing.
- [#129](https://github.com/WhlteAdmln/audiodoc/issues/129) Contributors can read the shared development principles in `docs/development-principles.md` and its Russian twin.

### Fixed

- [#111](https://github.com/WhlteAdmln/audiodoc/issues/111) XML extraction keeps the text that follows a child element.
- [#107](https://github.com/WhlteAdmln/audiodoc/issues/107) `audiodoc doctor` no longer reports the API port as failed while the service is running.
- [#106](https://github.com/WhlteAdmln/audiodoc/issues/106) `install.sh --upgrade` no longer leaves `.venv.new` paths in the environment, so the service starts after an upgrade.

### Removed

- [#124](https://github.com/WhlteAdmln/audiodoc/issues/124) `ROADMAP.md`; planned work lives in GitHub issues.

## [0.3.0] - 2026-11-24

Deprecated functionality is not supported starting with 0.3.0.

### Added

- pylint with every message enabled, next to ruff and mypy, for the package, the scripts and the tests.
- `AGENTS.md` and `CLAUDE.md` with the rules for LLM agents, and `ROADMAP.md` with the planned work.
- Checks shared with bot-obormot: `check_test_layout.py`, `check_test_rules.py`, `check_changelog.py` and `coverage_gaps.py`.
- [#73](https://github.com/WhlteAdmln/audiodoc/pull/73) `make lock` generates `requirements-lock.txt` with `uv pip compile` and skips releases younger than 14 days.
- [#91](https://github.com/WhlteAdmln/audiodoc/pull/91) `make check` runs every local CI gate.
- [#91](https://github.com/WhlteAdmln/audiodoc/pull/91) The `test` extra holds the test dependencies; the `dev` extra includes it.
- [#86](https://github.com/WhlteAdmln/audiodoc/pull/86) `audiodoc.errors.djvu` and `audiodoc.errors.images` hold the DJVU and OCR errors as public classes.
- [#86](https://github.com/WhlteAdmln/audiodoc/pull/86) `audiodoc.transcription.temp_files.temp_dir()` returns the private audio directory.
- [#66](https://github.com/WhlteAdmln/audiodoc/pull/66) Python 3.14 classifiers and a Python 3.14 CI job.

### Changed

- Python 3.11.5 or newer is required.
- Renovate replaces Dependabot version updates; Dependabot alerts stay enabled.
- CI runs the type, dependency, dead-code and import-contract gates.
- [#88](https://github.com/WhlteAdmln/audiodoc/pull/88) `audiodoc/cli.py` is split into the `audiodoc.cli` package with one module per command.
- [#90](https://github.com/WhlteAdmln/audiodoc/pull/90) `scripts/check_docs.py` is split into `scripts/docs_checks/`.
- [#54](https://github.com/WhlteAdmln/audiodoc/pull/54) `scripts/check_vendored.py` compares only the files that are really shared.
- Stricter lint and fewer ruff ignores; behavior is unchanged.
- [#86](https://github.com/WhlteAdmln/audiodoc/pull/86) Importing `audiodoc.transcription.temp_files` no longer loads the settings.
- [#92](https://github.com/WhlteAdmln/audiodoc/pull/92) Tests follow the general test rules.
- The security tests have one assert with a message per test and cover hostile inputs.

### Fixed

- [#54](https://github.com/WhlteAdmln/audiodoc/pull/54) The installer reads the latest release metadata from GitHub again.
- [#100](https://github.com/WhlteAdmln/audiodoc/pull/100) The source checkout instructions install audiodoc itself, not only its dependencies.

### Removed

- [#66](https://github.com/WhlteAdmln/audiodoc/pull/66) The `WHISPER_API_KEY` and `DOCUMENT_API_KEY` environment variables. Use `AUDIODOC_AUDIO_KEY` and `AUDIODOC_DOCUMENT_KEY`.
- [#66](https://github.com/WhlteAdmln/audiodoc/pull/66) The `app.py` module and the `uvicorn app:app` entry point. Use `audiodoc run`.
- [#66](https://github.com/WhlteAdmln/audiodoc/pull/66) The duplicate modules `audiodoc.common.logging_setup`, `audiodoc.common.log_filters` and `audiodoc.config.env`.
- [#86](https://github.com/WhlteAdmln/audiodoc/pull/86) `TEMP_DIR` and `DEFAULT_TEMP_DIR` in `audiodoc.transcription.temp_files`. Call `temp_dir()` instead.
- [#66](https://github.com/WhlteAdmln/audiodoc/pull/66) The 0.1.x migration in `install.sh` and its CI job.

### Security

- [#75](https://github.com/WhlteAdmln/audiodoc/pull/75) The lock pins `soupsieve` 4.x, which fixes GHSA-mmhr-3c5m-f64f.

## [0.2.0] - 2026-11-12

### Added (CLI, Docker, and API errors)

- [#35](https://github.com/WhlteAdmln/audiodoc/pull/35) Added a command-line interface for application management.
- [#40](https://github.com/WhlteAdmln/audiodoc/pull/40) Added Docker and Docker Compose deployment.
- [#29](https://github.com/WhlteAdmln/audiodoc/pull/29) Added a stable `code` field to API error responses.
- [#39](https://github.com/WhlteAdmln/audiodoc/pull/39) Added CI smoke coverage for release-wheel installation and virtual environment upgrades.
- [#39](https://github.com/WhlteAdmln/audiodoc/pull/39) Added installer tests for HTTP release assets, version changes, and rollback after a failed offline doctor check.

### Changed

- [#34](https://github.com/WhlteAdmln/audiodoc/pull/34) Renamed the Python package and import namespace from `backend` to `audiodoc`.
- [#28](https://github.com/WhlteAdmln/audiodoc/pull/28) Renamed API key settings to `AUDIODOC_AUDIO_KEY` and `AUDIODOC_DOCUMENT_KEY`.
- [#39](https://github.com/WhlteAdmln/audiodoc/pull/39) Replaced the legacy installer interface with verified release-wheel installation and staged `--upgrade`.
- Replaced the `AUDIODOC_INSTALL_DIR` environment variable with `AUDIODOC_HOME`.
- [#45](https://github.com/WhlteAdmln/audiodoc/pull/45) Documented the legacy 0.1.0 directory upgrade path and rollback behavior.

### Deprecated

- [#28](https://github.com/WhlteAdmln/audiodoc/pull/28) Deprecated `WHISPER_API_KEY`; use `AUDIODOC_AUDIO_KEY` instead.
- [#28](https://github.com/WhlteAdmln/audiodoc/pull/28) Deprecated `DOCUMENT_API_KEY`; use `AUDIODOC_DOCUMENT_KEY` instead.
- Deprecated `uvicorn app:app`; use `audiodoc run` instead.

### Removed

- [#39](https://github.com/WhlteAdmln/audiodoc/pull/39) Removed the legacy installer flags `--latest`, `--nightly`, and `--yes`. The installer selects the latest stable release automatically.

## [0.1.0] - 2026-11-06

### Added

- FastAPI service for audio transcription and document text extraction.
- Authenticated transcription and document-processing endpoints.
- Bounded processing queues, readiness checks, and request-ID logging.
- audiodoc deployment examples, bot connection guide, and release installer.

### Fixed

- [#1](https://github.com/WhlteAdmln/audiodoc/pull/1) Document truncation reporting at exact text-budget boundaries and across extractors.
