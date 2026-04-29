"""
Tests for ``RuntimeSweeper``.

Author: Vasiliy Zdanovskiy
email: vasilyvz@gmail.com
"""

from __future__ import annotations

import os
import time
from pathlib import Path

from docprinter.runtime.sweeper import RuntimeSweeper


def test_sweep_once_removes_old_output(tmp_path: Path) -> None:
    out = tmp_path / "output"
    work = tmp_path / "work"
    out.mkdir()
    work.mkdir()
    f = out / "old.docx"
    f.write_bytes(b"PK")
    old = time.time() - 7200
    os.utime(f, (old, old))
    s = RuntimeSweeper(out, work, output_ttl_seconds=3600, sweep_interval_seconds=60)
    r = s.sweep_once()
    assert r["output_removed"] >= 1
    assert not f.exists()


def test_sweep_once_keeps_fresh_output(tmp_path: Path) -> None:
    out = tmp_path / "output"
    work = tmp_path / "work"
    out.mkdir()
    work.mkdir()
    f = out / "fresh.docx"
    f.write_bytes(b"PK")
    s = RuntimeSweeper(out, work, output_ttl_seconds=3600, sweep_interval_seconds=60)
    r = s.sweep_once()
    assert r["output_removed"] == 0
    assert f.is_file()


def test_sweep_once_removes_old_work_subdir(tmp_path: Path) -> None:
    out = tmp_path / "output"
    work = tmp_path / "work"
    out.mkdir()
    work.mkdir()
    d = work / "stale"
    d.mkdir()
    old = time.time() - 7200
    os.utime(d, (old, old))
    s = RuntimeSweeper(out, work, output_ttl_seconds=3600, sweep_interval_seconds=60)
    r = s.sweep_once()
    assert r["work_removed"] >= 1
    assert not d.exists()


def test_sweeper_thread_lifecycle(tmp_path: Path) -> None:
    out = tmp_path / "o"
    work = tmp_path / "w"
    out.mkdir()
    work.mkdir()
    s = RuntimeSweeper(out, work, output_ttl_seconds=3600, sweep_interval_seconds=300)
    s.start()
    th = s._thread
    assert th is not None
    assert th.is_alive()
    time.sleep(0.05)
    s.stop(timeout=2.0)
    assert not th.is_alive()
