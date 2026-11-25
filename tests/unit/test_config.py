# Copyright (c) 2026 Nikolai Zelensky
"""Environment readers and application settings validation."""

import os
from collections.abc import Iterator
from dataclasses import FrozenInstanceError, is_dataclass
from pathlib import Path

import pytest

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

INTEGER_SETTINGS = [
    "WHISPER_CPU_THREADS",
    "WHISPER_BEAM_SIZE",
    "WHISPER_TIMEOUT",
    "MAX_AUDIO_SIZE",
    "MAX_AUDIO_DURATION",
    "MAX_CONCURRENT_TRANSCRIPTIONS",
    "MAX_WAITING_DOCUMENTS",
    "MAX_WAITING_TRANSCRIPTIONS",
]


def _clear_environment(monkeypatch: pytest.MonkeyPatch, *names: str) -> None:
    for name in names:
        monkeypatch.setenv(name, "")
        monkeypatch.delenv(name)


@pytest.fixture(name="fresh_settings_cache")
def fixture_fresh_settings_cache() -> Iterator[None]:
    """Start with an empty settings cache and leave none behind."""
    reset_settings_cache()
    yield
    reset_settings_cache()


@pytest.mark.parametrize("raw", [" YES ", "1", "True", "on"])
def test_get_bool_reads_true_spellings_from_the_process_environment(
    monkeypatch: pytest.MonkeyPatch, raw: str
) -> None:
    monkeypatch.setenv("BOOL_SETTING", raw)

    value = get_bool("BOOL_SETTING")

    assert value is True, f"{raw!r} was not read as true"


@pytest.mark.parametrize("raw", ["off", "0", " FALSE", "No"])
def test_get_bool_reads_false_spellings_over_a_true_default(raw: str) -> None:
    environ = {"FLAG_X": raw}

    value = get_bool("FLAG_X", default=True, environ=environ)

    assert value is False, f"{raw!r} was not read as false"


@pytest.mark.parametrize("environ", [{}, {"TOGGLE_Q": "  \t"}])
def test_get_bool_returns_the_default_for_a_missing_or_blank_value(
    environ: dict[str, str],
) -> None:
    value = get_bool("TOGGLE_Q", default=True, environ=environ)

    assert value is True, "a missing or blank boolean ignored the default"


@pytest.mark.parametrize("raw", ["sometimes", "yes\x00", "true!", "2", "y"])
def test_get_bool_rejects_an_unknown_spelling(raw: str) -> None:
    environ = {"BOOL_SETTING": raw}

    with pytest.raises(ValueError, match=r".") as caught:
        get_bool("BOOL_SETTING", environ=environ)

    expected = f"Setting BOOL_SETTING must be true or false. Got: {raw!r}"
    assert str(caught.value) == expected, "an unknown boolean was not rejected"


def test_get_int_returns_the_default_for_a_missing_variable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("INT_SETTING", raising=False)
    expected = 6

    value = get_int("INT_SETTING", "6")

    assert value == expected, "a missing integer ignored the default"


def test_get_int_reads_the_process_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("INT_SETTING", "12")
    expected = 12

    value = get_int("INT_SETTING", "6")

    assert value == expected, "the integer from the environment was not read"


def test_get_int_rejects_a_value_below_the_minimum(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("INT_SETTING", "12")

    with pytest.raises(ValueError, match=r".") as caught:
        get_int("INT_SETTING", "6", minimum=13)

    expected = "Setting INT_SETTING must be at least 13. Got: 12"
    assert str(caught.value) == expected, "a too small integer was accepted"


@pytest.mark.parametrize("raw", ["seven", "2.5", "", "0x10", "9" * 5000])
def test_get_int_rejects_a_value_that_is_not_an_integer(raw: str) -> None:
    environ = {"LIMIT_N": raw}

    with pytest.raises(ValueError, match=r".") as caught:
        get_int("LIMIT_N", "3", environ=environ)

    expected = f"Setting LIMIT_N must be an integer. Got: {raw!r}"
    assert str(caught.value) == expected, "a non-integer was accepted"


def test_get_float_reads_a_value_within_bounds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FLOAT_SETTING", "0.75")
    expected = 0.75

    value = get_float("FLOAT_SETTING", "0.5", minimum=0, maximum=1)

    assert value == expected, "a float within bounds was not read"


@pytest.mark.parametrize("raw", ["nan", "inf", "-Infinity"])
def test_get_float_rejects_a_value_that_is_not_finite(raw: str) -> None:
    environ = {"RATIO_F": raw}

    with pytest.raises(ValueError, match=r".") as caught:
        get_float("RATIO_F", "0.5", environ=environ)

    expected = f"Setting RATIO_F must be a finite number. Got: {raw!r}"
    assert str(caught.value) == expected, "a non-finite float was accepted"


def test_get_float_rejects_a_value_that_is_not_a_number() -> None:
    environ = {"RATIO_G": "half"}

    with pytest.raises(ValueError, match=r".") as caught:
        get_float("RATIO_G", "0.5", environ=environ)

    expected = "Setting RATIO_G must be a number. Got: 'half'"
    assert str(caught.value) == expected, "a non-number was accepted"


def test_get_float_rejects_a_value_below_the_minimum() -> None:
    environ = {"RATIO_H": "-0.01"}

    with pytest.raises(ValueError, match=r".") as caught:
        get_float("RATIO_H", "0.5", minimum=0, maximum=1, environ=environ)

    expected = "Setting RATIO_H must be at least 0. Got: -0.01"
    assert str(caught.value) == expected, "a too small float was accepted"


def test_get_float_rejects_a_value_above_the_maximum() -> None:
    environ = {"RATIO_K": "1.5"}

    with pytest.raises(ValueError, match=r".") as caught:
        get_float("RATIO_K", "0.5", minimum=0, maximum=1, environ=environ)

    expected = "Setting RATIO_K must be at most 1. Got: 1.5"
    assert str(caught.value) == expected, "a too large float was accepted"


@pytest.mark.parametrize("environ", [{}, {"OPTIONAL_INT": " "}])
def test_get_optional_int_returns_none_for_a_missing_or_blank_value(
    environ: dict[str, str],
) -> None:
    value = get_optional_int("OPTIONAL_INT", environ=environ)

    assert value is None, "a missing or blank optional integer was not None"


def test_get_optional_int_reads_a_value() -> None:
    environ = {"OPTIONAL_INT": "3"}
    expected = 3

    value = get_optional_int("OPTIONAL_INT", environ=environ)

    assert value == expected, "the optional integer was not read"


def test_get_optional_int_rejects_a_value_that_is_not_an_integer() -> None:
    environ = {"OPTIONAL_INT": "invalid"}

    with pytest.raises(ValueError, match=r".") as caught:
        get_optional_int("OPTIONAL_INT", environ=environ)

    expected = "Setting OPTIONAL_INT must be an integer. Got: 'invalid'"
    assert str(caught.value) == expected, "a non-integer was accepted"


@pytest.mark.parametrize("raw", ["0", "-4"])
def test_get_optional_int_rejects_a_value_below_the_minimum(raw: str) -> None:
    environ = {"OPTIONAL_INT": raw}

    with pytest.raises(ValueError, match=r".") as caught:
        get_optional_int("OPTIONAL_INT", environ=environ)

    expected = f"Setting OPTIONAL_INT must be at least 1. Got: {raw}"
    assert str(caught.value) == expected, "a too small optional integer passed"


def test_parse_ids_returns_an_empty_set_for_a_missing_variable() -> None:
    expected_empty: set[int] = set()

    value = parse_ids("ALLOWED_IDS", environ={})

    assert value == expected_empty, "a missing ID list was not empty"


def test_parse_ids_reads_unique_ids_and_skips_empty_items() -> None:
    environ = {"ALLOWED_IDS": "1, 2,,2"}
    expected = {1, 2}

    value = parse_ids("ALLOWED_IDS", environ=environ)

    assert value == expected, "the ID list was not parsed"


@pytest.mark.parametrize("item", ["no", "1.5", "7;8"])
def test_parse_ids_rejects_an_item_that_is_not_an_integer(item: str) -> None:
    environ = {"ALLOWED_IDS": f"1,{item}"}

    with pytest.raises(ValueError, match=r".") as caught:
        parse_ids("ALLOWED_IDS", environ=environ)

    expected = f"Setting ALLOWED_IDS contains an invalid ID: {item!r}"
    assert str(caught.value) == expected, "an invalid ID was accepted"


@pytest.mark.parametrize("item", ["0", "-42"])
def test_parse_ids_rejects_an_id_that_is_not_positive(item: str) -> None:
    environ = {"ALLOWED_IDS": item}

    with pytest.raises(ValueError, match=r".") as caught:
        parse_ids("ALLOWED_IDS", environ=environ)

    expected = f"ID in setting ALLOWED_IDS must be positive: {item}"
    assert str(caught.value) == expected, "a non-positive ID was accepted"


def test_get_log_level_normalizes_a_valid_value() -> None:
    environ = {"LOG_LEVEL": " warning "}
    expected = "WARNING"

    value = get_log_level(environ=environ)

    assert value == expected, "a valid log level was not normalized"


def test_get_log_level_warns_and_falls_back_for_an_invalid_value() -> None:
    environ = {"LOG_LEVEL": "trace"}
    expected = "INFO"

    with pytest.warns(RuntimeWarning, match="Invalid LOG_LEVEL"):
        value = get_log_level(environ=environ)

    assert value == expected, "an invalid log level did not fall back to INFO"


def test_load_settings_uses_the_supplied_environment_and_normalizes_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("WHISPER_MODEL_SIZE", "global-value")
    environ = {
        "WHISPER_MODEL_SIZE": "large",
        "WHISPER_CPU_THREADS": "8",
        "WHISPER_DEVICE": " CUDA ",
        "WHISPER_COMPUTE_TYPE": " float16 ",
        "WHISPER_MODEL_PATH": " /models/whisper ",
        "WHISPER_OFFLINE": "yes",
        "AUDIODOC_AUDIO_KEY": " whisper-key ",
        "AUDIODOC_DOCUMENT_KEY": " document-key ",
    }
    expected = ("large", 8, "cuda", "float16", "/models/whisper", True)
    expected += ("whisper-key", "document-key")

    loaded = load_settings(environ)

    actual = (
        loaded.WHISPER_MODEL_SIZE,
        loaded.WHISPER_CPU_THREADS,
        loaded.WHISPER_DEVICE,
        loaded.WHISPER_COMPUTE_TYPE,
        loaded.WHISPER_MODEL_PATH,
        loaded.WHISPER_OFFLINE,
        loaded.AUDIODOC_AUDIO_KEY,
        loaded.AUDIODOC_DOCUMENT_KEY,
    )
    assert actual == expected, "supplied settings were not read or normalized"


def test_load_settings_uses_the_default_audio_size_limit() -> None:
    expected = 25 * 1024 * 1024

    loaded = load_settings({})

    assert expected == loaded.MAX_AUDIO_SIZE, "the default audio limit changed"


@pytest.mark.parametrize("raw", ["   ", "\t\n"])
def test_load_settings_reads_a_blank_api_key_as_empty(raw: str) -> None:
    environ = {"AUDIODOC_AUDIO_KEY": raw, "AUDIODOC_DOCUMENT_KEY": raw}
    expected = ("", "")

    loaded = load_settings(environ)

    actual = (loaded.AUDIODOC_AUDIO_KEY, loaded.AUDIODOC_DOCUMENT_KEY)
    assert actual == expected, "a whitespace-only API key was kept"


def test_load_settings_keeps_inner_characters_of_an_api_key() -> None:
    key = " k3y with spacesé;'\"-- "
    expected = "k3y with spacesé;'\"--"

    loaded = load_settings({"AUDIODOC_DOCUMENT_KEY": key})

    assert expected == loaded.AUDIODOC_DOCUMENT_KEY, "the API key was altered"


@pytest.mark.parametrize("name", INTEGER_SETTINGS)
@pytest.mark.parametrize("raw", ["not-an-integer", "2.5", "", "9" * 5000])
def test_load_settings_rejects_each_invalid_integer(name: str, raw: str) -> None:
    environ = {name: raw}

    with pytest.raises(ConfigError, match=r".") as caught:
        load_settings(environ)

    expected = (f"Setting {name} must be an integer. Got: {raw!r}",)
    assert caught.value.errors == expected, f"{name}={raw[:20]!r} was accepted"


@pytest.mark.parametrize("name", INTEGER_SETTINGS)
@pytest.mark.parametrize("raw", ["0", "-1", "-99999999999999999999"])
def test_load_settings_rejects_each_integer_below_minimum(name: str, raw: str) -> None:
    environ = {name: raw}

    with pytest.raises(ConfigError, match=r".") as caught:
        load_settings(environ)

    expected = (f"Setting {name} must be at least 1. Got: {raw}",)
    assert caught.value.errors == expected, f"{name}={raw} was accepted"


@pytest.mark.parametrize(
    "name",
    ["WHISPER_OFFLINE", "ENABLE_DOCS", "ALLOW_UNAUTHENTICATED"],
)
@pytest.mark.parametrize("raw", ["sometimes", "true\x00", "yes please"])
def test_load_settings_rejects_each_invalid_boolean(name: str, raw: str) -> None:
    environ = {name: raw}

    with pytest.raises(ConfigError, match=r".") as caught:
        load_settings(environ)

    expected = (f"Setting {name} must be true or false. Got: {raw!r}",)
    assert caught.value.errors == expected, f"{name}={raw!r} was accepted"


def test_load_settings_collects_all_errors() -> None:
    environ = {
        "WHISPER_CPU_THREADS": "invalid",
        "WHISPER_OFFLINE": "sometimes",
        "MAX_AUDIO_SIZE": "0",
    }
    expected = ["WHISPER_CPU_THREADS", "WHISPER_OFFLINE", "MAX_AUDIO_SIZE"]

    with pytest.raises(ConfigError, match=r".") as caught:
        load_settings(environ)

    names = [error.split()[1] for error in caught.value.errors]
    assert names == expected, "not every invalid setting was reported"


def test_config_error_message_lists_every_error() -> None:
    errors = ["Setting A_1 is wrong.", "Setting B_2 is worse."]
    expected = "Invalid configuration:\nSetting A_1 is wrong.\nSetting B_2 is worse."

    message = str(ConfigError(errors))

    assert message == expected, "the configuration error message lost an error"


def test_load_settings_resolves_a_relative_temp_dir_against_home(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    environ = {"AUDIODOC_HOME": str(home), "BACKEND_TEMP_DIR": "cache/audio"}
    expected = str(home / "cache" / "audio")

    loaded = load_settings(environ)

    assert expected == loaded.TEMP_DIR, "the relative temp dir was not resolved"


def test_load_settings_resolves_a_relative_model_path_against_home(
    tmp_path: Path,
) -> None:
    home = tmp_path / "base"
    environ = {"AUDIODOC_HOME": str(home), "WHISPER_MODEL_PATH": "models/small"}
    expected = str(home / "models" / "small")

    loaded = load_settings(environ)

    assert expected == loaded.WHISPER_MODEL_PATH, "the model path was not resolved"


def test_load_settings_keeps_an_absolute_temp_dir(tmp_path: Path) -> None:
    absolute = tmp_path / "elsewhere" / "spool"
    environ = {"AUDIODOC_HOME": str(tmp_path / "h"), "BACKEND_TEMP_DIR": str(absolute)}
    expected = str(absolute)

    loaded = load_settings(environ)

    assert expected == loaded.TEMP_DIR, "an absolute temp dir was moved under home"


@pytest.mark.parametrize("temp_dir", [None, "  "])
def test_load_settings_defaults_temp_dir_to_home_tmp(
    tmp_path: Path, temp_dir: str | None
) -> None:
    home = tmp_path / "app-home"
    environ = {"AUDIODOC_HOME": str(home)}
    if temp_dir is not None:
        environ["BACKEND_TEMP_DIR"] = temp_dir
    expected = str(home / "tmp")

    loaded = load_settings(environ)

    assert expected == loaded.TEMP_DIR, "the default temp dir is not home/tmp"


def test_settings_is_a_slotted_dataclass() -> None:
    expected = (True, True)

    actual = (is_dataclass(Settings), hasattr(Settings, "__slots__"))

    assert actual == expected, "Settings is not a slotted dataclass"


def test_settings_rejects_attribute_assignment() -> None:
    field_name = "WHISPER_MODEL_SIZE"

    with pytest.raises(FrozenInstanceError, match=r".") as caught:
        setattr(Settings(), field_name, "large")

    expected = f"cannot assign to field {field_name!r}"
    assert str(caught.value) == expected, "Settings is not frozen"


@pytest.mark.usefixtures("fresh_settings_cache")
def test_settings_proxy_keeps_the_cached_value_after_an_environment_change(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("WHISPER_MODEL_SIZE", "first")
    expected = ("first", "first")
    proxied = settings.WHISPER_MODEL_SIZE
    monkeypatch.setenv("WHISPER_MODEL_SIZE", "second")

    actual = (proxied, get_settings().WHISPER_MODEL_SIZE)

    assert actual == expected, "the settings were not cached"


@pytest.mark.usefixtures("fresh_settings_cache")
def test_reset_settings_cache_reloads_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("WHISPER_MODEL_SIZE", "medium")
    _ = settings.WHISPER_MODEL_SIZE
    monkeypatch.setenv("WHISPER_MODEL_SIZE", "tiny")
    expected = "tiny"

    reset_settings_cache()

    assert expected == settings.WHISPER_MODEL_SIZE, "the cache was not reset"


@pytest.mark.usefixtures("fresh_settings_cache")
def test_settings_proxy_assignment_overrides_the_cached_value() -> None:
    expected = "override-model"

    settings.WHISPER_MODEL_SIZE = expected

    assert expected == get_settings().WHISPER_MODEL_SIZE, "the override was lost"


@pytest.mark.usefixtures("fresh_settings_cache")
def test_settings_proxy_deletion_restores_the_cached_value() -> None:
    original = get_settings().WHISPER_MODEL_SIZE
    settings.WHISPER_MODEL_SIZE = "temporary"

    del settings.WHISPER_MODEL_SIZE

    assert original == settings.WHISPER_MODEL_SIZE, "deletion did not restore it"


@pytest.mark.usefixtures("fresh_settings_cache")
def test_settings_proxy_deletion_keeps_other_overrides() -> None:
    expected = "xx-override"
    settings.WHISPER_MODEL_SIZE = "temporary"
    settings.WHISPER_LANGUAGE = expected

    del settings.WHISPER_MODEL_SIZE

    assert expected == settings.WHISPER_LANGUAGE, "another override was dropped"


@pytest.mark.usefixtures("fresh_settings_cache")
def test_settings_proxy_returns_the_cached_settings_without_overrides() -> None:
    original = get_settings()
    settings.WHISPER_MODEL_SIZE = "temporary"
    settings.WHISPER_LANGUAGE = "temporary"
    del settings.WHISPER_MODEL_SIZE

    del settings.WHISPER_LANGUAGE

    assert get_settings() is original, "the cached settings were not restored"


@pytest.mark.usefixtures("fresh_settings_cache")
@pytest.mark.parametrize("name", ["NOT_A_SETTING", "__class__", "errors"])
def test_settings_proxy_rejects_an_unknown_setting(name: str) -> None:
    with pytest.raises(AttributeError, match=r".") as caught:
        setattr(settings, name, "injected")

    assert str(caught.value) == name, "an unknown setting was accepted"


def test_load_env_file_prefers_home_env_over_working_directory_env(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    working_dir = tmp_path / "working"
    home.mkdir()
    working_dir.mkdir()
    (home / ".env").write_text("AD_PROBE_ORDER=from-home\n", encoding="utf-8")
    (working_dir / ".env").write_text("AD_PROBE_ORDER=from-cwd\n", encoding="utf-8")
    _clear_environment(monkeypatch, "AD_PROBE_ORDER")
    monkeypatch.setenv("AUDIODOC_HOME", str(home))
    monkeypatch.chdir(working_dir)
    expected = "from-home"

    load_env_file()

    assert os.environ.get("AD_PROBE_ORDER") == expected, "home .env lost"


def test_load_env_file_reads_the_working_directory_env(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    working_dir = tmp_path / "cwd"
    working_dir.mkdir()
    (working_dir / ".env").write_text("AD_PROBE_CWD=seen-7\n", encoding="utf-8")
    _clear_environment(monkeypatch, "AD_PROBE_CWD")
    monkeypatch.setenv("AUDIODOC_HOME", str(tmp_path / "missing-home"))
    monkeypatch.chdir(working_dir)
    expected = "seen-7"

    load_env_file()

    assert os.environ.get("AD_PROBE_CWD") == expected, "cwd .env was not read"


def test_load_env_file_does_not_override_an_existing_variable(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    home = tmp_path / "h0me"
    home.mkdir()
    (home / ".env").write_text("AD_PROBE_KEEP=from-file\n", encoding="utf-8")
    monkeypatch.setenv("AD_PROBE_KEEP", "from-process")
    monkeypatch.setenv("AUDIODOC_HOME", str(home))
    monkeypatch.chdir(tmp_path)
    expected = "from-process"

    load_env_file()

    assert os.environ.get("AD_PROBE_KEEP") == expected, "a variable was overridden"


def test_load_env_file_reads_the_explicit_file_before_the_home_it_configures(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    home = tmp_path / "configured-home"
    working_dir = tmp_path / "working"
    home.mkdir()
    working_dir.mkdir()
    env_file = tmp_path / "custom.env"
    env_file.write_text(
        f"AUDIODOC_HOME={home}\nAD_PROBE_FIRST=explicit\n", encoding="utf-8"
    )
    (home / ".env").write_text(
        "AD_PROBE_FIRST=home\nAD_PROBE_HOME=read\n", encoding="utf-8"
    )
    _clear_environment(monkeypatch, "AUDIODOC_HOME", "AD_PROBE_FIRST", "AD_PROBE_HOME")
    monkeypatch.chdir(working_dir)
    expected = ("explicit", "read")

    load_env_file(env_file)

    actual = (os.environ.get("AD_PROBE_FIRST"), os.environ.get("AD_PROBE_HOME"))
    assert actual == expected, "the explicit file or its home .env was not read"
