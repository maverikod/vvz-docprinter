"""
Tests for ``GetPrintResultCommand``.

Author: Vasiliy Zdanovskiy
email: vasilyvz@gmail.com
"""

from __future__ import annotations

import asyncio
import base64
from pathlib import Path

import pytest
from mcp_proxy_adapter.config import get_config

from docprinter.commands.get_print_result_command import GetPrintResultCommand


@pytest.fixture
def docprinter_output(tmp_path: Path) -> Path:
    out = tmp_path / "out"
    wk = tmp_path / "wk"
    cfg = get_config()
    cfg.config_data["docprinter"] = {
        "output_dir": str(out),
        "work_dir": str(wk),
        "output_ttl_seconds": 3600,
        "sweep_interval_seconds": 300,
    }
    out.mkdir(parents=True, exist_ok=True)
    return out


def test_get_print_result_success(docprinter_output: Path) -> None:
    rid = "33333333-3333-4333-8333-333333333333"
    payload = b"PK\x03\x04fake-docx"
    (docprinter_output / f"{rid}.docx").write_bytes(payload)

    async def _run() -> dict:
        cmd = GetPrintResultCommand()
        r = await cmd.execute(result_id=rid)
        return r.to_dict()

    d = asyncio.run(_run())
    assert d["success"] is True
    assert d["data"]["result_id"] == rid
    assert base64.b64decode(d["data"]["document_base64"]) == payload
    assert "wordprocessingml" in d["data"]["content_type"]


def test_get_print_result_not_found(docprinter_output: Path) -> None:
    """Missing file (e.g. TTL sweep or wrong id) -> RESULT_NOT_FOUND."""

    async def _run() -> dict:
        cmd = GetPrintResultCommand()
        r = await cmd.execute(
            result_id="44444444-4444-4444-8444-444444444444",
        )
        return r.to_dict()

    d = asyncio.run(_run())
    assert d["success"] is False
    assert d["error"]["data"]["error_code"] == "RESULT_NOT_FOUND"
    assert d["error"]["data"].get("may_have_been_removed_by_ttl") is True


def test_get_print_result_invalid_uuid(docprinter_output: Path) -> None:

    async def _run() -> dict:
        cmd = GetPrintResultCommand()
        r = await cmd.execute(result_id="not-a-uuid")
        return r.to_dict()

    d = asyncio.run(_run())
    assert d["success"] is False
    assert d["error"]["data"]["error_code"] == "RESULT_ID_INVALID"


def test_get_print_result_schema() -> None:
    s = GetPrintResultCommand.get_schema()
    assert s["required"] == ["result_id"]
    assert s.get("additionalProperties") is False


def test_get_print_result_result_schema_title() -> None:
    s = GetPrintResultCommand.get_result_schema()
    assert s.get("title") == "get_print_result_success"
    req = s["properties"]["data"]["required"]
    assert set(req) >= {"result_id", "document_base64", "content_type"}
