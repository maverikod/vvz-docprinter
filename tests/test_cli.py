"""
Tests for :mod:`docprinter.cli`.

Author: Vasiliy Zdanovskiy
email: vasilyvz@gmail.com
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest

from docprinter import cli


def test_normalize_argv_inserts_run_before_config() -> None:
    assert cli._normalize_argv(["--config", "x.json"]) == ["run", "--config", "x.json"]
    assert cli._normalize_argv(["-c", "x.json"]) == ["run", "-c", "x.json"]
    cyr = "-\u0441"
    assert cli._normalize_argv([cyr, "x.json"]) == ["run", cyr, "x.json"]


def test_normalize_argv_preserves_subcommands() -> None:
    assert cli._normalize_argv(["start", "-c", "x.json"]) == ["start", "-c", "x.json"]


def test_status_no_pid_file(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    pid_path = tmp_path / "missing.pid"
    old = sys.argv[:]
    try:
        sys.argv = ["docprinter", "status", "--pid-file", str(pid_path), "--no-http"]
        cli.main()
    finally:
        sys.argv[:] = old
    out = capsys.readouterr().out
    assert "stopped" in out.lower()


def test_stop_no_pid_file(tmp_path: Path) -> None:
    pid_path = tmp_path / "missing.pid"
    old = sys.argv[:]
    try:
        sys.argv = ["docprinter", "stop", "--pid-file", str(pid_path)]
        with pytest.raises(SystemExit) as exc:
            cli.main()
        assert exc.value.code == 0
    finally:
        sys.argv[:] = old


def test_main_no_args_prints_help(capsys: pytest.CaptureFixture[str]) -> None:
    old = sys.argv[:]
    try:
        sys.argv = ["docprinter"]
        with pytest.raises(SystemExit) as exc:
            cli.main()
        assert exc.value.code == 0
    finally:
        sys.argv[:] = old
    assert "start" in capsys.readouterr().out


def test_start_daemon_writes_pid_file(tmp_path: Path) -> None:
    repo = Path(__file__).resolve().parents[1]
    cfg = repo / "config" / "docprinter.server.json"
    pid_path = tmp_path / "srv.pid"
    log_path = tmp_path / "srv.log"

    fake = mock.Mock(spec=subprocess.Popen)
    fake.pid = 424242

    old = sys.argv[:]
    try:
        sys.argv = [
            "docprinter",
            "start",
            "-c",
            str(cfg),
            "--pid-file",
            str(pid_path),
            "--log-file",
            str(log_path),
        ]
        with mock.patch("docprinter.cli.subprocess.Popen", return_value=fake):
            cli.main()
    finally:
        sys.argv[:] = old

    assert pid_path.is_file()
    meta = json.loads(pid_path.read_text(encoding="utf-8"))
    assert meta["pid"] == 424242
    assert meta["config"] == str(cfg.resolve())


def test_parser_run_default_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DOCPRINTER_CONFIG", raising=False)
    parser = cli._build_parser()
    args = parser.parse_args(["run"])
    assert args.config == "config/config.json"


def test_parser_start_accepts_cyrillic_c_flag() -> None:
    parser = cli._build_parser()
    cyr = "-\u0441"
    args = parser.parse_args(
        ["start", cyr, "other/server.json", "--pid-file", "/tmp/p.pid"]
    )
    assert args.config == "other/server.json"


def test_status_stale_pid(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    pid_path = tmp_path / "stale.pid"
    pid_path.write_text(
        json.dumps({"pid": 999999001, "host": "127.0.0.1", "port": 9}),
        encoding="utf-8",
    )
    old = sys.argv[:]
    try:
        sys.argv = ["docprinter", "status", "--pid-file", str(pid_path), "--no-http"]
        with pytest.raises(SystemExit) as exc:
            cli.main()
        assert exc.value.code == 1
    finally:
        sys.argv[:] = old
    assert "stale" in capsys.readouterr().out.lower()
