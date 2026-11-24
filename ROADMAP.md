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

## Planned

### 0.4.x: alpha finishing

- One assert per test and a message on every assert in all tests, not only the security tests.
- Unusual inputs instead of `"x"` and `"foo"` in all tests.
- Remove the pylint `no-docstring-rgx` exemption for tests and the `D1` ignore for `tests/*`.
- Review the remaining production suppressions: `too-many-instance-attributes` in `config/settings.py` and `common/work_queue.py`.

### 0.5.0: beta

The scope is not defined yet.

## Backlog

- `install.sh --upgrade` leaves the paths of the staged `.venv.new` in the activated `.venv`: the shebang of `.venv/bin/audiodoc`, the `activate` scripts and `pyvenv.cfg` still point to `.venv.new`, so the systemd unit fails after an upgrade with `Failed to execute .../.venv/bin/audiodoc: No such file or directory` (seen when upgrading 0.2.0 to 0.3.0). bot-obormot fixed the same bug with `relocate_venv` in its `install.sh` (pull request #65); port it with a test that no file in `.venv` mentions `.venv.new` after an upgrade and that `audiodoc doctor --offline` runs from the swapped environment. Users download `install.sh` from `main`, so the fix applies without a new release.
- `audiodoc doctor` reports `FAIL API port: Port 8000 on 127.0.0.1 is unavailable: [Errno 98] Address already in use.` while the audiodoc service is running, because `check_port` tries to bind the port that the running service holds. Proposed solution: when the bind fails with `EADDRINUSE`, check whether audiodoc answers `/health` on that address and report that the port is used by the running service instead of a failure; this changes behavior.
- Add `scripts/docs_checks/markdown.py`, `links.py`, `russian.py` and their tests to the files checked by `scripts/check_vendored.py`; they are identical in both repositories since AD-03.
- The CI job with the latest allowed dependencies installs `-c requirements-lock.txt`, so its runtime packages are the locked ones, not the latest allowed; decide whether it should drop the constraint, as bot-obormot does.
- The CI test, integration and e2e steps repeat the skipped-test check in shell; they could call `make test-no-skips` and an equivalent target for the other markers.
- `configure_logging` keeps the `SecretsFilter` of its first call: a later call with other secrets adds no filter, so the new secrets are not redacted. Today it runs once per process; replacing the filter would change behavior.
- `tests/contract/test_bot_contract.py` still patches the private `ModelHolder._model`; it could load a fake model through `tests/support/whisper.py` (`loaded_model_holder`) instead.
- The three integration tests define the same `_PytesseractModule` protocol; it could move to `tests/support/`.
- An API key with non-ASCII characters can never authenticate: Starlette decodes the `Authorization` header as Latin-1, while `require_key` compares UTF-8 bytes. It fails closed. Decision: startup rejects such keys with a clear error message, and the documentation says that keys are ASCII.
- `WorkQueue` keeps its lifecycle (open, draining, closed) in a `_closed` flag and an `_idle` event; an explicit state enum would make `start` and `shutdown` easier to reason about. Decision: replace them with an explicit state enum.
- `extract_csv` lets `csv.Sniffer` pick any character as the delimiter, so a single-column file is split on a letter (in `single\ncolumn` the letter `n` becomes the delimiter, so the first row is `si | gle`). Restricting the sniffer to `,;\t|` would fix it; this changes behavior.
- `extract_csv` raises `csv.Error` for a cell longer than `csv.field_size_limit()` (131072 characters); the pipeline reports it as a generic extraction failure.
- `extract_xml_text` reads only `element.text` and drops tail text, so `<r><b>one</b>tail</r>` gives `one`.
- The Tesseract proxy decodes the output as strict UTF-8, so invalid bytes raise `UnicodeDecodeError` instead of a client-safe OCR error; the pipeline reports a generic extraction failure.
- An image whose header declares more than Pillow's decompression bomb threshold (about 179 million pixels) raises `PIL.Image.DecompressionBombError` in `extract_image_text` instead of `ImageTooLargeError`; the pipeline reports a generic extraction failure.
- `check_bind_address` warns only for the spellings `0.0.0.0` and `::`; other spellings of the all-interfaces address (`0`, `::0`, `0:0:0:0:0:0:0:0`) report OK. Parsing the host with `ipaddress` and checking `is_unspecified` would fix it; this changes behavior.
- `tests/unit/test_config.py` still tests `log_safe` from `audiodoc/common/safe_log.py`, and `tests/unit/document_engine/test_pipeline.py` still tests the extractor registry, `runner.process_document` and the removal of `processor.py`; they belong in their mirrored test files.

## Released

- 0.3.0 (2026-11-24): deprecated functionality removed, code base aligned with bot-obormot, strict lint and test gates, Python 3.11.5 or newer. See [CHANGELOG.md](CHANGELOG.md).
- 0.2.0 (2026-11-12): CLI, Docker deployment, stable error codes. See [CHANGELOG.md](CHANGELOG.md).
