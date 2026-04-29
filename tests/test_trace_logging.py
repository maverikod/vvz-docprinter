"""Tests for :mod:`docprinter.trace_logging`."""

from __future__ import annotations

from pathlib import Path

from docprinter.trace_logging import configure_trace_log_file, tlog


def test_trace_log_file_writes_line(tmp_path: Path) -> None:
    log_path = tmp_path / "trace.log"
    configure_trace_log_file(str(log_path), log_level_name="INFO")
    tlog("print", "01_test_step", foo=1)
    configure_trace_log_file(None)
    text = log_path.read_text(encoding="utf-8")
    assert "[trace]" in text
    assert "print" in text
    assert "01_test_step" in text
