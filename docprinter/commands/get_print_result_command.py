"""
MCP command: get_print_result

Return a rendered ``.docx`` as base64 by ``result_id`` from ``print``.

Author: Vasiliy Zdanovskiy
email: vasilyvz@gmail.com
"""

from __future__ import annotations

import base64
import logging
import uuid
from pathlib import Path
from typing import Any, Dict, Type, Union

from mcp_proxy_adapter.commands.base import Command
from mcp_proxy_adapter.commands.result import ErrorResult, SuccessResult
from mcp_proxy_adapter.config import get_config

from docprinter.commands.registration import (
    PRINT_RESULT_COMPANION_NOTE,
    PRINT_SCHEMA_DISCOVERY_SHORT,
)
from docprinter.trace_logging import tlog

DOCX_MEDIA_TYPE = (
    "application/vnd.openxmlformats-officedocument." "wordprocessingml.document"
)

logger = logging.getLogger(__name__)


def _output_dir() -> Path:
    cfg = get_config()
    return Path(str(cfg.get("docprinter.output_dir", "runtime/output")))


class GetPrintResultCommand(Command):
    """
    Load ``<result_id>.docx`` from the configured output directory; return base64.
    """

    name = "get_print_result"
    version = "0.2.4"
    descr = (
        "Fetch a rendered Word document by ``result_id`` returned from ``print``. "
        "Payload is base64-encoded file bytes."
    )
    category = "docprinter"
    author = "Vasiliy Zdanovskiy"
    email = "vasilyvz@gmail.com"
    use_queue = False

    @classmethod
    def get_schema(cls) -> Dict[str, Any]:
        """Authoritative JSON Schema for JSON-RPC ``params`` (strict)."""
        return {
            "type": "object",
            "title": "get_print_result",
            "description": (
                "Return the ``.docx`` produced by ``print`` for the given UUID. "
                "The file may be absent if it was never created, the id is wrong, or "
                "the runtime sweeper deleted it after ``output_ttl_seconds``. "
                f"{PRINT_RESULT_COMPANION_NOTE} "
                f"{PRINT_SCHEMA_DISCOVERY_SHORT}"
            ),
            "properties": {
                "result_id": {
                    "type": "string",
                    "format": "uuid",
                    "description": (
                        "UUID returned by ``print`` in ``data.result_id`` "
                        "(same value as the ``.docx`` basename without extension)."
                    ),
                },
            },
            "required": ["result_id"],
            "additionalProperties": False,
            "examples": [
                {"result_id": "22222222-2222-4222-8222-222222222222"},
            ],
        }

    @classmethod
    def metadata(cls: Type["GetPrintResultCommand"]) -> Dict[str, Any]:
        """Rich discovery for humans and doc generators (code_analysis pattern)."""
        return {
            "name": cls.name,
            "version": cls.version,
            "description": cls.descr,
            "detailed_description": (
                "Reads ``<result_id>.docx`` from ``docprinter.output_dir`` and returns "
                "``document_base64`` plus a MIME type hint. If the file is missing, "
                "returns ``RESULT_NOT_FOUND`` (same outcome whether the id never "
                "existed or the document was evicted by the TTL sweeper).\n\n"
                f"{PRINT_RESULT_COMPANION_NOTE}"
            ),
            "category": cls.category,
            "author": cls.author,
            "email": cls.email,
            "parameters": {
                "result_id": {
                    "description": "UUID from ``print`` success payload.",
                    "required": True,
                },
            },
            "usage_examples": [
                {
                    "description": "After ``print``, fetch the rendered document",
                    "params": {"result_id": "22222222-2222-4222-8222-222222222222"},
                },
            ],
            "error_codes": [
                "INVALID_DATA_TYPE",
                "RESULT_ID_INVALID",
                "RESULT_NOT_FOUND",
                "RESULT_READ_FAILED",
            ],
            "error_codes_note": (
                "``-32602``: ``INVALID_DATA_TYPE`` (missing/empty ``result_id``); "
                "``RESULT_ID_INVALID`` (not a UUID); ``RESULT_NOT_FOUND`` (no file or "
                "removed by TTL sweeper). "
                "``-32603``: ``RESULT_READ_FAILED`` (I/O while reading the file)."
            ),
            "return_value": {
                "success": {
                    "description": "Rendered document returned as base64.",
                    "data": {
                        "result_id": "Echo of the requested UUID.",
                        "content_type": DOCX_MEDIA_TYPE,
                        "document_base64": "Standard base64 of the ``.docx`` bytes.",
                    },
                    "example": {
                        "result_id": "22222222-2222-4222-8222-222222222222",
                        "content_type": DOCX_MEDIA_TYPE,
                        "document_base64": "<base64 of .docx>",
                    },
                },
                "error": {
                    "description": "Invalid id or missing/expired output file.",
                    "code": "JSON-RPC ``-32602`` or ``-32603`` for read I/O",
                    "details": {
                        "error_code": "Stable string from ``error_codes``",
                        "result_id": "Canonical UUID when parsed",
                    },
                },
            },
            "error_cases": [
                {
                    "description": "Parameter missing or empty.",
                    "message": "Parameter 'result_id' must be a non-empty string",
                    "solution": "Pass the ``result_id`` string returned by ``print``.",
                },
                {
                    "description": "String is not a valid UUID.",
                    "message": "Invalid UUID in 'result_id'",
                    "solution": "Use the exact UUID from ``print`` success payload.",
                },
                {
                    "description": "Output file absent (never created or sweeper TTL).",
                    "message": "Rendered document not found for this result_id",
                    "solution": "Call soon after ``print``; check ``docprinter.output_ttl_seconds``.",
                },
                {
                    "description": "File existed but could not be read from disk.",
                    "message": "Failed to read document",
                    "solution": "Check server logs and permissions on ``docprinter.output_dir``.",
                },
            ],
            "best_practices": [
                "Always use the ``result_id`` from the immediately preceding ``print`` call.",
                "Decode ``document_base64`` and save as ``<result_id>.docx`` on the client.",
                "Do not retry indefinitely after ``RESULT_NOT_FOUND``; re-run ``print`` instead.",
                "Large documents inflate in base64; prefer fetching once right after render.",
            ],
        }

    @classmethod
    def get_result_schema(cls) -> Dict[str, Any]:
        """Structured success payload for tools that merge result schemas."""
        return {
            "type": "object",
            "title": "get_print_result_success",
            "properties": {
                "success": {"type": "boolean", "const": True},
                "data": {
                    "type": "object",
                    "properties": {
                        "result_id": {
                            "type": "string",
                            "format": "uuid",
                            "description": "Echo of the requested id.",
                        },
                        "content_type": {
                            "type": "string",
                            "const": DOCX_MEDIA_TYPE,
                            "description": "MIME type for the decoded bytes.",
                        },
                        "document_base64": {
                            "type": "string",
                            "contentEncoding": "base64",
                            "description": "The ``.docx`` file as standard base64.",
                        },
                    },
                    "required": ["result_id", "content_type", "document_base64"],
                },
            },
            "required": ["success", "data"],
        }

    async def execute(  # type: ignore[override]
        self, **kwargs: Any
    ) -> Union[SuccessResult, ErrorResult]:
        """Resolve ``result_id`` to a file under ``output_dir`` or return errors."""
        tlog("get_print_result", "01_enter_execute")
        raw_id = kwargs.get("result_id")
        if not isinstance(raw_id, str) or not raw_id.strip():
            tlog("get_print_result", "02_fail_invalid_result_id_param")
            return ErrorResult(
                message="Parameter 'result_id' must be a non-empty string",
                code=-32602,
                details={"error_code": "INVALID_DATA_TYPE", "field": "result_id"},
            )

        text = raw_id.strip()
        try:
            parsed = uuid.UUID(text)
        except ValueError:
            tlog("get_print_result", "03_fail_uuid_parse", result_id=text)
            return ErrorResult(
                message=f"Invalid UUID in 'result_id': {text!r}",
                code=-32602,
                details={"error_code": "RESULT_ID_INVALID", "result_id": text},
            )

        canonical = str(parsed)
        tlog("get_print_result", "04_uuid_ok", result_id=canonical)
        logger.info("get_print_result: start result_id=%s", canonical)
        out_dir = _output_dir()
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"{canonical}.docx"
        tlog("get_print_result", "05_resolve_path", path=str(path))

        if not path.is_file():
            tlog("get_print_result", "06_fail_result_not_found", path=str(path))
            return ErrorResult(
                message=(
                    "Rendered document not found for this result_id. "
                    "It may never have existed, or it was removed after "
                    "docprinter.output_ttl_seconds (sweeper)."
                ),
                code=-32602,
                details={
                    "error_code": "RESULT_NOT_FOUND",
                    "result_id": canonical,
                    "may_have_been_removed_by_ttl": True,
                },
            )

        logger.info("get_print_result: found file path=%s", path)

        try:
            blob = path.read_bytes()
        except OSError as exc:
            tlog("get_print_result", "07_fail_read_file", err=str(exc))
            return ErrorResult(
                message=f"Failed to read document: {exc}",
                code=-32603,
                details={
                    "error_code": "RESULT_READ_FAILED",
                    "result_id": canonical,
                    "errstr": str(exc),
                },
            )

        b64_doc = base64.b64encode(blob).decode("ascii")
        tlog(
            "get_print_result",
            "08_success",
            result_id=canonical,
            doc_bytes=len(blob),
            document_base64_chars=len(b64_doc),
        )
        logger.info(
            "get_print_result: success doc_bytes=%s document_base64_chars=%s",
            len(blob),
            len(b64_doc),
        )
        return SuccessResult(
            data={
                "result_id": canonical,
                "content_type": DOCX_MEDIA_TYPE,
                "document_base64": b64_doc,
            },
            message=None,
        )
