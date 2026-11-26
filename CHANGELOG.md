# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Each entry is one short sentence that starts with a link to its issue or pull request; the details stay there.

## [Unreleased]

### Added

- [#171](https://github.com/WhlteAdmln/audiodoc/issues/171) `make docs-check` reports a path under `audiodoc/`, `scripts/` or `tests/` named in the documentation that does not exist.
- [#170](https://github.com/WhlteAdmln/audiodoc/issues/170) CI installs its system packages from a nightly apt cache and falls back to the network when the cache is missing or does not install.
- [#161](https://github.com/WhlteAdmln/audiodoc/issues/161) `scripts/check_test_rules.py` reports a docstring in a test function.
- [#157](https://github.com/WhlteAdmln/audiodoc/issues/157) `scripts/check_vendored.py` also compares the shared `tests/unit/scripts/docs_checks/test_settings.py`.
- [#118](https://github.com/WhlteAdmln/audiodoc/issues/118) `scripts/check_vendored.py` also compares the shared `docs_checks` modules `links.py`, `markdown.py`, `russian.py` and their tests.
- [#131](https://github.com/WhlteAdmln/audiodoc/issues/131) `scripts/check_vendored.py` has its own shared unit tests in `tests/unit/scripts/test_check_vendored.py`.
- [#130](https://github.com/WhlteAdmln/audiodoc/issues/130) CI reports the number of changed lines of a pull request against the 256-line limit without failing.
- [#129](https://github.com/WhlteAdmln/audiodoc/issues/129) Contributors can read the shared development principles in `docs/development-principles.md` and its Russian twin.

### Changed

- [#163](https://github.com/WhlteAdmln/audiodoc/issues/163) `scripts/check_test_rules.py` applies the one-assert and failure-message rules to every test file, so `tests/strict_test_files.txt` is gone.
- [#119](https://github.com/WhlteAdmln/audiodoc/issues/119) The `latest` CI test job installs the package with its `test` extra without the lock constraint, so it tests the latest allowed dependency versions.
- [#167](https://github.com/WhlteAdmln/audiodoc/issues/167) Ruff sorts the `build` import as third-party even with a leftover `build/` directory.
- [#119](https://github.com/WhlteAdmln/audiodoc/issues/119) The CI test job that installs the package with its `test` extra under the lock is named `package` instead of `latest`.
- [#104](https://github.com/WhlteAdmln/audiodoc/issues/104) Ruff and pylint exempt only test functions from docstrings, and test packages and modules have docstrings.
- [#102](https://github.com/WhlteAdmln/audiodoc/issues/102) Every test has exactly one assert with a failure message, and `scripts/check_test_rules.py` checks all test files in strict mode.
- [#103](https://github.com/WhlteAdmln/audiodoc/issues/103) Unit tests use irregular inputs such as non-ASCII text and binary bytes instead of placeholders like `"abc"` and `"hello"`.
- [#117](https://github.com/WhlteAdmln/audiodoc/issues/117) `WorkQueue` keeps its lifecycle in an explicit open, draining and closed state instead of a flag and an idle event.
- [#105](https://github.com/WhlteAdmln/audiodoc/issues/105) `WorkQueue` drops an unused attribute and its `too-many-instance-attributes` suppression; `Settings` keeps the suppression with an inline reason.
- [#123](https://github.com/WhlteAdmln/audiodoc/issues/123) The `log_safe`, extractor registry and runner tests live in the test files that mirror their modules.
- [#120](https://github.com/WhlteAdmln/audiodoc/issues/120) CI checks for skipped unit, integration and e2e tests with the `test-no-skips`, `test-integration-no-skips` and `test-e2e-no-skips` make targets instead of inline shell.
- [#121](https://github.com/WhlteAdmln/audiodoc/issues/121) The bot contract test loads a fake Whisper model through `loaded_model_holder` instead of patching a private attribute.
- [#122](https://github.com/WhlteAdmln/audiodoc/issues/122) The OCR integration tests share the `PytesseractModule` protocol from `tests/support/tesseract.py`.

### Fixed

- [#171](https://github.com/WhlteAdmln/audiodoc/issues/171) The guides name the extractor matrix and the installed `.env` file at their real locations.
- [#174](https://github.com/WhlteAdmln/audiodoc/issues/174) CI reuses the cached `.deb` files whose versions match the current package index instead of installing every list from the network.
- [#148](https://github.com/WhlteAdmln/audiodoc/issues/148) `audiodoc doctor` fails the API keys check for a key with non-ASCII characters, as startup does.
- [#108](https://github.com/WhlteAdmln/audiodoc/issues/108) Startup rejects an API key with non-ASCII characters with a clear error instead of accepting a key that can never authenticate.
- [#112](https://github.com/WhlteAdmln/audiodoc/issues/112) OCR reports Tesseract output that is not valid UTF-8 as a failed page recognition instead of a generic extraction failure.
- [#110](https://github.com/WhlteAdmln/audiodoc/issues/110) CSV extraction reports a cell longer than 131072 characters with its own client message instead of a generic extraction failure.
- [#115](https://github.com/WhlteAdmln/audiodoc/issues/115) Logs redact the secrets of the latest `configure_logging` call instead of keeping those of the first call.
- [#139](https://github.com/WhlteAdmln/audiodoc/issues/139) `audiodoc run` warns about and `audiodoc pair` renders as loopback every spelling of the all-interfaces bind address.
- [#114](https://github.com/WhlteAdmln/audiodoc/issues/114) `audiodoc doctor` warns about every spelling of the all-interfaces bind address, such as `0` or `::0`.
- [#116](https://github.com/WhlteAdmln/audiodoc/issues/116) Logs redact a Telegram token inside a bot API URL or one that ends with `-`.
- [#113](https://github.com/WhlteAdmln/audiodoc/issues/113) OCR reports an image whose header exceeds Pillow's decompression bomb limit as too large.
- [#109](https://github.com/WhlteAdmln/audiodoc/issues/109) CSV extraction only detects `,`, `;`, tab or `|` as the delimiter, so a single-column file is no longer split on a letter.
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
