"""Tests for the meterhistory CLI command."""

from __future__ import annotations

import io
import re
from contextlib import redirect_stdout
from pathlib import Path  # noqa: TC003

import pytest
from aresponses import ResponsesMockServer

from peblar.cli import meterhistory
from tests import load_fixture


def _add_meterhistory_responses(
    aresponses: ResponsesMockServer,
    *,
    meterhistory_fixture: str,
) -> None:
    """Register HTTP mocks for login, meter history, and RFID token list."""
    aresponses.add(
        "example.com",
        "/api/v1/auth/login",
        "POST",
        aresponses.Response(status=200, body=load_fixture("ok_response.json")),
    )
    aresponses.add(
        "example.com",
        "/api/v1/statistics/meterhistory",
        "GET",
        aresponses.Response(
            status=200,
            body=load_fixture(meterhistory_fixture),
        ),
    )
    aresponses.add(
        "example.com",
        "/api/v1/config/auth/standalonelist",
        "GET",
        aresponses.Response(
            status=200,
            body=load_fixture("standalonelist.json"),
        ),
    )


@pytest.mark.asyncio
async def test_meterhistory_summary_no_sessions_message(
    aresponses: ResponsesMockServer,
) -> None:
    """NoSessions response shows the warning and no CSV."""
    _add_meterhistory_responses(
        aresponses,
        meterhistory_fixture="meterhistory-nosessions.json",
    )

    capture = io.StringIO()
    with redirect_stdout(capture):
        await meterhistory(
            host="example.com",
            password="secret",
            export=False,
            quiet=False,
        )

    out = capture.getvalue()
    assert "No sessions found" in out


@pytest.mark.asyncio
async def test_meterhistory_summary_shows_totals_and_table(
    aresponses: ResponsesMockServer,
) -> None:
    """With sessions, summary shows total kWh, session count, and token table."""
    _add_meterhistory_responses(aresponses, meterhistory_fixture="meterhistory.json")

    capture = io.StringIO()
    with redirect_stdout(capture):
        await meterhistory(
            host="example.com",
            password="secret",
            export=False,
            quiet=False,
        )

    out = capture.getvalue()
    # Total span: max(end) - min(start) = 1998041111 - 1956857265 = 41183846 mWh
    assert re.search(r"41[.,]184", out), out
    assert "kWh" in out
    assert re.search(r"Sessions:\s*2\b", out), out
    assert "Energy by authorisation token" in out
    assert "123456789A1234" in out
    assert "12345E01234567" in out


@pytest.mark.asyncio
async def test_meterhistory_export_writes_csv(
    aresponses: ResponsesMockServer,
    tmp_path: Path,
) -> None:
    """With --export, meter history is written to the given CSV path."""
    _add_meterhistory_responses(aresponses, meterhistory_fixture="meterhistory.json")

    out_file = tmp_path / "meter.csv"
    await meterhistory(
        host="example.com",
        password="secret",
        export=True,
        filename=str(out_file),
        quiet=True,
    )

    assert out_file.is_file()
    text = out_file.read_text(encoding="utf-8")
    assert "12-34-Z56-P4R" in text
    assert "123456789A1234" in text
