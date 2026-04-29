#!/usr/bin/env python3
"""
Orchestrates DocPrinter HTTP server lifecycle.

Loads config, builds the ASGI app, runtime dirs, sweeper, and Hypercorn.

Author: Vasiliy Zdanovskiy
email: vasilyvz@gmail.com
"""

from __future__ import annotations

import json
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mcp_proxy_adapter.api.app import create_app
from mcp_proxy_adapter.commands.command_registry import registry
from mcp_proxy_adapter.config import get_config
from mcp_proxy_adapter.core.app_factory.ssl_config import build_server_ssl_config
from mcp_proxy_adapter.core.config.simple_config import SimpleConfig
from mcp_proxy_adapter.core.config.simple_config_validator import SimpleConfigValidator
from mcp_proxy_adapter.core.server_engine import ServerEngineFactory

from docprinter.commands.get_print_result_command import GetPrintResultCommand
from docprinter.commands.print_command import PrintCommand
from docprinter.runtime.sweeper import RuntimeSweeper
from docprinter.trace_logging import configure_trace_log_file, tlog

logger = logging.getLogger(__name__)

_DOCPRINTER_LOG_HANDLER_MARKER = "_docprinter_stderr_handler"


def _configure_docprinter_logging(app_config: dict[str, Any]) -> None:
    """
    Ensure ``docprinter.*`` loggers emit to stderr with level from ``server.log_level``.

    Hypercorn may configure the root logger elsewhere; we attach one handler on the
    ``docprinter`` logger so command diagnostics (e.g. large ``print`` payloads) are
    visible without duplicating library noise.
    """
    server = app_config.get("server") or {}
    level_name = str(server.get("log_level", "INFO")).upper()
    level = getattr(logging, level_name, logging.INFO)
    dp = logging.getLogger("docprinter")
    dp.setLevel(level)
    if not any(
        getattr(h, _DOCPRINTER_LOG_HANDLER_MARKER, False) for h in dp.handlers
    ):
        handler = logging.StreamHandler(sys.stderr)
        setattr(handler, _DOCPRINTER_LOG_HANDLER_MARKER, True)
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)s [%(name)s] %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        dp.addHandler(handler)


def _configure_docprinter_trace_file(app_config: dict[str, Any]) -> None:
    """
    ``docprinter.trace_log_file``: append-only UTF-8 step trace.

    * Key **absent** or value ``null`` / empty string: trace file disabled.
    * Non-empty string: log path (relative paths are resolved from process ``cwd``).
    """
    doc = app_config.get("docprinter") or {}
    server = app_config.get("server") or {}
    level_name = str(server.get("log_level", "INFO"))
    if "trace_log_file" not in doc:
        configure_trace_log_file(None, log_level_name=level_name)
        return
    raw_val = doc.get("trace_log_file")
    if raw_val is None:
        configure_trace_log_file(None, log_level_name=level_name)
        return
    path_str = str(raw_val).strip()
    if not path_str:
        configure_trace_log_file(None, log_level_name=level_name)
        return
    configure_trace_log_file(path_str, log_level_name=level_name)


@dataclass(frozen=True)
class DocprinterRuntimeSettings:
    """Resolved ``docprinter`` section: paths and sweeper tuning."""

    output_dir: Path
    work_dir: Path
    output_ttl_seconds: int
    sweep_interval_seconds: int

    @classmethod
    def from_global_config(cls) -> DocprinterRuntimeSettings:
        cfg = get_config()
        output_dir = Path(str(cfg.get("docprinter.output_dir", "runtime/output")))
        work_dir = Path(str(cfg.get("docprinter.work_dir", "runtime/work")))
        ttl = int(cfg.get("docprinter.output_ttl_seconds", 3600))
        interval = int(cfg.get("docprinter.sweep_interval_seconds", 300))
        return cls(
            output_dir=output_dir,
            work_dir=work_dir,
            output_ttl_seconds=ttl,
            sweep_interval_seconds=interval,
        )


def register_docprinter_commands() -> None:
    """Register DocPrinter MCP commands (``print`` + ``get_print_result``)."""
    registry.register(PrintCommand, "custom")
    registry.register(GetPrintResultCommand, "custom")


class ServerManager:
    """
    Load server JSON, validate, publish to ``get_config()``, build ASGI app,
    ensure runtime directories, run background sweeper, and block on Hypercorn.
    """

    def __init__(self, config_path: Path) -> None:
        self._config_path = config_path.resolve()
        self._app_config: dict[str, Any] | None = None
        self._model: Any = None
        self._simple_config: SimpleConfig | None = None
        self._app: Any = None
        self._sweeper: RuntimeSweeper | None = None
        self._runtime: DocprinterRuntimeSettings | None = None
        self._server_engine_config: dict[str, Any] | None = None

    @property
    def config_path(self) -> Path:
        return self._config_path

    @property
    def app_config(self) -> dict[str, Any]:
        if self._app_config is None:
            raise RuntimeError("ServerManager.prepare() was not called")
        return self._app_config

    @property
    def app(self) -> Any:
        if self._app is None:
            raise RuntimeError("ServerManager.prepare() was not called")
        return self._app

    @property
    def runtime_settings(self) -> DocprinterRuntimeSettings:
        if self._runtime is None:
            raise RuntimeError("ServerManager.prepare() was not called")
        return self._runtime

    def load_raw_config(self) -> dict[str, Any]:
        """Read JSON from ``config_path``; on failure print to stderr and exit."""
        if not self._config_path.is_file():
            print(f"Configuration file not found: {self._config_path}", file=sys.stderr)
            raise SystemExit(1)
        try:
            with self._config_path.open("r", encoding="utf-8") as handle:
                return json.load(handle)
        except json.JSONDecodeError as exc:
            print(f"Invalid JSON configuration: {exc}", file=sys.stderr)
            raise SystemExit(1) from exc

    def validate_and_merge_model(self, app_config: dict[str, Any]) -> Any:
        """Load ``SimpleConfig``, validate, merge model dict into ``app_config``."""
        simple_config = SimpleConfig(str(self._config_path))
        model = simple_config.load()
        validator = SimpleConfigValidator(config_path=str(self._config_path))
        errors = validator.validate(model)
        if errors:
            print("Configuration validation failed:", file=sys.stderr)
            for err in errors:
                print(f"  - {err.message}", file=sys.stderr)
            raise SystemExit(1)

        simple_config.model = model
        merged = simple_config.to_dict()
        for section, value in merged.items():
            app_config[section] = value

        app_config.setdefault("server", {})
        app_config["server"].setdefault("debug", False)
        app_config["server"].setdefault("log_level", "INFO")

        self._simple_config = simple_config
        self._model = model
        return model

    def apply_cli_overrides(
        self,
        app_config: dict[str, Any],
        *,
        host: str | None,
        port: int | None,
    ) -> None:
        if port is not None:
            app_config.setdefault("server", {})["port"] = port
            if self._model is not None:
                self._model.server.port = port
        if host is not None:
            app_config.setdefault("server", {})["host"] = host
            if self._model is not None:
                self._model.server.host = host

    def publish_config_to_globals(self, app_config: dict[str, Any]) -> None:
        """Sync merged config into process-wide ``get_config()``."""
        cfg = get_config()
        cfg.config_path = str(self._config_path)
        setattr(cfg, "model", self._model)
        cfg.config_data = app_config
        if hasattr(cfg, "feature_manager"):
            cfg.feature_manager.config_data = cfg.config_data

    def assert_transport_consistent(self, app_config: dict[str, Any]) -> None:
        """Reject incompatible protocol and TLS combinations."""
        server_cfg = app_config.get("server", {}) or {}
        proto = str(server_cfg.get("protocol", "http")).lower()
        ssl_block = server_cfg.get("ssl") or {}
        cert_file = ssl_block.get("cert") if ssl_block else None
        key_file = ssl_block.get("key") if ssl_block else None
        ca_cert_file = ssl_block.get("ca") if ssl_block else None
        transport = app_config.get("transport", {}) or {}
        require_client_cert = bool(transport.get("verify_client") or (proto == "mtls"))

        if proto == "http" and require_client_cert:
            raise SystemExit(
                "Configuration error: client certificate verification "
                "cannot be used with HTTP."
            )
        if proto == "mtls":
            if not (cert_file and key_file):
                raise SystemExit(
                    "Configuration error: mtls requires server.ssl.cert "
                    "and server.ssl.key."
                )
            if not require_client_cert:
                raise SystemExit(
                    "Configuration error: mtls requires transport.verify_client=true."
                )
            if not ca_cert_file:
                raise SystemExit("Configuration error: mtls requires server.ssl.ca.")

    def build_asgi_app(self, app_config: dict[str, Any]) -> Any:
        """Create Quart/ASGI application and register DocPrinter commands."""
        app = create_app(
            title="DocPrinter",
            description=(
                "HTTP JSON-RPC service for Word template printing from JSON data"
            ),
            version="0.1.0",
            app_config=app_config,
            config_path=str(self._config_path),
        )
        register_docprinter_commands()
        self._app = app
        return app

    def ensure_runtime_directories(self, settings: DocprinterRuntimeSettings) -> None:
        """Create ``output_dir`` and ``work_dir`` if missing."""
        settings.output_dir.mkdir(parents=True, exist_ok=True)
        settings.work_dir.mkdir(parents=True, exist_ok=True)

    def build_hypercorn_config(self, app_config: dict[str, Any]) -> dict[str, Any]:
        """Host, port, log level, and optional SSL for ``ServerEngineFactory``."""
        port = int(app_config.get("server", {}).get("port", 8080))
        host = str(app_config.get("server", {}).get("host", "0.0.0.0"))
        server_config: dict[str, Any] = {
            "host": host,
            "port": port,
            "log_level": "info",
            "reload": False,
        }
        try:
            ssl_engine = build_server_ssl_config(app_config)
            if ssl_engine:
                server_config.update(ssl_engine)
        except ValueError as exc:
            print(f"SSL configuration invalid: {exc}", file=sys.stderr)
            raise SystemExit(1) from exc
        self._server_engine_config = server_config
        return server_config

    def prepare(
        self,
        *,
        cli_host: str | None = None,
        cli_port: int | None = None,
    ) -> None:
        """
        Load config, validate, sync globals, build ASGI app, resolve runtime paths,
        and create output/work directories.
        """
        app_config = self.load_raw_config()
        self.validate_and_merge_model(app_config)
        self.apply_cli_overrides(app_config, host=cli_host, port=cli_port)
        self.assert_transport_consistent(app_config)
        self.publish_config_to_globals(app_config)
        self._app_config = app_config

        _configure_docprinter_logging(app_config)
        _configure_docprinter_trace_file(app_config)

        self.build_asgi_app(app_config)

        try:
            import docprinter.commands.print_command as _pc

            logger.info(
                "Loaded print_command from %s (command version %s)",
                _pc.__file__,
                getattr(PrintCommand, "version", "?"),
            )
        except Exception:  # noqa: BLE001 — diagnostic only
            logger.warning("Could not resolve print_command module path", exc_info=True)

        self._runtime = DocprinterRuntimeSettings.from_global_config()
        self.ensure_runtime_directories(self._runtime)
        self.build_hypercorn_config(app_config)
        logger.info(
            "DocPrinter prepared: config=%s host=%s port=%s",
            self._config_path,
            app_config.get("server", {}).get("host"),
            app_config.get("server", {}).get("port"),
        )
        tlog(
            "server",
            "prepare_complete",
            config_path=str(self._config_path),
            host=str(app_config.get("server", {}).get("host", "")),
            port=str(app_config.get("server", {}).get("port", "")),
        )

    def run_server(self) -> None:
        """
        Start ``RuntimeSweeper``, run Hypercorn until stop, then stop sweeper.
        Requires ``prepare()`` first.
        """
        if (
            self._app is None
            or self._runtime is None
            or self._server_engine_config is None
        ):
            raise RuntimeError(
                "ServerManager.prepare() must be called before run_server()"
            )

        engine = ServerEngineFactory.get_engine("hypercorn")
        if not engine:
            raise RuntimeError("Hypercorn engine is not available")

        sweeper = RuntimeSweeper(
            self._runtime.output_dir,
            self._runtime.work_dir,
            self._runtime.output_ttl_seconds,
            self._runtime.sweep_interval_seconds,
        )
        self._sweeper = sweeper
        sweeper.start()
        try:
            tlog(
                "server",
                "hypercorn_listen_start",
                host=str(self._server_engine_config.get("host", "")),
                port=str(self._server_engine_config.get("port", "")),
            )
            logger.info("DocPrinter listening (Hypercorn)")
            engine.run_server(self._app, self._server_engine_config)
        finally:
            sweeper.stop()
            self._sweeper = None
            logger.info("DocPrinter server stopped")

    def run(
        self,
        *,
        cli_host: str | None = None,
        cli_port: int | None = None,
    ) -> None:
        """``prepare()`` then ``run_server()``."""
        self.prepare(cli_host=cli_host, cli_port=cli_port)
        self.run_server()


__all__ = [
    "DocprinterRuntimeSettings",
    "ServerManager",
    "register_docprinter_commands",
]
