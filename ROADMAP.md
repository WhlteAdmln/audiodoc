# Roadmap

This file holds the plans for audiodoc. It lives next to `CHANGELOG.md`: the changelog records what was released, the roadmap records what is planned and what is in progress. `CLAUDE.md` tells Claude how to read it.

## How to use this file

- Work is split into tasks. One task is one Claude Code session. A task is a heading `#### <ID> <title>` followed by `Needs:`, `Scope:` and `Done when:`.
- IDs are `AD-<number>` for audiodoc and `BO-<number>` for bot-obormot. Numbers are never reused.
- The next task is the first one, in document order, that is not struck through and whose `Needs:` tasks are done. Tasks run in the order of this file.
- A finished task stays in place: its heading and every `Scope:` bullet are struck through (`~~text~~`).
- A task marked `[shared]` changes files that exist in both repositories. audiodoc is the source of truth, so the task is done in a session here, and bot-obormot keeps a pointer with the same title in its own `ROADMAP.md`. Both are struck through together.
- Work that is not split into tasks yet lives under "Planned" and "Backlog". It becomes tasks when its release starts.
- When a release is published, its section collapses into one line under "Released".

## 0.3.0 (in progress)

Goal: remove deprecated functionality, make the code base uniform with bot-obormot and make every gate strict. Behavior does not change except for the removed functionality. The starting point is 0.2.0.

### Tasks

#### ~~AD-01 Suppressions, types and small cleanups~~

- Needs: none.
- Scope:
  - ~~Replace `Any` where the precise type is obvious (4 left: `audiodoc/config/settings.py` and three in `audiodoc/transcription/service.py`).~~
  - ~~Give the `S603` and `consider-using-with` suppressions in `audiodoc/common/subprocess_runner.py` a one-line reason on the same line, or remove them (one wrapper with a validated argv).~~
  - ~~Add a comment to every `DEP002` entry in `pyproject.toml` (`uvicorn`, `python-multipart` and `av` have none).~~
  - ~~Confirm that the SWIG `DeprecationWarning` in `filterwarnings` comes from a third-party package and comment it.~~
  - ~~Delete the empty `tests/layout_pending.txt`.~~
- Done when: no suppression without a reason; `make check` is green.

#### ~~AD-02 Split `audiodoc/cli.py`~~

- Needs: none.
- Scope:
  - ~~Split `audiodoc/cli.py` (555 lines) by responsibility into modules that mirror the command groups, keeping `build_parser` and the `audiodoc` entry point unchanged.~~
  - ~~Move the tests so that every module has one mirrored test file.~~
- Done when: the import-linter contracts stay valid, no production file is much longer than 350 lines (or the reason is listed), `make check` is green.

#### ~~AD-03 [shared] Split `scripts/check_docs.py` and document its differences~~

- Needs: none.
- Scope:
  - ~~Split `scripts/check_docs.py` (audiodoc 474 lines, bot-obormot 471) by responsibility in both repositories.~~
  - ~~Describe the intentional differences between the two copies (settings source, OpenAPI check, CLI command check) in the "Documentation checks" part of `CONTRIBUTING.md` of both repositories.~~
  - ~~Replace the private `_settings_environment_names` import in `tests/unit/scripts/test_check_docs.py` of both repositories with a public name.~~
- Done when: both `make docs-check` are green and no test imports a private name from the script.

#### ~~AD-04 [shared] `make check` runs every CI gate; one extra for test dependencies~~

- Needs: none.
- Scope:
  - ~~Compare the jobs of `.github/workflows/ci.yml` with the `check` target of the `Makefile` in both repositories and add every gate that CI runs and `make check` does not.~~
  - ~~Add one extra (for example `test`) with the test dependencies, used by `dev` and by the CI job with the latest allowed dependencies, so the package lists cannot drift.~~
  - ~~Keep the `Makefile` target names identical in both repositories.~~
- Done when: `make check` is the one command that covers CI, and the CI job with the latest dependencies installs the extra instead of a hand-written list.

#### ~~AD-05 General test rules in audiodoc~~

- Needs: AD-03.
- Scope:
  - ~~Remove comments from test files (except tool pragmas with a reason), docstrings from test functions, classes defined inside test functions, `time.sleep` for waiting and temporary files outside `tmp_path`.~~
  - ~~Move every remaining fake to `tests/support/`; remove the one `unittest.mock` use.~~
  - ~~Rename tests whose names are not sentences with a verb, and mechanical names such as `expected_fragment` or `expected_text_2`.~~
  - ~~Remove shared mutable state and fixtures wider than `function` scope, except immutable data.~~
- Done when: a throwaway scan finds none of the above; the test count did not fall; `make check` is green.

#### ~~AD-06 [shared] `scripts/check_test_rules.py`~~

- Needs: AD-05, BO-09.
- Scope:
  - ~~Add `scripts/check_test_rules.py` with its own tests. It fails on mocks, classes inside test functions, comments other than `# noqa`, `# pylint`, `# type:` and `# pragma` with a reason, `time.sleep` and `tempfile` outside `tmp_path`.~~
  - ~~For the files of the security list (AD-07 to AD-09 and BO-11 to BO-13) it also fails on tests with more than one assert and on asserts without a message. The list is kept in the script or in a file that only grows.~~
  - ~~Add the script to the vendored files and to `CONTRIBUTING.md` of both repositories; run it from `make lint`, `make check` and CI.~~
- Done when: both repositories pass the script and `check_vendored.py` matches.

#### AD-07 Security tests: API and common utilities

- Needs: AD-06.
- Scope:
  - Bring these files to the full standard: one assert per test, a message on every assert, hostile and unusual inputs, public entry points only, and add them to the list of `check_test_rules.py`.
  - `tests/unit/api/`: `test_auth.py`, `test_middleware.py`, `test_documents.py`, `test_transcribe.py`.
  - `tests/unit/common/`: `test_limited_upload.py`, `test_work_queue.py`, `test_deadline.py`, `test_request_id.py`, `test_subprocess_runner.py`.
- Done when: the script passes with these files on the list; coverage did not drop.

#### AD-08 Security tests: document engine

- Needs: AD-06.
- Scope:
  - Same standard as AD-07 for `tests/unit/document_engine/`: `guards/test_zip_archive.py`, `guards/test_xml_safe.py`, `extractors/test_djvu.py`, `extractors/test_xml_text.py`, `extractors/test_csv_text.py`, `ocr/test_preprocessing.py`, `ocr/test_recognize.py`, `ocr/test_tesseract.py`, `test_ocr.py`.
- Done when: as AD-07.

#### AD-09 Security tests: log filters, temporary files, installer

- Needs: AD-06.
- Scope:
  - Same standard as AD-07 for `tests/unit/test_log_filters.py`, `tests/unit/transcription/test_temp_files.py`, `tests/unit/project/test_installer.py` and `tests/unit/project/test_installer_python_snippets.py`.
  - Review the whole test tree once more against the security criteria (limits, authentication and permissions, dangerous files, masking of secrets and logs, subprocesses, installation) and add files that qualify.
- Done when: as AD-07.

#### AD-10 [shared] Release 0.3.0

- Needs: AD-01 to AD-09 and BO-01 to BO-13.
- Scope:
  - Move `[Unreleased]` into `[0.3.0]`, shorten the entries, set the release date (now 2026-11-21) and `version = "0.3.0"`.
  - Replace the old version where it is current: README (EN and RU), docs, `Dockerfile`, `compose*.yaml`, `deploy/`, `install.sh`, version-asserting tests, `contract/openapi.json`; copy the contract to `bot-obormot/tests/contract/audiodoc-openapi.json`.
  - Regenerate the lock with `make lock`.
  - Require Python 3.11.5 or newer and install with `--constraint`.
  - Confirm the CI matrix and classifiers for Python 3.11 to 3.14.
  - Collapse this section into "Released".
- Done when: both `make check` are green. The user then enables branch protection on `main`, tags and publishes the release.

### Done before this roadmap

- ~~The `WHISPER_API_KEY` and `DOCUMENT_API_KEY` environment variables are removed.~~
- ~~The `app.py` module and the `uvicorn app:app` entry point are removed.~~
- ~~The duplicate modules `audiodoc.common.logging_setup`, `audiodoc.common.log_filters` and `audiodoc.config.env` are removed.~~
- ~~The 0.1.x upgrade path in `install.sh`, its tests and its CI job are removed.~~
- ~~pylint with every message and all stable extensions, pinned to 4.1.4, rated 10.00 for the package, the scripts and every test module.~~
- ~~Renovate replaces Dependabot version updates; the lock is refreshed monthly and merged by a human.~~
- ~~`make lock` generates `requirements-lock.txt` with `uv`; `scripts/check_lock.py` checks it.~~
- ~~CI runs the type, dependency, dead-code and import-contract gates.~~
- ~~CI test matrix and classifiers cover Python 3.11 to 3.14; the unit suite passes on Python 3.14 with the lock and every compiled dependency has a 3.14 wheel (checked on PyPI).~~
- ~~`AGENTS.md`, `scripts/check_vendored.py` (15 files), `scripts/check_test_layout.py`, `scripts/check_changelog.py` and `scripts/coverage_gaps.py`, shared with bot-obormot.~~
- ~~vulture runs without a whitelist; the ruff ignores `FBT`, `TD002`, `TD003`, `FIX002` are gone and the test ignores are reduced to `S101` and `D1`.~~
- ~~Minimal stubs in `typings/` replace `ignore_missing_imports` and `Any` casts for `odf` and `pymupdf`.~~
- ~~Magic values are named constants, every `try` wraps one statement, long functions are split; `build_parser` is public.~~
- ~~The client-safe DJVU and OCR errors are public classes in `audiodoc.errors.djvu` and `audiodoc.errors.images`; `temp_dir()` resolves the temporary directory when it is used.~~
- ~~Unit tests mirror the production unit they cover; shared fakes live in `tests/support/`.~~
- ~~No test reads or patches a private name; checks for an empty result compare with a typed empty literal.~~

## Planned

### 0.4.x: alpha finishing

- One assert per test and a message on every assert in all tests, not only the security tests.
- Unusual inputs instead of `"x"` and `"foo"` in all tests.
- Remove the pylint `no-docstring-rgx` exemption for tests and the `D1` ignore for `tests/*`.
- Review the remaining production suppressions: `too-many-instance-attributes` in `config/settings.py` and `common/work_queue.py`.

### 0.5.0: beta

The scope is not defined yet.

## Backlog

- Add `scripts/docs_checks/markdown.py`, `links.py`, `russian.py` and their tests to the files checked by `scripts/check_vendored.py`; they are identical in both repositories since AD-03.
- The CI job with the latest allowed dependencies installs `-c requirements-lock.txt`, so its runtime packages are the locked ones, not the latest allowed; decide whether it should drop the constraint, as bot-obormot does.
- The CI test, integration and e2e steps repeat the skipped-test check in shell; they could call `make test-no-skips` and an equivalent target for the other markers.
- `tests/unit/api/test_transcribe.py` and `tests/contract/test_bot_contract.py` still patch the private `ModelHolder._model`; they could load a fake model through `tests/support/whisper.py` (`loaded_model_holder`) instead.
- The three integration tests define the same `_PytesseractModule` protocol; it could move to `tests/support/`.
- `tests/unit/common/test_subprocess_runner.py` polls with `time.sleep` until an orphaned grandchild process disappears, because there is no portable notification for a process that is not a direct child. Revisit when the subprocess runner tests are reworked in AD-07.

## Released

- 0.2.0 (2026-11-12): CLI, Docker deployment, stable error codes. See [CHANGELOG.md](CHANGELOG.md).
