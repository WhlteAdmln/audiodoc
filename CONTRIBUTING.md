# Contributing

1. Use Python 3.11 or newer and GNU Make.
2. Create a focused branch for your change.
3. Create a virtual environment with `make venv`.
4. Install development dependencies with `make install-dev`.
5. Keep changes focused and preserve existing application behavior unless the task requires otherwise.
6. Add or update tests for changed behavior. Tests must not require network access, a GPU, or real secrets.
7. Run `make fix` to apply Ruff fixes and formatting.
8. Run `make check` before opening a pull request.
9. For integration tests, install Tesseract OCR (Russian and English) and DjVuLibre, then run `make test-integration`.
10. LLM agents must also follow the rules in [AGENTS.md](AGENTS.md).
11. Open a pull request describing the change and the checks you ran. Do not include secrets, local environments, or generated build artifacts.

## Files shared with bot-obormot

`.editorconfig`, `.pre-commit-config.yaml`, `.github/dependabot.yml`, `scripts/check_lock.py`,
`scripts/check_vendored.py`, `scripts/build_release.sh`, `.markdownlint-cli2.yaml`, `AGENTS.md`, the `ruff` and `mypy` tables of `pyproject.toml`,
`audiodoc/log_filters.py` and `audiodoc/env_readers.py` are copied into bot-obormot.
audiodoc is the source of truth. After changing one of them, copy it to the bot repository
and run `python scripts/check_vendored.py --other ../bot-obormot` in both repositories.
