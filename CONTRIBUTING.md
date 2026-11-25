# Contributing

1. Use Python 3.11.5 or newer and GNU Make.
2. Create a focused branch for your change.
3. Create a virtual environment with `make venv`.
4. Install development dependencies with `make install-dev`.
5. Keep changes focused and preserve existing application behavior unless the task requires otherwise.
6. Add or update tests for changed behavior. Tests must not require network access, a GPU, or real secrets.
7. Run `make fix` to apply Ruff fixes and formatting.
8. Run `make check` before opening a pull request.
9. For integration tests, install Tesseract OCR (Russian and English) and DjVuLibre, then run `make test-integration`.
10. LLM agents must also follow the rules in [AGENTS.md](AGENTS.md) and [CLAUDE.md](CLAUDE.md). Planned work is tracked in GitHub issues; one issue is one session and one pull request.
11. Follow the [development principles](docs/development-principles.md): they explain the reasons behind these rules.
12. Open a pull request describing the change and the checks you ran. Do not include secrets, local environments, or generated build artifacts.

## Checks and CI

`make check` runs every CI gate that needs only Python and network access: lint and documentation checks, mypy, pylint, deptry, vulture, import contracts, `pip check`, unit tests with coverage that fail when a test is skipped (`make test-no-skips`), `pip-audit` of the lock (`make audit`) and a release build with verified checksums (`make release-check`). The test dependencies are the `test` extra of `pyproject.toml`; the `dev` extra includes it, and the `package` CI job installs the package with it under the lock constraints.

`make lint` also runs `scripts/check_test_layout.py` and `scripts/check_test_rules.py`. The second one fails when a `test_*.py` or `conftest.py` module under `tests/` uses mocks (`unittest.mock`, `mock`, the `mocker` fixture or `assert_called*`), defines a class inside a function, imports `tempfile` or `time.sleep`, when a test function calls `time.sleep`, when a comment inside a test function is not a `# noqa`, `# pylint:`, `# type:` or `# pragma:` pragma followed by a reason, or when a test function has a docstring. The files listed in `tests/strict_test_files.txt` must also have exactly one assert per test and a failure message on every assert; the list only grows.

Only CI runs the jobs that need system tools or services: integration tests with Tesseract and DjVuLibre (`make test-integration-no-skips`), the real Whisper test (`make test-e2e-no-skips`), the Docker image (`make docker`), the installer smoke test against a locally served release, and the systemd, UFW and nginx examples. Like `make test-no-skips`, both test targets fail when a test is skipped.

On a pull request the `pr-size` CI job runs `scripts/report_pr_size.py --base HEAD^1` and prints the number of changed lines (insertions plus deletions) next to the 256-line limit of [the development principles](docs/development-principles.md). `requirements-lock.txt`, `*.ru.md` translations and files marked `linguist-generated` in `.gitattributes` are not counted. The job only reports and never fails.

## Files shared with bot-obormot

`.editorconfig`, `.pre-commit-config.yaml`, `.github/renovate.json5`, `.markdownlint-cli2.yaml`, `AGENTS.md`, `CLAUDE.md`, `docs/development-principles.md`, `docs/development-principles.ru.md`,
`scripts/build_release.sh`, `scripts/check_changelog.py`, `scripts/check_lock.py`, `scripts/check_test_layout.py`,
`scripts/check_test_rules.py`, `scripts/check_vendored.py`, `scripts/coverage_gaps.py`, `scripts/docs_checks/links.py`, `scripts/docs_checks/markdown.py`, `scripts/docs_checks/russian.py`, `scripts/report_pr_size.py`, `tests/unit/scripts/test_check_changelog.py`, `tests/unit/scripts/test_check_test_rules.py`, `tests/unit/scripts/test_check_vendored.py`, `tests/unit/scripts/test_report_pr_size.py`, `tests/unit/scripts/docs_checks/test_links.py`, `tests/unit/scripts/docs_checks/test_markdown.py`, `tests/unit/scripts/docs_checks/test_russian.py`, `tests/unit/scripts/docs_checks/test_settings.py`, the `ruff`, `mypy` and `pylint` tables of `pyproject.toml`,
`audiodoc/log_filters.py` and `audiodoc/env_readers.py` are copied into bot-obormot.
audiodoc is the source of truth. After changing one of them, copy it to the bot repository
and run `python scripts/check_vendored.py --other ../bot-obormot` in both repositories.

## Documentation checks

`make docs-check` runs `scripts/check_docs.py`. It runs the changelog check and the modules of `scripts/docs_checks/`: `links.py` (local links and their anchors), `russian.py` (H2 section parity and Cyrillic text of `.ru.md` twins), `settings.py` (settings against `.env.example` and `docs/configuration.md`), `cli_commands.py` (documented CLI commands against the real parser), one project-specific check, and `markdown.py` (helpers the others share). Each module has its tests in `tests/unit/scripts/docs_checks/`.

`markdown.py`, `links.py` and `russian.py` are the same in audiodoc and bot-obormot. The other modules differ on purpose:

- Settings source: audiodoc reads `audiodoc.config.Settings` and maps the field `TEMP_DIR` to the variable `BACKEND_TEMP_DIR`; bot-obormot reads `bot_obormot.settings.Settings` and skips the computed fields `DEFAULT_HISTORY_EXCHANGES` and `DEFAULT_SYSTEM_PROMPT`. Each lists its own names that are documented but are not settings (`AUDIODOC_HOME`, `AUDIODOC_HOST`, `AUDIODOC_PORT` in audiodoc, `BOT_OBORMOT_HOME` in bot-obormot).
- Project-specific check: audiodoc checks that every path of `contract/openapi.json` appears in `docs/api.md` (`openapi.py`); bot-obormot checks that every Telegram command declared as `Command("...")` in `bot_obormot/` appears in `docs/commands.md` (`telegram_commands.py`).
- CLI command check: only the command name (`audiodoc` or `bot-obormot`) and the parser it imports (`audiodoc.cli` or `bot_obormot.cli`) differ.

## Changelog

Every `CHANGELOG.md` entry is one short sentence that starts with a link to the issue it closes, for example `- [#107](https://github.com/WhlteAdmln/audiodoc/issues/107) audiodoc doctor no longer reports ...`. The details stay in the issue.

## Dependency updates

Renovate is the only tool that updates dependencies, opens pull requests and merges them; its configuration is `.github/renovate.json5`. Minor and patch updates are merged automatically after every check passes, except for the parsers and network libraries listed in the configuration, which are merged automatically only for patches. A human merges every update that can run code with more trust than the application: major updates, `0.x` releases, GitHub Actions, pre-commit hooks and the build tooling (`setuptools`, `wheel`, `build`, `packaging`). Python versions and the image base are changed by hand. The lock is refreshed on the first day of each month in `renovate/pip-compile-refresh`; it is the only way transitive packages change, and a human merges it. `requirements-lock.txt` is generated by `make lock` (it needs `uv`) and is never edited by hand; Renovate regenerates it with the same command, and `make lock` skips releases younger than 14 days (`make lock LOCK_MIN_RELEASE_AGE_DAYS=0` turns the cutoff off when `pyproject.toml` already requires a newer release). A release must be 14 days old before it is proposed; security fixes are not delayed.

Dependabot alerts and the dependency graph stay enabled as a second source of vulnerability reports, and Renovate reads the alerts. Dependabot security updates and version updates are disabled so that only one tool opens pull requests.

## Code style

Use the assignment expression `:=` only when the value is needed for the condition and is used again inside the block, as in `while chunk := file.read(size):`. Use a plain assignment when the name is used once, when the expression becomes nested or hard to read, or when two separate lines show the order of steps better. The goal is to avoid computing the same value twice, not to save lines.

## Open questions

- Abandoned dependencies reported by Renovate (for example `odfpy`, `defusedxml`, `pytesseract`, `python-pptx`): review whether to replace them. Several of them parse untrusted files.
- `max-try-statements = 1` in the pylint configuration is reported for existing long `try` blocks; they are split gradually.
