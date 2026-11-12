# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

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
