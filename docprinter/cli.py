#!/usr/bin/env python3
"""
Console entry: ``docprinter start|stop|status|run`` and ``python -m docprinter``.

Author: Vasiliy Zdanovskiy
email: vasilyvz@gmail.com
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

DEFAULT_PID_FILE = Path("runtime/docprinter.pid")
DEFAULT_LOG_FILE = Path("logs/docprinter-server.log")
DEFAULT_CONFIG_FILE = Path("config/config.json")
# Cyrillic es (U+0441): same shape as Latin c on RU layout.
_CONFIG_FLAG_CYRILLIC = "-\u0441"

_SUBCOMMANDS = frozenset({"start", "stop", "status", "run", "help"})


def _default_pid_path() -> Path:
    return Path(
        os.environ.get("DOCPRINTER_PID_FILE", str(DEFAULT_PID_FILE))
    ).expanduser()


def _default_log_path() -> Path:
    return Path(
        os.environ.get("DOCPRINTER_LOG_FILE", str(DEFAULT_LOG_FILE))
    ).expanduser()


def _default_config_str() -> str:
    """Default server JSON path (cwd-relative unless absolute)."""
    return os.environ.get("DOCPRINTER_CONFIG", str(DEFAULT_CONFIG_FILE))


def _add_config_argument(subparser: argparse.ArgumentParser) -> None:
    subparser.add_argument(
        "-c",
        _CONFIG_FLAG_CYRILLIC,
        "--config",
        default=_default_config_str(),
        metavar="CONFIG",
        help=(
            "Path to server JSON (default: config/config.json; "
            "override with DOCPRINTER_CONFIG)"
        ),
    )


def _read_pidfile(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        raw = path.read_text(encoding="utf-8").strip()
        data = json.loads(raw)
        if isinstance(data, dict) and "pid" in data:
            return data
    except (OSError, json.JSONDecodeError):
        pass
    return None


def _write_pidfile(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(payload), indent=2), encoding="utf-8")


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def _server_bind_from_config(config_path: Path) -> tuple[str, int]:
    with config_path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    server = data.get("server") or {}
    host = str(server.get("host", "0.0.0.0"))
    port = int(server.get("port", 8080))
    return host, port


def _health_url(host: str, port: int) -> str:
    connect_host = "127.0.0.1" if host in ("0.0.0.0", "::", "") else host
    return f"http://{connect_host}:{port}/health"


def cmd_run(args: argparse.Namespace) -> None:
    """Run server in the foreground (blocks until shutdown)."""
    from docprinter.server_manager import ServerManager

    cfg_path = Path(args.config).resolve()
    manager = ServerManager(cfg_path)
    try:
        manager.run(cli_host=args.host, cli_port=args.port)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc


def cmd_start(args: argparse.Namespace) -> None:
    """Start server in background (subprocess) or foreground."""
    cfg_path = Path(args.config).resolve()
    pid_path = Path(args.pid_file).expanduser().resolve()

    existing = _read_pidfile(pid_path)
    if existing and _pid_alive(int(existing["pid"])):
        print(
            f"DocPrinter already running (pid {existing['pid']}).",
            file=sys.stderr,
        )
        raise SystemExit(1)

    if pid_path.is_file():
        pid_path.unlink(missing_ok=True)

    if getattr(args, "foreground", False):
        host, port = _server_bind_from_config(cfg_path)
        _write_pidfile(
            pid_path,
            {
                "pid": os.getpid(),
                "config": str(cfg_path),
                "cwd": str(Path.cwd()),
                "started": datetime.now(timezone.utc).isoformat(),
                "host": host,
                "port": port,
                "foreground": True,
            },
        )
        try:
            cmd_run(args)
        finally:
            pid_path.unlink(missing_ok=True)
        return

    log_path = Path(args.log_file).expanduser().resolve()
    log_path.parent.mkdir(parents=True, exist_ok=True)

    host, port = _server_bind_from_config(cfg_path)
    cmd = [
        sys.executable,
        "-m",
        "docprinter",
        "run",
        "-c",
        str(cfg_path),
    ]
    if args.host is not None:
        cmd.extend(["--host", args.host])
    if args.port is not None:
        cmd.extend(["--port", str(args.port)])

    log_f = open(log_path, "a", encoding="utf-8", buffering=1)
    child_env = os.environ.copy()
    cwd_resolved = str(Path.cwd().resolve())
    marker = Path(cwd_resolved) / "docprinter" / "commands" / "print_command.py"
    if marker.is_file():
        prev = child_env.get("PYTHONPATH", "")
        child_env["PYTHONPATH"] = (
            cwd_resolved + (os.pathsep + prev if prev else "")
        )

    try:
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=log_f,
            stderr=subprocess.STDOUT,
            close_fds=True,
            cwd=os.getcwd(),
            env=child_env,
            start_new_session=True,
        )
    except OSError as exc:
        log_f.close()
        print(f"Failed to start process: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    log_f.close()

    _write_pidfile(
        pid_path,
        {
            "pid": proc.pid,
            "config": str(cfg_path),
            "cwd": str(Path.cwd()),
            "started": datetime.now(timezone.utc).isoformat(),
            "host": host,
            "port": port,
            "log_file": str(log_path),
            "foreground": False,
        },
    )
    print(f"DocPrinter started (pid {proc.pid}), log: {log_path}")


def cmd_stop(args: argparse.Namespace) -> None:
    """Send SIGTERM to the managed server process."""
    pid_path = Path(args.pid_file).expanduser().resolve()
    data = _read_pidfile(pid_path)
    if not data:
        print("DocPrinter is not running (no pid file).")
        raise SystemExit(0)

    pid = int(data["pid"])
    if not _pid_alive(pid):
        print(f"Removing stale pid file (pid {pid} not found).")
        pid_path.unlink(missing_ok=True)
        raise SystemExit(1)

    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        pid_path.unlink(missing_ok=True)
        print("Process already exited.")
        raise SystemExit(0)

    deadline = time.monotonic() + float(args.timeout)
    while time.monotonic() < deadline:
        if not _pid_alive(pid):
            break
        time.sleep(0.2)

    if _pid_alive(pid):
        if args.force:
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            time.sleep(0.1)
        else:
            print(
                f"Process {pid} still running after {args.timeout}s; "
                "use --force to send SIGKILL.",
                file=sys.stderr,
            )
            raise SystemExit(1)

    pid_path.unlink(missing_ok=True)
    print(f"DocPrinter stopped (was pid {pid}).")


def cmd_status(args: argparse.Namespace) -> None:
    """Print whether the server process from the pid file is alive."""
    pid_path = Path(args.pid_file).expanduser().resolve()
    data = _read_pidfile(pid_path)
    if not data:
        print("status: stopped (no pid file)")
        return

    pid = int(data["pid"])
    if not _pid_alive(pid):
        print(f"status: stopped (stale pid {pid})")
        raise SystemExit(1)

    host = str(data.get("host", "?"))
    port = int(data.get("port", 0))
    cfg = data.get("config", "?")
    line = f"status: running pid={pid} config={cfg} listen={host}:{port}"
    print(line)

    if not getattr(args, "no_http", False) and port:
        url = _health_url(host, port)
        try:
            import urllib.request

            with urllib.request.urlopen(url, timeout=3.0) as resp:
                code = resp.getcode()
                print(f"health: {url} -> HTTP {code}")
        except Exception as exc:  # noqa: BLE001 — diagnostic only
            print(f"health: {url} -> unreachable ({exc})")

    return


def _normalize_argv(argv: list[str]) -> list[str]:
    """Support legacy ``python -m docprinter --config file.json`` (implicit ``run``)."""
    if not argv:
        return argv
    if argv[0] in _SUBCOMMANDS:
        return argv
    if argv[0] in ("-c", "--config", _CONFIG_FLAG_CYRILLIC):
        return ["run", *argv]
    if argv[0] == "--help" or argv[0] == "-h":
        return ["help"]
    return argv


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="docprinter",
        description="DocPrinter HTTP JSON-RPC server control",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="Run server in the foreground (blocks)")
    _add_config_argument(p_run)
    p_run.add_argument("--host", type=str, default=None, help="Override server.host")
    p_run.add_argument("--port", type=int, default=None, help="Override server.port")
    p_run.set_defaults(func=cmd_run)

    p_start = sub.add_parser(
        "start",
        help="Start server in background (default) or --foreground",
    )
    _add_config_argument(p_start)
    p_start.add_argument("--host", type=str, default=None, help="Override server.host")
    p_start.add_argument("--port", type=int, default=None, help="Override server.port")
    p_start.add_argument(
        "--pid-file",
        default=str(_default_pid_path()),
        help=(
            "Pid/metadata file (default: runtime/docprinter.pid; "
            "override with DOCPRINTER_PID_FILE)"
        ),
    )
    p_start.add_argument(
        "--log-file",
        default=str(_default_log_path()),
        help=(
            "Daemon stdout/stderr log (default: logs/docprinter-server.log; "
            "override with DOCPRINTER_LOG_FILE)"
        ),
    )
    p_start.add_argument(
        "-f",
        "--foreground",
        action="store_true",
        help="Do not detach; run in this terminal (still writes pid file for status)",
    )
    p_start.set_defaults(func=cmd_start)

    p_stop = sub.add_parser("stop", help="Stop background server (SIGTERM)")
    p_stop.add_argument(
        "--pid-file",
        default=str(_default_pid_path()),
        help="Pid file written by start (default: runtime/docprinter.pid)",
    )
    p_stop.add_argument(
        "--timeout",
        type=float,
        default=15.0,
        help="Seconds to wait after SIGTERM before failing (default: 15)",
    )
    p_stop.add_argument(
        "--force",
        action="store_true",
        help="If still alive after timeout, send SIGKILL",
    )
    p_stop.set_defaults(func=cmd_stop)

    p_status = sub.add_parser("status", help="Show whether server is running")
    p_status.add_argument(
        "--pid-file",
        default=str(_default_pid_path()),
        help="Pid file from start (default: runtime/docprinter.pid)",
    )
    p_status.add_argument(
        "--no-http",
        action="store_true",
        help="Skip GET /health check",
    )
    p_status.set_defaults(func=cmd_status)

    sub.add_parser("help", help="Show help").set_defaults(
        func=lambda _: parser.print_help()
    )

    return parser


def main() -> None:
    argv = _normalize_argv(sys.argv[1:])
    if not argv:
        _build_parser().print_help()
        raise SystemExit(0)

    parser = _build_parser()
    args = parser.parse_args(argv)
    func = getattr(args, "func", None)
    if func is None:
        parser.print_help()
        raise SystemExit(1)
    func(args)


if __name__ == "__main__":
    main()
