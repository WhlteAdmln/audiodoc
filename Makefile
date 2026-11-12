
PYTHON ?= $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)
VERSION ?= dev
PYTHON_SCRIPTS_DIR = $(shell $(PYTHON) -c "import sysconfig; print(sysconfig.get_path('scripts'))")

.PHONY: venv install-dev lint fix types deptry vulture import-lint test \
        test-integration test-e2e integration e2e audit build docker installer \
        cov docs-check contract check clean

venv:
	@if [ ! -x .venv/bin/python ]; then $(PYTHON) -m venv .venv; else echo "Virtual environment already exists"; fi

install-dev: venv
	.venv/bin/python -m pip install -r requirements-dev.txt

lint: docs-check
	$(PYTHON) -m ruff check .
	$(PYTHON) -m ruff format --check .
	$(PYTHON) scripts/check_lock.py
	$(PYTHON_SCRIPTS_DIR)/shfmt -i 0 -d install.sh
	find scripts -type f -name '*.sh' -exec $(PYTHON_SCRIPTS_DIR)/shfmt -i 2 -sr -d {} +
	find deploy -type f -name '*.sh' -exec $(PYTHON_SCRIPTS_DIR)/shfmt -i 2 -sr -d {} +
	find deploy -type f -name '*.sh.example' -exec $(PYTHON_SCRIPTS_DIR)/shfmt -i 2 -sr -d {} +
	$(PYTHON_SCRIPTS_DIR)/shellcheck $(shell git ls-files '*.sh' '*.sh.example')

fix:
	$(PYTHON) -m ruff check . --fix
	$(PYTHON) -m ruff format .

types:
	$(PYTHON) -m mypy audiodoc

deptry:
	$(PYTHON_SCRIPTS_DIR)/deptry .

vulture:
	$(PYTHON_SCRIPTS_DIR)/vulture

import-lint:
	$(PYTHON_SCRIPTS_DIR)/lint-imports

test:
	$(PYTHON) -m pytest -q -rs -m "not integration and not e2e" \
		--cov=audiodoc --cov-branch \
		--cov-report=term-missing:skip-covered \
		--cov-report=xml --cov-report=html --junitxml=junit.xml

test-integration:
	$(PYTHON) -m pytest -q -rs -m integration

test-e2e:
	$(PYTHON) -c "from faster_whisper.utils import download_model; download_model('tiny')"
	$(PYTHON) -m pytest -q -rs -m e2e

integration: test-integration

e2e: test-e2e

audit:
	$(PYTHON_SCRIPTS_DIR)/pip-audit -r requirements-lock.txt

docker:
	docker compose -f compose.yaml config --quiet
	docker compose -f compose.yaml -f compose.cuda.yaml config --quiet
	docker compose -f compose.yaml build --pull audiodoc

installer:
	$(PYTHON) -m pytest -q tests/unit/test_installer.py
	$(PYTHON) -m pytest -q tests/integration/legacy_installer_ci.py

cov:
	$(PYTHON) -m coverage xml --fail-under=0
	$(PYTHON) scripts/coverage_gaps.py
	$(PYTHON) -m coverage report --show-missing

docs-check:
	$(PYTHON) -m scripts.check_docs
	$(PYTHON) -m pre_commit run --all-files

contract:
	$(PYTHON) -m scripts.export_openapi

check: lint types deptry vulture import-lint test docs-check

build:
	bash scripts/build_release.sh "$(VERSION)"

clean:
	rm -rf .pytest_cache .ruff_cache .mypy_cache .coverage coverage.xml htmlcov junit.xml dist build
