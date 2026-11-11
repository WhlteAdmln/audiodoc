# Copyright (c) 2026 Nikolai Zelensky
"""Regression tests for deployment configuration examples."""

from configparser import ConfigParser
from pathlib import Path

import pytest

DEPLOY_DIR = Path(__file__).resolve().parents[2] / "deploy"


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
    """Ensure both WireGuard examples contain the expected placeholders."""
    parser = ConfigParser(interpolation=None, strict=True)
    with (DEPLOY_DIR / filename).open(encoding="utf-8") as config_file:
        parser.read_file(config_file)

    assert parser.sections() == ["Interface", "Peer"]
    interface = parser["Interface"]
    peer = parser["Peer"]
    assert interface["address"] == address
    assert interface["privatekey"] == private_key
    assert peer["publickey"] == public_key
    assert peer["allowedips"] == allowed_ips
    if endpoint is None:
        assert "endpoint" not in peer
    else:
        assert peer["endpoint"] == endpoint


def test_ci_systemd_verification_uses_canonical_renderer() -> None:
    """Keep CI systemd validation aligned with the canonical unit renderer."""
    workflow = (DEPLOY_DIR.parent / ".github" / "workflows" / "ci.yml").read_text(
        encoding="utf-8"
    )

    assert "from audiodoc.service import render_service_unit" in workflow
    assert 'systemd-analyze verify "${service_file}"' in workflow
    assert 'deploy/audiodoc.service.example > "${service_file}"' not in workflow
