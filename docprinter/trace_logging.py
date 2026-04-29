"""
Step-by-step trace log to ``docprinter.trace_log_file`` (server JSON).

Shows how far ``print`` / ``get_print_result`` got before a failure.

Author: Vasiliy Zdanovskiy
email: vasilyvz@gmail.com
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any

_TRACE_LOGGER_NAME = "docprinter.trace"
_LOCK = threading.Lock()
_HANDLER_MARKER = "_docprinter_trace_file_handler"


def configure_trace_log_file(
    path_str: str | None,
    *,
    log_level_name: str = "INFO",
) -> None:
    """
    Attach or detach a single file handler on ``docprinter.trace``.

    * ``path_str`` ``None`` or empty: remove file handler; trace calls are no-ops
      (``NullHandler`` only).
    * Otherwise: append UTF-8 log at the resolved path (parent dirs created).
    """
    level = getattr(logging, str(log_level_name).upper(), logging.INFO)
    trace = logging.getLogger(_TRACE_LOGGER_NAME)
    trace.setLevel(level)
    trace.propagate = False

    with _LOCK:
        for h in list(trace.handlers):
            trace.removeHandler(h)
            h.close()

        if path_str is None or not str(path_str).strip():
            trace.addHandler(logging.NullHandler())
            return

        path = Path(str(path_str).strip()).expanduser()
        if not path.is_absolute():
            path = Path.cwd() / path
        path.parent.mkdir(parents=True, exist_ok=True)

        fh = logging.FileHandler(path, encoding="utf-8", mode="a")
        setattr(fh, _HANDLER_MARKER, True)
        fh.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)s %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        trace.addHandler(fh)


def tlog(command: str, step: str, **fields: Any) -> None:
    """
    Write one trace line: ``command``, ``step``, optional ``key=value`` fields.

    Safe to call when trace file is disabled (no output).
    """
    log = logging.getLogger(_TRACE_LOGGER_NAME)
    if not fields:
        log.info("[trace] %s | %s", command, step)
        return
    tail = " ".join(f"{k}={v!r}" for k, v in sorted(fields.items()))
    log.info("[trace] %s | %s | %s", command, step, tail)


__all__ = ["configure_trace_log_file", "tlog"]
