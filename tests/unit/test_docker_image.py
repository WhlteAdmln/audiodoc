# Copyright (c) 2026 Nikolai Zelensky
"""Regression tests for the Docker image configuration."""

from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]


def test_dockerfile_builds_a_multi_stage_python_image() -> None:
    """Ensure the image uses a Python builder and runtime stage."""
    dockerfile = (ROOT_DIR / "Dockerfile").read_text(encoding="utf-8")

    assert dockerfile.startswith("ARG RUNTIME_BASE=python:3.12-slim\n")
    assert "FROM python:3.12-slim AS builder\n" in dockerfile
    assert "FROM ${RUNTIME_BASE} AS runtime\n" in dockerfile
    assert "requirements-lock.txt" in dockerfile
    assert "pip wheel" in dockerfile
    assert "--no-index" in dockerfile
    assert "--find-links=/wheels" in dockerfile
    assert "python -m venv /opt/venv" in dockerfile


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

    assert "AUDIODOC_HOME=/data" in dockerfile
    assert "HF_HOME=/data/models" in dockerfile
    assert 'VOLUME ["/data"]' in dockerfile
    assert "USER audiodoc:audiodoc" in dockerfile


def test_dockerfile_configures_healthcheck_and_server_command() -> None:
    """Ensure Docker can monitor the API and start the server."""
    dockerfile = (ROOT_DIR / "Dockerfile").read_text(encoding="utf-8")

    assert "HEALTHCHECK" in dockerfile
    assert "http://127.0.0.1:8000/health" in dockerfile
    assert 'CMD ["audiodoc", "run", "--host", "0.0.0.0"]' in dockerfile


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

    for key in (
        "AUDIODOC_AUDIO_KEY",
        "AUDIODOC_DOCUMENT_KEY",
        "WHISPER_API_KEY",
        "DOCUMENT_API_KEY",
    ):
        assert f"unset {key}" in entrypoint
    assert 'exec "$@"' in entrypoint


def test_docker_entrypoint_dispatches_cli_subcommands() -> None:
    """Ensure entrypoint routes Compose subcommands through the CLI."""
    entrypoint = (ROOT_DIR / "docker-entrypoint.sh").read_text(encoding="utf-8")

    assert 'if [ "${1:-}" != "audiodoc" ]; then' in entrypoint
    assert 'set -- audiodoc "$@"' in entrypoint
    assert 'exec "$@"' in entrypoint


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

    assert "pids_limit:" not in compose


def test_cuda_compose_uses_nvidia_runtime_and_reserves_gpu_devices() -> None:
    """Ensure the CUDA override selects an NVIDIA runtime and GPU devices."""
    compose = (ROOT_DIR / "compose.cuda.yaml").read_text(encoding="utf-8")

    assert "nvidia/cuda:12.8.1-cudnn-runtime-ubuntu24.04" in compose
    assert "WHISPER_DEVICE: cuda" in compose
    assert "WHISPER_COMPUTE_TYPE: float16" in compose
    assert "driver: nvidia" in compose
    assert "count: all" in compose
    assert "- gpu" in compose


def test_ci_builds_checks_and_publishes_the_container_image() -> None:
    """Ensure CI runs doctor in the image and publishes it to GHCR."""
    workflow = (ROOT_DIR / ".github" / "workflows" / "ci.yml").read_text(
        encoding="utf-8"
    )

    assert "name: Docker image smoke test" in workflow
    assert "docker compose -f compose.yaml build --pull audiodoc" in workflow
    assert "path: .cache/whisper" in workflow
    assert "whisper-tiny-${{ hashFiles('requirements-lock.txt') }}" in workflow
    assert ".cache/whisper:/data/models" in workflow
    assert "audiodoc model download --name tiny --dir /data/models/tiny" in workflow
    assert "WHISPER_MODEL_PATH=/data/models/tiny" in workflow
    assert (
        "docker compose -f compose.yaml run --rm --no-deps audiodoc init --model tiny"
        in workflow
    )
    assert "audiodoc doctor --offline" in workflow
    assert "name: Publish Docker image to GHCR" in workflow
    assert "packages: write" in workflow
    assert "GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}" in workflow
    assert "docker login ghcr.io" in workflow
    assert 'docker push "${image}:${GITHUB_SHA}"' in workflow
    assert 'docker push "${image}:latest"' in workflow
