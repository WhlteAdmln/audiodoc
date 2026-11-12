# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added (Installer)

- CI smoke coverage for release-wheel installation and virtual environment upgrades.
- Installer tests for HTTP release assets, version changes, and rollback after a failed offline doctor check.

### Changed

- Replaced the legacy installer interface with verified release-wheel installation and staged `--upgrade`.
- Removed the legacy installer flags `--latest`, `--nightly`, and `--yes`; the installer now selects the latest stable release automatically.
- Replaced the `AUDIODOC_INSTALL_DIR` environment variable with `AUDIODOC_HOME`.
- Documented the legacy 0.1.0 directory upgrade path and rollback behavior.

## [0.1.0] - 2026-11-06

### Added

- FastAPI service for audio transcription and document text extraction.
- Authenticated transcription and document-processing endpoints.
- Bounded processing queues, readiness checks, and request-ID logging.
- audiodoc deployment examples, bot connection guide, and release installer.

### Fixed

- Document truncation reporting at exact text-budget boundaries and across extractors.
