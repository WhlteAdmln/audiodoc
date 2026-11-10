# Adding a document format

Keep the detector, extractor registry, limits, tests, and public documentation in sync. Do not change the existing HTTP response fields used by the Telegram bot.

1. **Register detection.** In `audiodoc/document_engine/detection/formats.py`, add the format code and extension. Add a signature in `signatures.py` when the format has a reliable one. Preserve the detector's ordering and existing image rejection behavior.
2. **Create an extractor.** Add `audiodoc/document_engine/extractors/<name>.py` with a typed public function following the current extractor contract. It receives raw bytes and `ExtractContext`, adds output through `ctx.budget.add(...)`, exits when `ctx.budget.exhausted` is true, and checks `ctx.deadline.check()` inside potentially long loops. Validate containers before passing data to third-party parsers.
3. **Register the extractor.** Import it in `audiodoc/document_engine/extractors/__init__.py` and add its format code to `REGISTRY`. Keep extractors independent of FastAPI, transcription, and settings.
4. **Add a reproducible fixture and tests.** Put document builders in `tests/support/builders.py`; maintain backward-compatible exports in `tests/builders.py` where needed. Add focused unit tests under `tests/unit/`. Add integration coverage only when an external system program or model is required. Cover malformed input, budget exhaustion, and deadline checks where applicable.

   Every key in `REGISTRY` must have exactly one row in `tests/unit/test_extractor_matrix.py`. Each row covers a normal file, an empty file, malformed input, Unicode text (Cyrillic and emoji), and a file that reaches the text limit. The registry/matrix consistency test prevents a new format from being registered without matrix coverage. Tolerant text formats must convert malformed input without an uncaught exception; structured formats must return a clean `BackendError` without parser details or a traceback.

5. **Update documentation.** Add the format to the supported-format sections in `docs/api.md`, `README.md`, and `README.ru.md`. Explain any required OS package in `docs/operations.md` and add a `/ready` diagnostic when the format depends on a native executable.

Run both test commands before returning the change:

```bash
python -m pytest -q
python -m pytest -q -m integration
