# Copyright (c) 2026 Nikolai Zelensky
"""Regression tests for the Docker image configuration."""

from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[3]


def test_dockerfile_builds_a_multi_stage_python_image() -> None:
    dockerfile = (ROOT_DIR / "Dockerfile").read_text(encoding="utf-8")

    assert dockerfile.startswith("ARG RUNTIME_BASE=python:3.12-slim\n")
    builder_stage = "FROM python:3.12-slim AS builder\n"
    assert builder_stage in dockerfile
    runtime_stage = "FROM ${RUNTIME_BASE} AS runtime\n"
    assert runtime_stage in dockerfile
    lock_file = "requirements-lock.txt"
    assert lock_file in dockerfile
    wheel_build = "pip wheel"
    assert wheel_build in dockerfile
    offline_install = "--no-index"
    assert offline_install in dockerfile
    wheel_source = "--find-links=/wheels"
    assert wheel_source in dockerfile
    venv_creation = "python -m venv /opt/venv"
    assert venv_creation in dockerfile


def test_dockerfile_declares_ghcr_source_repository() -> None:
    dockerfile = (ROOT_DIR / "Dockerfile").read_text(encoding="utf-8")
    expected_label = (
        'LABEL org.opencontainers.image.source="https://github.com/WhlteAdmln/audiodoc"'
    )

    assert expected_label in dockerfile


def test_dockerfile_installs_native_document_dependencies() -> None:
    dockerfile = (ROOT_DIR / "Dockerfile").read_text(encoding="utf-8")

    for package in (
        "tesseract-ocr",
        "tesseract-ocr-rus",
        "tesseract-ocr-eng",
        "djvulibre-bin",
    ):
        assert package in dockerfile


def test_dockerfile_uses_persistent_storage_and_non_root_user() -> None:
    dockerfile = (ROOT_DIR / "Dockerfile").read_text(encoding="utf-8")

    home_variable = "AUDIODOC_HOME=/data"
    assert home_variable in dockerfile
    model_cache_variable = "HF_HOME=/data/models"
    assert model_cache_variable in dockerfile
    data_volume = 'VOLUME ["/data"]'
    assert data_volume in dockerfile
    service_user = "USER audiodoc:audiodoc"
    assert service_user in dockerfile


def test_dockerfile_configures_healthcheck_and_server_command() -> None:
    dockerfile = (ROOT_DIR / "Dockerfile").read_text(encoding="utf-8")

    healthcheck = "HEALTHCHECK"
    assert healthcheck in dockerfile
    health_url = "http://127.0.0.1:8000/health"
    assert health_url in dockerfile
    server_command = 'CMD ["audiodoc", "run", "--host", "0.0.0.0"]'
    assert server_command in dockerfile


def test_dockerignore_excludes_secrets_and_local_state() -> None:
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
    entrypoint = (ROOT_DIR / "docker-entrypoint.sh").read_text(encoding="utf-8")

    for key in ("AUDIODOC_AUDIO_KEY", "AUDIODOC_DOCUMENT_KEY"):
        assert f"unset {key}" in entrypoint
    exec_line = 'exec "$@"'
    assert exec_line in entrypoint


def test_docker_entrypoint_dispatches_cli_subcommands() -> None:
    entrypoint = (ROOT_DIR / "docker-entrypoint.sh").read_text(encoding="utf-8")

    command_check = 'if [ "${1:-}" != "audiodoc" ]; then'
    assert command_check in entrypoint
    command_prefix = 'set -- audiodoc "$@"'
    assert command_prefix in entrypoint
    exec_line = 'exec "$@"'
    assert exec_line in entrypoint


def test_compose_configures_secure_persistent_storage() -> None:
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

    pids_limit = "pids_limit:"
    assert pids_limit not in compose


def test_cuda_compose_uses_nvidia_runtime_and_reserves_gpu_devices() -> None:
    compose = (ROOT_DIR / "compose.cuda.yaml").read_text(encoding="utf-8")

    cuda_base_image = "nvidia/cuda:12.8.1-cudnn-runtime-ubuntu24.04"
    assert cuda_base_image in compose
    cuda_device = "WHISPER_DEVICE: cuda"
    assert cuda_device in compose
    compute_type = "WHISPER_COMPUTE_TYPE: float16"
    assert compute_type in compose
    gpu_driver = "driver: nvidia"
    assert gpu_driver in compose
    gpu_count = "count: all"
    assert gpu_count in compose
    gpu_capability = "- gpu"
    assert gpu_capability in compose


def test_ci_smoke_tests_the_container_image_through_the_makefile() -> None:
    workflow = (ROOT_DIR / ".github" / "workflows" / "ci.yml").read_text(
        encoding="utf-8"
    )
    makefile = (ROOT_DIR / "Makefile").read_text(encoding="utf-8")

    smoke_test_step = "name: Docker image smoke test"
    assert smoke_test_step in workflow
    compose_check = "docker compose -f compose.yaml config --quiet"
    assert compose_check in makefile
    cuda_compose_check = (
        "docker compose -f compose.yaml -f compose.cuda.yaml config --quiet"
    )
    assert cuda_compose_check in makefile
    image_build = "docker compose -f compose.yaml build --pull audiodoc"
    assert image_build in makefile


def test_ci_caches_the_whisper_model_and_runs_doctor_in_the_container() -> None:
    workflow = (ROOT_DIR / ".github" / "workflows" / "ci.yml").read_text(
        encoding="utf-8"
    )

    cache_path = "path: .cache/whisper"
    assert cache_path in workflow
    cache_key = "whisper-tiny-${{ hashFiles('requirements-lock.txt') }}"
    assert cache_key in workflow
    cache_mount = ".cache/whisper:/data/models"
    assert cache_mount in workflow
    model_download = "audiodoc model download --name tiny --dir /data/models/tiny"
    assert model_download in workflow
    model_path = "WHISPER_MODEL_PATH=/data/models/tiny"
    assert model_path in workflow
    doctor_step = (
        "      - name: Initialize persistent volume and run doctor\n"
        "        run: |\n"
        "          set -euo pipefail\n"
        "          docker compose -f compose.yaml run --rm --no-deps "
        "audiodoc init --model tiny\n"
    )
    assert doctor_step in workflow
    offline_doctor = "audiodoc doctor --offline"
    assert offline_doctor in workflow
    cache_permissions_step = (
        "      - name: Make Whisper cache readable by runner\n"
        "        if: always()\n"
        "        run: |\n"
        "          if [[ -d .cache/whisper ]]; then\n"
        '            sudo chown -R "$(id -u):$(id -g)" .cache/whisper\n'
        "          fi\n"
    )
    assert cache_permissions_step in workflow


def test_ci_publishes_the_container_image_to_ghcr() -> None:
    workflow = (ROOT_DIR / ".github" / "workflows" / "ci.yml").read_text(
        encoding="utf-8"
    )

    publish_step = "name: Publish Docker image to GHCR"
    assert publish_step not in workflow
    packages_permission = "packages: write"
    assert packages_permission in workflow
    registry_auth_env = "GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}"
    assert registry_auth_env in workflow
    registry_login = "docker login ghcr.io"
    assert registry_login in workflow
    sha_push = 'docker push "${image}:${GITHUB_SHA}"'
    assert sha_push in workflow
    latest_push = 'docker push "${image}:latest"'
    assert latest_push in workflow
