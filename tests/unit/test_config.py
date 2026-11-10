# Copyright (c) 2026 Nikolai Zelensky
"""Environment readers and application settings validation."""

from dataclasses import FrozenInstanceError, is_dataclass
from pathlib import Path

import pytest

from backend.common.safe_log import log_safe
from backend.config import (
    ConfigError,
    Settings,
    get_settings,
    load_settings,
    reset_settings_cache,
    settings,
)
from backend.config.env import load_env_file as legacy_load_env_file
from backend.config.paths import PROJECT_ROOT
from backend.env_readers import (
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
    assert get_int("INT_SETTING", "6") == 6

    monkeypatch.setenv("INT_SETTING", "12")
    assert get_int("INT_SETTING", "6") == 12

    with pytest.raises(ValueError, match="at least"):
        get_int("INT_SETTING", "6", minimum=13)


def test_get_float_enforces_finite_value_and_bounds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FLOAT_SETTING", "0.75")
    assert get_float("FLOAT_SETTING", "0.5", minimum=0, maximum=1) == 0.75

    monkeypatch.setenv("FLOAT_SETTING", "nan")
    with pytest.raises(ValueError, match="finite number"):
        get_float("FLOAT_SETTING", "0.5")


def test_get_optional_int_reads_missing_blank_and_value() -> None:
    assert get_optional_int("OPTIONAL_INT", environ={}) is None
    assert get_optional_int("OPTIONAL_INT", environ={"OPTIONAL_INT": " "}) is None
    assert get_optional_int("OPTIONAL_INT", environ={"OPTIONAL_INT": "3"}) == 3

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
    assert get_log_level(environ={"LOG_LEVEL": " warning "}) == "WARNING"

    with pytest.warns(RuntimeWarning, match="Invalid LOG_LEVEL"):
        assert get_log_level(environ={"LOG_LEVEL": "trace"}) == "INFO"


def test_legacy_environment_reader_module_reexports_vendored_functions() -> None:
    assert legacy_load_env_file is load_env_file


def test_log_safe_removes_line_breaks_and_non_printable_characters() -> None:
    assert log_safe("user\nname\r\x00", limit=30) == "user\\nname\\r?"


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

    assert loaded.WHISPER_MODEL_SIZE == "large"
    assert loaded.WHISPER_CPU_THREADS == 8
    assert loaded.WHISPER_DEVICE == "cuda"
    assert loaded.WHISPER_COMPUTE_TYPE == "float16"
    assert loaded.WHISPER_MODEL_PATH == "/models/whisper"
    assert loaded.WHISPER_OFFLINE is True
    assert loaded.AUDIODOC_AUDIO_KEY == "whisper-key"
    assert loaded.AUDIODOC_DOCUMENT_KEY == "document-key"
    assert loaded.WHISPER_API_KEY == "whisper-key"
    assert loaded.DOCUMENT_API_KEY == "document-key"
    assert loaded.MAX_AUDIO_SIZE == 25 * 1024 * 1024


def test_load_settings_falls_back_to_legacy_api_keys() -> None:
    loaded = load_settings(
        {
            "AUDIODOC_AUDIO_KEY": " ",
            "WHISPER_API_KEY": " legacy-audio ",
            "DOCUMENT_API_KEY": " legacy-document ",
        }
    )

    assert loaded.AUDIODOC_AUDIO_KEY == "legacy-audio"
    assert loaded.AUDIODOC_DOCUMENT_KEY == "legacy-document"
    assert loaded.deprecated_environment_names == (
        "WHISPER_API_KEY",
        "DOCUMENT_API_KEY",
    )


def test_load_settings_prefers_new_api_keys_when_both_names_are_set() -> None:
    loaded = load_settings(
        {
            "AUDIODOC_AUDIO_KEY": "new-audio",
            "WHISPER_API_KEY": "old-audio",
            "AUDIODOC_DOCUMENT_KEY": "new-document",
            "DOCUMENT_API_KEY": "old-document",
        }
    )

    assert loaded.AUDIODOC_AUDIO_KEY == "new-audio"
    assert loaded.AUDIODOC_DOCUMENT_KEY == "new-document"
    assert loaded.WHISPER_API_KEY == "new-audio"
    assert loaded.DOCUMENT_API_KEY == "new-document"
    assert loaded.deprecated_environment_names == ()


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

    assert len(error.value.errors) == 3
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


def test_settings_proxy_is_cached_and_resettable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reset_settings_cache()

    try:
        with monkeypatch.context() as scoped:
            scoped.setenv("WHISPER_MODEL_SIZE", "first")
            assert settings.WHISPER_MODEL_SIZE == "first"

            scoped.setenv("WHISPER_MODEL_SIZE", "second")
            assert get_settings().WHISPER_MODEL_SIZE == "first"

            reset_settings_cache()
            assert settings.WHISPER_MODEL_SIZE == "second"
    finally:
        reset_settings_cache()


def test_settings_proxy_deletion_restores_cached_values() -> None:
    reset_settings_cache()
    original = get_settings()

    try:
        settings.WHISPER_MODEL_SIZE = "temporary"
        settings.WHISPER_LANGUAGE = "temporary"

        del settings.WHISPER_MODEL_SIZE
        assert settings.WHISPER_MODEL_SIZE == original.WHISPER_MODEL_SIZE
        assert settings.WHISPER_LANGUAGE == "temporary"

        del settings.WHISPER_LANGUAGE
        assert get_settings() is original
    finally:
        reset_settings_cache()


def test_load_env_file_uses_project_file_without_overriding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[Path, bool]] = []

    def fake_load_dotenv(path: Path, *, override: bool) -> bool:
        calls.append((path, override))
        return True

    monkeypatch.setattr("backend.env_readers.load_dotenv", fake_load_dotenv)

    load_env_file()

    assert calls == [(PROJECT_ROOT / ".env", False)]
