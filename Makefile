PYTHON ?= $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)
VERSION ?= dev

.PHONY: venv install-dev lint fix types test test-integration cov docs-check check build clean

venv:
	@if [ ! -x .venv/bin/python ]; then $(PYTHON) -m venv .venv; else echo "Virtual environment already exists"; fi

install-dev: venv
	.venv/bin/python -m pip install -r requirements-dev.txt

lint:
	$(PYTHON) -m ruff check .
	$(PYTHON) -m ruff format --check .
	$(PYTHON) scripts/check_lock.py
	@command -v shellcheck >/dev/null 2>&1 || { echo "shellcheck is required; install it to lint install.sh" >&2; exit 1; }
	shellcheck --shell=sh install.sh

fix:
	$(PYTHON) -m ruff check . --fix
	$(PYTHON) -m ruff format .

types:
	$(PYTHON) -m mypy backend

test:
	$(PYTHON) -m pytest -q -rs -o addopts='' -m "not integration" \
		--cov=backend --cov-branch \
		--cov-report=term-missing:skip-covered

test-integration:
	$(PYTHON) -m pytest -q -rs -o addopts='' -m integration

cov:
	$(PYTHON) -m coverage report --show-missing

docs-check:
	@echo "Documentation checks are not configured yet."

check: lint types test

build:
	bash scripts/build_release.sh "$(VERSION)"

clean:
	rm -rf .pytest_cache .ruff_cache .mypy_cache .coverage coverage.xml htmlcov junit.xml dist build
