# Copyright (c) 2026 Nikolai Zelensky
"""Environment readers and application settings validation."""

from collections.abc import Iterator
from dataclasses import FrozenInstanceError, is_dataclass
from pathlib import Path

import pytest

from audiodoc.common.safe_log import log_safe
from audiodoc.config import (
    ConfigError,
    Settings,
    get_settings,
    load_settings,
    reset_settings_cache,
    settings,
)
from audiodoc.env_readers import (
    get_bool,
    get_float,
    get_int,
    get_log_level,
    get_optional_int,
    load_env_file,
    parse_ids,
)


def test_get_bool_accepts_common_spellings_and_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BOOL_SETTING", " YES ")
    assert get_bool("BOOL_SETTING") is True

    monkeypatch.setenv("BOOL_SETTING", "off")
    assert get_bool("BOOL_SETTING", default=True) is False

    monkeypatch.setenv("BOOL_SETTING", "  ")
    assert get_bool("BOOL_SETTING", default=True) is True


def test_get_bool_rejects_invalid_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BOOL_SETTING", "sometimes")
    with pytest.raises(ValueError, match="BOOL_SETTING"):
        get_bool("BOOL_SETTING")


def test_get_int_reads_default_environment_and_minimum(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("INT_SETTING", raising=False)
    expected_default = 6
    assert get_int("INT_SETTING", "6") == expected_default

    monkeypatch.setenv("INT_SETTING", "12")
    expected_from_environment = 12
    assert get_int("INT_SETTING", "6") == expected_from_environment

    with pytest.raises(ValueError, match="at least"):
        get_int("INT_SETTING", "6", minimum=13)


def test_get_float_enforces_finite_value_and_bounds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FLOAT_SETTING", "0.75")
    expected_get_float = 0.75
    assert get_float("FLOAT_SETTING", "0.5", minimum=0, maximum=1) == expected_get_float

    monkeypatch.setenv("FLOAT_SETTING", "nan")
    with pytest.raises(ValueError, match="finite number"):
        get_float("FLOAT_SETTING", "0.5")


def test_get_optional_int_reads_missing_blank_and_value() -> None:
    assert get_optional_int("OPTIONAL_INT", environ={}) is None
    assert get_optional_int("OPTIONAL_INT", environ={"OPTIONAL_INT": " "}) is None
    expected_get_optional_int = 3
    assert (
        get_optional_int("OPTIONAL_INT", environ={"OPTIONAL_INT": "3"})
        == expected_get_optional_int
    )

    with pytest.raises(ValueError, match="integer"):
        get_optional_int("OPTIONAL_INT", environ={"OPTIONAL_INT": "invalid"})

    with pytest.raises(ValueError, match="at least"):
        get_optional_int("OPTIONAL_INT", environ={"OPTIONAL_INT": "0"})


def test_parse_ids_reads_unique_positive_ids() -> None:
    assert parse_ids("ALLOWED_IDS", environ={}) == set()
    assert parse_ids("ALLOWED_IDS", environ={"ALLOWED_IDS": "1, 2,,2"}) == {1, 2}

    with pytest.raises(ValueError, match="invalid ID"):
        parse_ids("ALLOWED_IDS", environ={"ALLOWED_IDS": "1,no"})

    with pytest.raises(ValueError, match="must be positive"):
        parse_ids("ALLOWED_IDS", environ={"ALLOWED_IDS": "0"})


def test_get_log_level_validates_values_and_warns_on_invalid_value() -> None:
    expected_level = "WARNING"
    assert get_log_level(environ={"LOG_LEVEL": " warning "}) == expected_level

    expected_fallback_level = "INFO"
    with pytest.warns(RuntimeWarning, match="Invalid LOG_LEVEL"):
        assert get_log_level(environ={"LOG_LEVEL": "trace"}) == expected_fallback_level


def test_log_safe_removes_line_breaks_and_non_printable_characters() -> None:
    expected_log_safe = "user\\nname\\r?"
    assert log_safe("user\nname\r\x00", limit=30) == expected_log_safe


def test_load_settings_uses_supplied_environment_and_normalizes_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("WHISPER_MODEL_SIZE", "global-value")

    loaded = load_settings(
        {
            "WHISPER_MODEL_SIZE": "large",
            "WHISPER_CPU_THREADS": "8",
            "WHISPER_DEVICE": " CUDA ",
            "WHISPER_COMPUTE_TYPE": " float16 ",
            "WHISPER_MODEL_PATH": " /models/whisper ",
            "WHISPER_OFFLINE": "yes",
            "AUDIODOC_AUDIO_KEY": " whisper-key ",
            "AUDIODOC_DOCUMENT_KEY": " document-key ",
        }
    )

    expected_whisper_model_size = "large"
    assert expected_whisper_model_size == loaded.WHISPER_MODEL_SIZE
    expected_whisper_cpu_threads = 8
    assert expected_whisper_cpu_threads == loaded.WHISPER_CPU_THREADS
    expected_whisper_device = "cuda"
    assert expected_whisper_device == loaded.WHISPER_DEVICE
    expected_whisper_compute_type = "float16"
    assert expected_whisper_compute_type == loaded.WHISPER_COMPUTE_TYPE
    expected_whisper_model_path = "/models/whisper"
    assert expected_whisper_model_path == loaded.WHISPER_MODEL_PATH
    assert loaded.WHISPER_OFFLINE is True
    expected_audiodoc_audio_key = "whisper-key"
    assert expected_audiodoc_audio_key == loaded.AUDIODOC_AUDIO_KEY
    expected_audiodoc_document_key = "document-key"
    assert expected_audiodoc_document_key == loaded.AUDIODOC_DOCUMENT_KEY
    assert loaded.MAX_AUDIO_SIZE == 25 * 1024 * 1024


@pytest.mark.parametrize(
    "name",
    [
        "WHISPER_CPU_THREADS",
        "WHISPER_BEAM_SIZE",
        "WHISPER_TIMEOUT",
        "MAX_AUDIO_SIZE",
        "MAX_AUDIO_DURATION",
        "MAX_CONCURRENT_TRANSCRIPTIONS",
        "MAX_WAITING_DOCUMENTS",
        "MAX_WAITING_TRANSCRIPTIONS",
    ],
)
def test_load_settings_rejects_each_invalid_integer(name: str) -> None:
    with pytest.raises(ConfigError, match=name):
        load_settings({name: "not-an-integer"})


@pytest.mark.parametrize(
    "name",
    [
        "WHISPER_CPU_THREADS",
        "WHISPER_BEAM_SIZE",
        "WHISPER_TIMEOUT",
        "MAX_AUDIO_SIZE",
        "MAX_AUDIO_DURATION",
        "MAX_CONCURRENT_TRANSCRIPTIONS",
        "MAX_WAITING_DOCUMENTS",
        "MAX_WAITING_TRANSCRIPTIONS",
    ],
)
def test_load_settings_rejects_each_integer_below_minimum(name: str) -> None:
    with pytest.raises(ConfigError, match=name):
        load_settings({name: "0"})


@pytest.mark.parametrize(
    "name",
    ["WHISPER_OFFLINE", "ENABLE_DOCS", "ALLOW_UNAUTHENTICATED"],
)
def test_load_settings_rejects_each_invalid_boolean(name: str) -> None:
    with pytest.raises(ConfigError, match=name):
        load_settings({name: "sometimes"})


def test_load_settings_collects_all_errors() -> None:
    with pytest.raises(ConfigError) as error:
        load_settings(
            {
                "WHISPER_CPU_THREADS": "invalid",
                "WHISPER_OFFLINE": "sometimes",
                "MAX_AUDIO_SIZE": "0",
            }
        )

    expected_count = 3
    assert len(error.value.errors) == expected_count
    assert all(
        name in str(error.value)
        for name in ("WHISPER_CPU_THREADS", "WHISPER_OFFLINE", "MAX_AUDIO_SIZE")
    )


def test_settings_is_a_frozen_slotted_dataclass() -> None:
    assert is_dataclass(Settings)
    assert hasattr(Settings, "__slots__")

    field_name = "WHISPER_MODEL_SIZE"
    with pytest.raises(FrozenInstanceError):
        setattr(Settings(), field_name, "large")


@pytest.fixture(name="fresh_settings_cache")
def fixture_fresh_settings_cache() -> Iterator[None]:
    """Start with an empty settings cache and leave none behind."""
    reset_settings_cache()
    yield
    reset_settings_cache()


@pytest.mark.usefixtures("fresh_settings_cache")
def test_settings_proxy_is_cached_and_resettable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with monkeypatch.context() as scoped:
        scoped.setenv("WHISPER_MODEL_SIZE", "first")
        cached_size = "first"
        assert cached_size == settings.WHISPER_MODEL_SIZE

        scoped.setenv("WHISPER_MODEL_SIZE", "second")
        cached_size = "first"
        assert cached_size == get_settings().WHISPER_MODEL_SIZE

        reset_settings_cache()
        reloaded_size = "second"
        assert reloaded_size == settings.WHISPER_MODEL_SIZE


@pytest.mark.usefixtures("fresh_settings_cache")
def test_settings_proxy_deletion_restores_cached_values() -> None:
    original = get_settings()

    settings.WHISPER_MODEL_SIZE = "temporary"
    settings.WHISPER_LANGUAGE = "temporary"

    del settings.WHISPER_MODEL_SIZE
    assert settings.WHISPER_MODEL_SIZE == original.WHISPER_MODEL_SIZE
    expected_whisper_language = "temporary"
    assert expected_whisper_language == settings.WHISPER_LANGUAGE

    del settings.WHISPER_LANGUAGE
    assert get_settings() is original


def test_load_settings_resolves_relative_paths_against_application_home(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    loaded = load_settings(
        {
            "AUDIODOC_HOME": str(home),
            "BACKEND_TEMP_DIR": "cache/audio",
            "WHISPER_MODEL_PATH": "models/small",
        }
    )

    assert str(home / "cache" / "audio") == loaded.TEMP_DIR
    assert str(home / "models" / "small") == loaded.WHISPER_MODEL_PATH

    defaults = load_settings({"AUDIODOC_HOME": str(home)})
    assert str(home / "tmp") == defaults.TEMP_DIR


def test_load_env_file_uses_home_then_working_directory_without_overriding(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls: list[tuple[Path, bool]] = []
    home = tmp_path / "home"
    working_dir = tmp_path / "working"
    working_dir.mkdir()
    monkeypatch.setenv("AUDIODOC_HOME", str(home))
    monkeypatch.chdir(working_dir)

    def fake_load_dotenv(path: Path, *, override: bool) -> bool:
        calls.append((path, override))
        return True

    monkeypatch.setattr("audiodoc.env_readers.load_dotenv", fake_load_dotenv)
    load_env_file()

    assert calls == [
        (home / ".env", False),
        (working_dir / ".env", False),
    ]


def test_load_env_file_uses_explicit_path_then_home_and_working_directory(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls: list[tuple[Path, bool]] = []
    env_file = tmp_path / "custom.env"
    home = tmp_path / "configured-home"
    working_dir = tmp_path / "working"
    working_dir.mkdir()
    monkeypatch.delenv("AUDIODOC_HOME", raising=False)
    monkeypatch.chdir(working_dir)

    def fake_load_dotenv(path: Path, *, override: bool) -> bool:
        calls.append((path, override))
        if path == env_file:
            monkeypatch.setenv("AUDIODOC_HOME", str(home))
        return True

    monkeypatch.setattr("audiodoc.env_readers.load_dotenv", fake_load_dotenv)

    load_env_file(env_file)

    assert calls == [
        (env_file, False),
        (home / ".env", False),
        (working_dir / ".env", False),
    ]
