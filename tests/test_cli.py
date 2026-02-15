"""Tests for the Peblar CLI."""

from __future__ import annotations

import io
from contextlib import redirect_stdout
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aresponses import ResponsesMockServer
from typer.testing import CliRunner

from peblar.cli import cli, identify, versions
from peblar.models import PeblarVersions
from tests import load_fixture

if TYPE_CHECKING:
    from collections.abc import Iterator


def _add_versions_responses(aresponses: ResponsesMockServer) -> None:
    """Add aresponses mocks for the versions command."""
    aresponses.add(
        "example.com",
        "/api/v1/auth/login",
        "POST",
        aresponses.Response(status=200, body=load_fixture("ok_response.json")),
    )
    aresponses.add(
        "example.com",
        "/api/v1/system/software/automatic-update/current-versions",
        "GET",
        aresponses.Response(
            status=200,
            body=load_fixture("peblar_versions.json"),
        ),
    )
    aresponses.add(
        "example.com",
        "/api/v1/system/software/automatic-update/available-versions",
        "GET",
        aresponses.Response(
            status=200,
            body=load_fixture("peblar_versions.json"),
        ),
    )


@pytest.fixture
def patched_peblar_versions_for_cli() -> Iterator[None]:
    """Patch Peblar so CliRunner runs versions without HTTP (nested asyncio.run)."""
    vers = PeblarVersions.from_json(load_fixture("peblar_versions.json").encode())
    mock_instance = AsyncMock()
    mock_instance.login = AsyncMock()
    mock_instance.current_versions = AsyncMock(return_value=vers)
    mock_instance.available_versions = AsyncMock(return_value=vers)
    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_instance)
    mock_cm.__aexit__ = AsyncMock(return_value=False)
    mock_cls = MagicMock(return_value=mock_cm)
    with patch("peblar.cli.Peblar", mock_cls):
        yield


def _add_identify_responses(aresponses: ResponsesMockServer) -> None:
    """Add aresponses mocks for the identify command."""
    aresponses.add(
        "example.com",
        "/api/v1/auth/login",
        "POST",
        aresponses.Response(status=200, body=load_fixture("ok_response.json")),
    )
    aresponses.add(
        "example.com",
        "/api/v1/system/identify",
        "PUT",
        aresponses.Response(status=200, body=load_fixture("ok_response.json")),
    )


@pytest.mark.asyncio
async def test_versions_quiet_still_prints_table(
    aresponses: ResponsesMockServer,
) -> None:
    """--quiet suppresses status/success only; versions table still prints."""
    _add_versions_responses(aresponses)

    capture = io.StringIO()
    with redirect_stdout(capture):
        await versions(host="example.com", password="secret", quiet=True)

    output = capture.getvalue()
    assert "Peblar charger versions" in output
    assert "1.6.1+1" in output


@pytest.mark.asyncio
async def test_versions_without_quiet_shows_output(
    aresponses: ResponsesMockServer,
) -> None:
    """Test that versions command shows output without --quiet option."""
    _add_versions_responses(aresponses)

    capture = io.StringIO()
    with redirect_stdout(capture):
        await versions(host="example.com", password="secret", quiet=False)

    output = capture.getvalue()
    assert "Peblar charger versions" in output
    assert "Firmware" in output
    assert "Customization" in output
    assert "1.6.1+1" in output


@pytest.mark.asyncio
async def test_versions_short_quiet_flag_still_prints_table(
    aresponses: ResponsesMockServer,
) -> None:
    """Test that -q still prints the versions table."""
    _add_versions_responses(aresponses)

    capture = io.StringIO()
    with redirect_stdout(capture):
        await versions(host="example.com", password="secret", quiet=True)

    assert "Firmware" in capture.getvalue()


@pytest.mark.usefixtures("patched_peblar_versions_for_cli")
@pytest.mark.parametrize("quiet_flag", ["-q", "--quiet"], ids=["short_q", "long_quiet"])
def test_versions_cli_runner_quiet_flags_print_table(quiet_flag: str) -> None:
    """CliRunner: -q and --quiet keep the versions table."""
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "versions",
            "--host",
            "example.com",
            "--password",
            "secret",
            quiet_flag,
        ],
        catch_exceptions=False,
    )
    assert result.exit_code == 0
    out = result.stdout
    assert "Peblar charger versions" in out
    assert "Firmware" in out
    assert "1.6.1+1" in out


@pytest.mark.asyncio
async def test_identify_quiet_suppresses_success_line(
    aresponses: ResponsesMockServer,
) -> None:
    """Test that --quiet hides the spinner and Success line (no table on identify)."""
    _add_identify_responses(aresponses)

    capture = io.StringIO()
    with redirect_stdout(capture):
        await identify(host="example.com", password="secret", quiet=True)

    assert capture.getvalue().strip() == ""


@pytest.mark.asyncio
async def test_identify_without_quiet_shows_success(
    aresponses: ResponsesMockServer,
) -> None:
    """Test that identify command shows success without --quiet option."""
    _add_identify_responses(aresponses)

    capture = io.StringIO()
    with redirect_stdout(capture):
        await identify(host="example.com", password="secret", quiet=False)

    assert "Success" in capture.getvalue()
