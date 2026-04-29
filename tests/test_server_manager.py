"""
Tests for :mod:`docprinter.server_manager`.

Author: Vasiliy Zdanovskiy
email: vasilyvz@gmail.com
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from docprinter.server_manager import ServerManager


def test_prepare_creates_runtime_directories(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    cfg_dst = tmp_path / "server.json"
    shutil.copy(repo_root / "config" / "docprinter.server.json", cfg_dst)
    payload = json.loads(cfg_dst.read_text(encoding="utf-8"))
    payload["docprinter"] = {
        "output_dir": str(tmp_path / "custom_out"),
        "work_dir": str(tmp_path / "custom_work"),
        "output_ttl_seconds": 7200,
        "sweep_interval_seconds": 60,
        "trace_log_file": None,
    }
    cfg_dst.write_text(json.dumps(payload), encoding="utf-8")

    manager = ServerManager(cfg_dst)
    manager.prepare()

    assert (tmp_path / "custom_out").is_dir()
    assert (tmp_path / "custom_work").is_dir()
    assert manager.runtime_settings.output_dir == tmp_path / "custom_out"
    assert manager.runtime_settings.work_dir == tmp_path / "custom_work"
    assert manager.runtime_settings.output_ttl_seconds == 7200
    assert manager.runtime_settings.sweep_interval_seconds == 60


def test_load_missing_file_exits(tmp_path: Path) -> None:
    missing = tmp_path / "missing.json"
    with pytest.raises(SystemExit):
        ServerManager(missing).load_raw_config()


def test_run_server_without_prepare_raises(tmp_path: Path) -> None:
    cfg = tmp_path / "x.json"
    cfg.write_text("{}", encoding="utf-8")
    manager = ServerManager(cfg)
    with pytest.raises(RuntimeError, match="prepare"):
        manager.run_server()
