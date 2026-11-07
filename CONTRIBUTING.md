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
10. Open a pull request describing the change and the checks you ran. Do not include secrets, local environments, or generated build artifacts.
