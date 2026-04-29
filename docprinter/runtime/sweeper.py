"""
Background eviction of stale files under runtime/output and runtime/work.

Author: Vasiliy Zdanovskiy
email: vasilyvz@gmail.com
"""

from __future__ import annotations

import logging
import shutil
import threading
import time
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)


class RuntimeSweeper:
    """Daemon thread: evict stale ``.docx`` in output_dir and stale dirs in work_dir."""

    def __init__(
        self,
        output_dir: Path,
        work_dir: Path,
        output_ttl_seconds: int,
        sweep_interval_seconds: int,
    ) -> None:
        self._output_dir = output_dir
        self._work_dir = work_dir
        self._output_ttl_seconds = output_ttl_seconds
        self._sweep_interval_seconds = sweep_interval_seconds
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._started = False

    def start(self) -> None:
        """Start the daemon thread. Idempotent."""
        if self._started:
            return
        self._started = True
        self._stop.clear()

        def _loop() -> None:
            while not self._stop.is_set():
                try:
                    self.sweep_once()
                except Exception:  # noqa: BLE001 — never kill sweeper thread
                    logger.exception("RuntimeSweeper iteration failed")
                if self._stop.wait(self._sweep_interval_seconds):
                    break

        self._thread = threading.Thread(
            target=_loop, daemon=True, name="RuntimeSweeper"
        )
        self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        """Signal stop and join."""
        self._stop.set()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=timeout)
        self._started = False
        self._thread = None

    def sweep_once(self) -> Dict[str, Any]:
        """Run one sweep iteration. Returns counters: {output_removed, work_removed}."""
        now = time.time()
        ttl = float(self._output_ttl_seconds)
        output_removed = 0
        work_removed = 0

        try:
            if self._output_dir.is_dir():
                for path in self._output_dir.iterdir():
                    try:
                        if not path.is_file():
                            continue
                        if path.suffix.lower() != ".docx":
                            continue
                        if now - path.stat().st_mtime > ttl:
                            path.unlink(missing_ok=True)
                            output_removed += 1
                    except OSError as exc:
                        logger.warning("sweep output %s: %s", path, exc)
        except OSError as exc:
            logger.warning("sweep output_dir %s: %s", self._output_dir, exc)

        try:
            if self._work_dir.is_dir():
                for path in self._work_dir.iterdir():
                    try:
                        if not path.is_dir():
                            continue
                        if now - path.stat().st_mtime > ttl:
                            shutil.rmtree(path, ignore_errors=True)
                            work_removed += 1
                    except OSError as exc:
                        logger.warning("sweep work %s: %s", path, exc)
        except OSError as exc:
            logger.warning("sweep work_dir %s: %s", self._work_dir, exc)

        return {"output_removed": output_removed, "work_removed": work_removed}
