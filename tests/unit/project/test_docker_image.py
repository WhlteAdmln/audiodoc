# Copyright (c) 2026 Nikolai Zelensky
"""Regression tests for the Docker image configuration."""

from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[3]


def test_dockerfile_builds_a_multi_stage_python_image() -> None:
    """Ensure the image uses a Python builder and runtime stage."""
    dockerfile = (ROOT_DIR / "Dockerfile").read_text(encoding="utf-8")

    assert dockerfile.startswith("ARG RUNTIME_BASE=python:3.12-slim\n")
    expected_fragment = "FROM python:3.12-slim AS builder\n"
    assert expected_fragment in dockerfile
    expected_fragment = "FROM ${RUNTIME_BASE} AS runtime\n"
    assert expected_fragment in dockerfile
    expected_fragment = "requirements-lock.txt"
    assert expected_fragment in dockerfile
    expected_fragment = "pip wheel"
    assert expected_fragment in dockerfile
    expected_fragment = "--no-index"
    assert expected_fragment in dockerfile
    expected_fragment = "--find-links=/wheels"
    assert expected_fragment in dockerfile
    expected_fragment = "python -m venv /opt/venv"
    assert expected_fragment in dockerfile


def test_dockerfile_declares_ghcr_source_repository() -> None:
    """Ensure the image metadata identifies its source repository."""
    dockerfile = (ROOT_DIR / "Dockerfile").read_text(encoding="utf-8")
    expected_label = (
        'LABEL org.opencontainers.image.source="https://github.com/WhlteAdmln/audiodoc"'
    )

    assert expected_label in dockerfile


def test_dockerfile_installs_native_document_dependencies() -> None:
    """Ensure OCR languages and DjVuLibre tools are installed."""
    dockerfile = (ROOT_DIR / "Dockerfile").read_text(encoding="utf-8")

    for package in (
        "tesseract-ocr",
        "tesseract-ocr-rus",
        "tesseract-ocr-eng",
        "djvulibre-bin",
    ):
        assert package in dockerfile


def test_dockerfile_uses_persistent_storage_and_non_root_user() -> None:
    """Ensure application data is persistent and the process is unprivileged."""
    dockerfile = (ROOT_DIR / "Dockerfile").read_text(encoding="utf-8")

    expected_fragment = "AUDIODOC_HOME=/data"
    assert expected_fragment in dockerfile
    expected_fragment = "HF_HOME=/data/models"
    assert expected_fragment in dockerfile
    expected_fragment = 'VOLUME ["/data"]'
    assert expected_fragment in dockerfile
    expected_fragment = "USER audiodoc:audiodoc"
    assert expected_fragment in dockerfile


def test_dockerfile_configures_healthcheck_and_server_command() -> None:
    """Ensure Docker can monitor the API and start the server."""
    dockerfile = (ROOT_DIR / "Dockerfile").read_text(encoding="utf-8")

    expected_fragment = "HEALTHCHECK"
    assert expected_fragment in dockerfile
    expected_fragment = "http://127.0.0.1:8000/health"
    assert expected_fragment in dockerfile
    expected_fragment = 'CMD ["audiodoc", "run", "--host", "0.0.0.0"]'
    assert expected_fragment in dockerfile


def test_dockerignore_excludes_secrets_and_local_state() -> None:
    """Ensure secrets and development artifacts stay outside the build context."""
    ignored = set((ROOT_DIR / ".dockerignore").read_text(encoding="utf-8").splitlines())

    assert {
        ".git/",
        ".cache/",
        ".env",
        ".env.*",
        "!.env.example",
        ".venv/",
        "venv/",
        "models/",
        "tests/",
    } <= ignored


def test_docker_entrypoint_uses_keys_from_persistent_home() -> None:
    """Ensure host environment keys cannot mask keys generated in the volume."""
    entrypoint = (ROOT_DIR / "docker-entrypoint.sh").read_text(encoding="utf-8")

    for key in ("AUDIODOC_AUDIO_KEY", "AUDIODOC_DOCUMENT_KEY"):
        assert f"unset {key}" in entrypoint
    expected_fragment = 'exec "$@"'
    assert expected_fragment in entrypoint


def test_docker_entrypoint_dispatches_cli_subcommands() -> None:
    """Ensure entrypoint routes Compose subcommands through the CLI."""
    entrypoint = (ROOT_DIR / "docker-entrypoint.sh").read_text(encoding="utf-8")

    expected_fragment = 'if [ "${1:-}" != "audiodoc" ]; then'
    assert expected_fragment in entrypoint
    expected_fragment = 'set -- audiodoc "$@"'
    assert expected_fragment in entrypoint
    expected_fragment = 'exec "$@"'
    assert expected_fragment in entrypoint


def test_compose_configures_secure_persistent_storage() -> None:
    """Ensure Compose uses persistent data and safe container defaults."""
    compose = (ROOT_DIR / "compose.yaml").read_text(encoding="utf-8")

    for setting in (
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
    ):
        assert setting in compose

    expected_fragment = "pids_limit:"
    assert expected_fragment not in compose


def test_cuda_compose_uses_nvidia_runtime_and_reserves_gpu_devices() -> None:
    """Ensure the CUDA override selects an NVIDIA runtime and GPU devices."""
    compose = (ROOT_DIR / "compose.cuda.yaml").read_text(encoding="utf-8")

    expected_fragment = "nvidia/cuda:12.8.1-cudnn-runtime-ubuntu24.04"
    assert expected_fragment in compose
    expected_fragment = "WHISPER_DEVICE: cuda"
    assert expected_fragment in compose
    expected_fragment = "WHISPER_COMPUTE_TYPE: float16"
    assert expected_fragment in compose
    expected_fragment = "driver: nvidia"
    assert expected_fragment in compose
    expected_fragment = "count: all"
    assert expected_fragment in compose
    expected_fragment = "- gpu"
    assert expected_fragment in compose


def test_ci_builds_checks_and_publishes_the_container_image() -> None:
    """Ensure CI runs doctor in the image and publishes it to GHCR."""
    workflow = (ROOT_DIR / ".github" / "workflows" / "ci.yml").read_text(
        encoding="utf-8"
    )
    makefile = (ROOT_DIR / "Makefile").read_text(encoding="utf-8")

    expected_fragment = "name: Docker image smoke test"
    assert expected_fragment in workflow
    expected_fragment = "docker compose -f compose.yaml config --quiet"
    assert expected_fragment in makefile
    expected_fragment = (
        "docker compose -f compose.yaml -f compose.cuda.yaml config --quiet"
    )
    assert expected_fragment in makefile
    expected_fragment = "docker compose -f compose.yaml build --pull audiodoc"
    assert expected_fragment in makefile
    expected_fragment = "path: .cache/whisper"
    assert expected_fragment in workflow
    expected_fragment = "whisper-tiny-${{ hashFiles('requirements-lock.txt') }}"
    assert expected_fragment in workflow
    expected_fragment = ".cache/whisper:/data/models"
    assert expected_fragment in workflow
    expected_fragment = "audiodoc model download --name tiny --dir /data/models/tiny"
    assert expected_fragment in workflow
    expected_fragment = "WHISPER_MODEL_PATH=/data/models/tiny"
    assert expected_fragment in workflow
    expected_fragment_2 = (
        "      - name: Initialize persistent volume and run doctor\n"
        "        run: |\n"
        "          set -euo pipefail\n"
        "          docker compose -f compose.yaml run --rm --no-deps "
        "audiodoc init --model tiny\n"
    )
    assert expected_fragment_2 in workflow
    expected_fragment = "audiodoc doctor --offline"
    assert expected_fragment in workflow
    expected_fragment = "name: Publish Docker image to GHCR"
    assert expected_fragment not in workflow
    expected_fragment = "packages: write"
    assert expected_fragment in workflow
    expected_fragment = "GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}"
    assert expected_fragment in workflow
    expected_fragment = "docker login ghcr.io"
    assert expected_fragment in workflow
    expected_fragment = 'docker push "${image}:${GITHUB_SHA}"'
    assert expected_fragment in workflow
    expected_fragment = 'docker push "${image}:latest"'
    assert expected_fragment in workflow
    expected_fragment_2 = (
        "      - name: Make Whisper cache readable by runner\n"
        "        if: always()\n"
        "        run: |\n"
        "          if [[ -d .cache/whisper ]]; then\n"
        '            sudo chown -R "$(id -u):$(id -g)" .cache/whisper\n'
        "          fi\n"
    )
    assert expected_fragment_2 in workflow
