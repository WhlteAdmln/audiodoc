# Copyright (c) 2026 Nikolai Zelensky
"""Regression tests for the Docker image configuration."""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parents[3]


def _read(*parts: str) -> str:
    return ROOT_DIR.joinpath(*parts).read_text(encoding="utf-8")


def _directives(text: str, keyword: str) -> list[str]:
    prefix = f"{keyword} "
    return [line for line in text.splitlines() if line.startswith(prefix)]


def test_dockerfile_starts_with_the_runtime_base_argument() -> None:
    dockerfile = _read("Dockerfile")
    expected_first_line = "ARG RUNTIME_BASE=python:3.12-slim\n"

    assert dockerfile.startswith(expected_first_line), (
        "the Dockerfile does not start with the runtime base argument"
    )


@pytest.mark.parametrize(
    "snippet",
    [
        "FROM python:3.12-slim AS builder\n",
        "FROM ${RUNTIME_BASE} AS runtime\n",
        "requirements-lock.txt",
        "pip wheel",
        "--no-index",
        "--find-links=/wheels",
        "python -m venv /opt/venv",
    ],
)
def test_dockerfile_builds_a_multi_stage_offline_python_image(snippet: str) -> None:
    dockerfile = _read("Dockerfile")

    assert snippet in dockerfile, f"the Dockerfile build misses {snippet!r}"


def test_dockerfile_declares_ghcr_source_repository() -> None:
    dockerfile = _read("Dockerfile")
    expected_label = (
        'LABEL org.opencontainers.image.source="https://github.com/WhlteAdmln/audiodoc"'
    )

    assert expected_label in dockerfile, "the GHCR source label is missing"


@pytest.mark.parametrize(
    "package",
    ["tesseract-ocr", "tesseract-ocr-rus", "tesseract-ocr-eng", "djvulibre-bin"],
)
def test_dockerfile_installs_native_document_dependencies(package: str) -> None:
    dockerfile = _read("Dockerfile")

    assert package in dockerfile, f"the image does not install {package}"


@pytest.mark.parametrize(
    "snippet",
    [
        "AUDIODOC_HOME=/data",
        "HF_HOME=/data/models",
        'VOLUME ["/data"]',
        "USER audiodoc:audiodoc",
    ],
)
def test_dockerfile_uses_persistent_storage_and_non_root_user(snippet: str) -> None:
    dockerfile = _read("Dockerfile")

    assert snippet in dockerfile, f"the Dockerfile misses {snippet!r}"


def test_dockerfile_switches_to_the_service_user_last() -> None:
    dockerfile = _read("Dockerfile")
    expected_users = ["USER audiodoc:audiodoc"]

    users = _directives(dockerfile, "USER")

    assert users == expected_users, "the image may run as root at the end"


def test_dockerfile_copies_no_secrets_or_whole_build_context() -> None:
    dockerfile = _read("Dockerfile")
    env_file_name = ".env"
    whole_context = ("COPY . ", "COPY ./ ")
    expected_empty: list[str] = []

    risky = [
        line
        for line in _directives(dockerfile, "COPY")
        if env_file_name in line or line.startswith(whole_context)
    ]

    assert risky == expected_empty, "the image copies secrets or the whole context"


@pytest.mark.parametrize(
    "snippet",
    [
        "HEALTHCHECK",
        "http://127.0.0.1:8000/health",
        'CMD ["audiodoc", "run", "--host", "0.0.0.0"]',
    ],
)
def test_dockerfile_configures_healthcheck_and_server_command(snippet: str) -> None:
    dockerfile = _read("Dockerfile")

    assert snippet in dockerfile, f"the Dockerfile misses {snippet!r}"


def test_dockerignore_excludes_secrets_and_local_state() -> None:
    ignored = set(_read(".dockerignore").splitlines())
    required = {
        ".git/",
        ".cache/",
        ".env",
        ".env.*",
        "!.env.example",
        ".venv/",
        "venv/",
        "models/",
        "tests/",
    }
    expected_empty: set[str] = set()

    assert required - ignored == expected_empty, ".dockerignore misses entries"


@pytest.mark.parametrize(
    "snippet",
    ["unset AUDIODOC_AUDIO_KEY", "unset AUDIODOC_DOCUMENT_KEY", 'exec "$@"'],
)
def test_docker_entrypoint_uses_keys_from_persistent_home(snippet: str) -> None:
    entrypoint = _read("docker-entrypoint.sh")

    assert snippet in entrypoint, f"the entrypoint misses {snippet!r}"


@pytest.mark.parametrize(
    "snippet",
    [
        'if [ "${1:-}" != "audiodoc" ]; then',
        'set -- audiodoc "$@"',
        'exec "$@"',
    ],
)
def test_docker_entrypoint_dispatches_cli_subcommands(snippet: str) -> None:
    entrypoint = _read("docker-entrypoint.sh")

    assert snippet in entrypoint, f"the entrypoint misses {snippet!r}"


@pytest.mark.parametrize(
    "setting",
    [
        "env_file:",
        "      - .env",
        "AUDIODOC_HOME: /data",
        "HF_HOME: /data/models",
        "read_only: true",
        "restart: unless-stopped",
        "audiodoc_data:/data",
        "tmpfs:",
        "noexec,nosuid,nodev",
        "size=256m",
        "127.0.0.1",
        "deploy:",
        'cpus: "${AUDIODOC_CPU_LIMIT:-2.0}"',
        "memory:",
        "pids: 256",
        "cap_drop:",
        "no-new-privileges:true",
    ],
)
def test_compose_configures_secure_persistent_storage(setting: str) -> None:
    compose = _read("compose.yaml")

    assert setting in compose, f"compose.yaml misses {setting!r}"


@pytest.mark.parametrize("setting", ["pids_limit:", "privileged: true"])
def test_compose_avoids_legacy_and_privileged_settings(setting: str) -> None:
    compose = _read("compose.yaml")

    assert setting not in compose, f"compose.yaml must not contain {setting!r}"


@pytest.mark.parametrize(
    "snippet",
    [
        "nvidia/cuda:12.8.1-cudnn-runtime-ubuntu24.04",
        "WHISPER_DEVICE: cuda",
        "WHISPER_COMPUTE_TYPE: float16",
        "driver: nvidia",
        "count: all",
        "- gpu",
    ],
)
def test_cuda_compose_uses_nvidia_runtime_and_reserves_gpu_devices(
    snippet: str,
) -> None:
    compose = _read("compose.cuda.yaml")

    assert snippet in compose, f"compose.cuda.yaml misses {snippet!r}"


def test_ci_has_a_docker_image_smoke_test_step() -> None:
    workflow = _read(".github", "workflows", "ci.yml")
    smoke_test_step = "name: Docker image smoke test"

    assert smoke_test_step in workflow, "CI has no Docker image smoke test"


@pytest.mark.parametrize(
    "command",
    [
        "docker compose -f compose.yaml config --quiet",
        "docker compose -f compose.yaml -f compose.cuda.yaml config --quiet",
        "docker compose -f compose.yaml build --pull audiodoc",
    ],
)
def test_makefile_validates_and_builds_the_container_image(command: str) -> None:
    makefile = _read("Makefile")

    assert command in makefile, f"the Makefile misses {command!r}"


@pytest.mark.parametrize(
    "snippet",
    [
        "path: .cache/whisper",
        "whisper-tiny-${{ hashFiles('requirements-lock.txt') }}",
        ".cache/whisper:/data/models",
        "audiodoc model download --name tiny --dir /data/models/tiny",
        "WHISPER_MODEL_PATH=/data/models/tiny",
        (
            "      - name: Initialize persistent volume and run doctor\n"
            "        run: |\n"
            "          set -euo pipefail\n"
            "          docker compose -f compose.yaml run --rm --no-deps "
            "audiodoc init --model tiny\n"
        ),
        "audiodoc doctor --offline",
        (
            "      - name: Make Whisper cache readable by runner\n"
            "        if: always()\n"
            "        run: |\n"
            "          if [[ -d .cache/whisper ]]; then\n"
            '            sudo chown -R "$(id -u):$(id -g)" .cache/whisper\n'
            "          fi\n"
        ),
    ],
)
def test_ci_caches_the_whisper_model_and_runs_doctor_in_the_container(
    snippet: str,
) -> None:
    workflow = _read(".github", "workflows", "ci.yml")

    assert snippet in workflow, f"the CI workflow misses {snippet!r}"


def test_ci_has_no_separate_ghcr_publish_step() -> None:
    workflow = _read(".github", "workflows", "ci.yml")
    publish_step = "name: Publish Docker image to GHCR"

    assert publish_step not in workflow, "CI still has a separate publish step"


@pytest.mark.parametrize(
    "snippet",
    [
        "packages: write",
        "GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}",
        "docker login ghcr.io",
        'docker push "${image}:${GITHUB_SHA}"',
        'docker push "${image}:latest"',
    ],
)
def test_ci_publishes_the_container_image_to_ghcr(snippet: str) -> None:
    workflow = _read(".github", "workflows", "ci.yml")

    assert snippet in workflow, f"the CI workflow misses {snippet!r}"
