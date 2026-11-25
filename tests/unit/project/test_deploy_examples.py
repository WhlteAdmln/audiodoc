# Copyright (c) 2026 Nikolai Zelensky
"""Regression tests for deployment configuration examples."""

from configparser import ConfigParser
from pathlib import Path

import pytest

DEPLOY_DIR = Path(__file__).resolve().parents[3] / "deploy"


@pytest.mark.parametrize(
    ("filename", "address", "private_key", "public_key", "allowed_ips", "endpoint"),
    [
        pytest.param(
            "wireguard-backend.conf.example",
            "10.8.0.1/24",
            "<PRIVATE_KEY_OF_MACHINE_B>",
            "<PUBLIC_KEY_OF_MACHINE_A>",
            "10.8.0.2/32",
            None,
            id="backend",
        ),
        pytest.param(
            "wireguard-bot.conf.example",
            "10.8.0.2/24",
            "<PRIVATE_KEY_OF_MACHINE_A>",
            "<PUBLIC_KEY_OF_MACHINE_B>",
            "10.8.0.1/32",
            "<PUBLIC_ENDPOINT_OF_MACHINE_B>:51820",
            id="bot",
        ),
    ],
)
def test_wireguard_examples_use_placeholders_and_expected_addresses(
    filename: str,
    address: str,
    private_key: str,
    public_key: str,
    allowed_ips: str,
    endpoint: str | None,
) -> None:
    parser = ConfigParser(interpolation=None, strict=True)
    with (DEPLOY_DIR / filename).open(encoding="utf-8") as config_file:
        parser.read_file(config_file)
    interface = parser["Interface"]
    peer = parser["Peer"]

    actual = (
        parser.sections(),
        interface.get("address"),
        interface.get("privatekey"),
        peer.get("publickey"),
        peer.get("allowedips"),
        peer.get("endpoint"),
    )
    expected = (
        ["Interface", "Peer"],
        address,
        private_key,
        public_key,
        allowed_ips,
        endpoint,
    )
    assert actual == expected, "the WireGuard example has wrong values"


@pytest.fixture(name="ci_workflow")
def fixture_ci_workflow() -> str:
    """Return the text of the CI workflow."""
    return (DEPLOY_DIR.parent / ".github" / "workflows" / "ci.yml").read_text(
        encoding="utf-8"
    )


@pytest.mark.parametrize(
    "expected_line",
    [
        "from audiodoc.service import render_service_unit",
        'systemd-analyze verify "${service_file}"',
    ],
)
def test_ci_systemd_verification_uses_canonical_renderer(
    ci_workflow: str, expected_line: str
) -> None:
    assert expected_line in ci_workflow, "CI must verify the rendered service unit"


def test_ci_systemd_verification_does_not_copy_the_example_unit(
    ci_workflow: str,
) -> None:
    example_redirect = 'deploy/audiodoc.service.example > "${service_file}"'
    assert example_redirect not in ci_workflow, "CI must not verify the example unit"
