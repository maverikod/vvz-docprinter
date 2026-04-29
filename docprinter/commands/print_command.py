"""
MCP command: print

Word template rendering from a base64 ZIP (data.json + template.docx).

Author: Vasiliy Zdanovskiy
email: vasilyvz@gmail.com
"""

from __future__ import annotations

import base64
import binascii
import json
import logging
import shutil
import uuid
import warnings
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, Set, Type, Union

from docxtpl import DocxTemplate  # type: ignore[import-untyped]
from jinja2.exceptions import (
    TemplateAssertionError,
    TemplateError,
    TemplateNotFound,
    TemplateRuntimeError,
    TemplateSyntaxError,
    UndefinedError,
)
from mcp_proxy_adapter.commands.base import Command
from mcp_proxy_adapter.commands.result import ErrorResult, SuccessResult
from mcp_proxy_adapter.config import get_config

from docprinter.commands.registration import (
    PRINT_LEGACY_DOCBYTPL_NOTE,
    PRINT_SCHEMA_DISCOVERY_SHORT,
)
from docprinter.trace_logging import tlog

logger = logging.getLogger(__name__)

REQUIRED_ARCHIVE_MEMBERS: Set[str] = {"data.json", "template.docx"}


def _unsafe_zip_member(name: str) -> bool:
    if not name or name.endswith("/"):
        return True
    if "/" in name or "\\" in name:
        return True
    if ".." in name:
        return True
    if name in (".", ".."):
        return True
    return False


def _docprinter_paths() -> tuple[Path, Path]:
    cfg = get_config()
    out = Path(str(cfg.get("docprinter.output_dir", "runtime/output")))
    work = Path(str(cfg.get("docprinter.work_dir", "runtime/work")))
    return out, work


_PLUGIN_RESULT_KEYS = frozenset({"exitcode", "data", "errstr"})


def _unwrap_json_job_root(root: Dict[str, Any]) -> Dict[str, Any]:
    """
    Strip ``plugin_result`` / read_json shells and redundant ``{"data": …}`` layers
    so the working dict matches what operators usually store as ``data.json``.
    """
    cur: Dict[str, Any] = root

    if _PLUGIN_RESULT_KEYS.issuperset(cur.keys()) and isinstance(cur.get("data"), dict):
        cur = cur["data"]

    while (
        isinstance(cur, dict)
        and tuple(cur.keys()) == ("data",)
        and isinstance(cur["data"], dict)
        and ("template" in cur["data"] or "cmd" in cur["data"])
    ):
        cur = cur["data"]

    return cur


def _inner_if_docbytpl_triple(triple: Dict[str, Any]) -> Dict[str, Any] | None:
    """
    If ``triple`` looks like ``{template, outfile?, data: {<vars>}}``, return
    ``triple["data"]`` (the dict passed to ``DocxTemplate.render`` in legacy code).

    ``outfile`` may be omitted in some exports; then ``template`` must look like a
    ``.docx`` path so we do not treat arbitrary ``{"template": …, "data": …}``
    Jinja roots as docbytpl.
    """
    if not isinstance(triple, dict):
        return None
    inner = triple.get("data")
    if not isinstance(inner, dict):
        return None
    if "template" not in triple:
        return None
    tpl = triple.get("template")
    if not isinstance(tpl, str):
        return None
    if "outfile" not in triple and ".docx" not in tpl.lower():
        return None
    return inner


def _jinja_context_from_data_root(root: Dict[str, Any]) -> Dict[str, Any]:
    """
    Resolve the Jinja mapping for ``DocxTemplate.render``.

    Matches ``scripts-old/plugins/docbytpl.py`` after ``starter`` passes
    ``indata["data"]``: inner object is ``payload["data"]`` where ``payload`` is the
    docbytpl triple ``{template, outfile, data: {<vars>}}``. Full saved jobs wrap
    that triple under ``root["data"]`` with ``cmd`` / ``outfile`` at the top.

    Detection is driven by a **docbytpl triple** (string ``template`` + dict
    ``data``), not by fragile ordering of previous branches, so a mis-classified
    root still unwraps instead of rendering the whole JSON (~18 420-byte UNI act).
    """
    cur = _unwrap_json_job_root(root)

    mid = cur.get("data")
    if isinstance(mid, dict):
        got = _inner_if_docbytpl_triple(mid)
        if got is not None:
            return got

    got = _inner_if_docbytpl_triple(cur)
    if got is not None:
        return got

    return cur


class PrintCommand(Command):
    """
    Fill a Word ``.docx`` template from JSON context supplied inside a base64 ZIP.
    """

    name = "print"
    version = "0.2.3"
    descr = (
        "Render a .docx Jinja template from JSON context. "
        "Params are a single base64 ZIP with ``data.json`` and ``template.docx``."
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
            "title": "print",
            "description": (
                "Decode a base64 ZIP that must contain exactly ``data.json`` and "
                "``template.docx`` at archive root, render with docxtpl, and store the "
                "result under the configured output directory. Returns ``result_id`` "
                "only (no filesystem paths). "
                f"{PRINT_LEGACY_DOCBYTPL_NOTE} "
                f"{PRINT_SCHEMA_DISCOVERY_SHORT}"
            ),
            "properties": {
                "archive": {
                    "type": "string",
                    "description": (
                        "Base64-encoded ZIP with exactly ``data.json`` and "
                        "``template.docx`` at the root "
                        "(no subdirectories or extra files)."
                    ),
                    "contentEncoding": "base64",
                },
            },
            "required": ["archive"],
            "additionalProperties": False,
            "examples": [],
        }

    @classmethod
    def metadata(cls: Type["PrintCommand"]) -> Dict[str, Any]:
        """Rich discovery for humans and doc generators (code_analysis pattern)."""
        return {
            "name": cls.name,
            "version": cls.version,
            "description": cls.descr,
            "detailed_description": (
                "Accepts a single ``archive`` parameter: base64 ZIP with "
                "``data.json`` and ``template.docx``. "
                "If ``data.json`` matches the legacy docbytpl shape "
                "(``data.template``, ``data.outfile``, ``data.data`` or the same "
                "triple at the root), the inner ``data`` object is passed to "
                "``DocxTemplate.render``—same as ``scripts-old/plugins/docbytpl``. "
                "Otherwise the whole ``data.json`` root is the Jinja context. "
                "The server unpacks, renders, writes ``<result_id>.docx`` under "
                "``docprinter.output_dir``, and returns ``result_id`` only. "
                f"Work dirs are removed after the call.\n\n{PRINT_LEGACY_DOCBYTPL_NOTE}"
            ),
            "category": cls.category,
            "author": cls.author,
            "email": cls.email,
            "parameters": {
                "archive": {
                    "description": (
                        "Base64 ZIP containing exactly ``data.json`` and "
                        "``template.docx``."
                    ),
                    "required": True,
                },
            },
            "usage_examples": [
                {
                    "description": (
                        "Client builds ZIP with template + data, sends base64"
                    ),
                    "params": {
                        "archive": ("<base64 of zip with data.json and template.docx>"),
                    },
                },
            ],
            "error_codes": [
                "INVALID_BASE64",
                "INVALID_ARCHIVE",
                "UNSAFE_ARCHIVE_MEMBER",
                "ARCHIVE_MISSING_REQUIRED_FILES",
                "INVALID_DATA_TYPE",
                "TEMPLATE_NOT_FOUND",
                "TEMPLATE_ASSERTION_ERROR",
                "TEMPLATE_SYNTAX_ERROR",
                "TEMPLATE_UNDEFINED",
                "TEMPLATE_RUNTIME_ERROR",
                "TEMPLATE_ERROR",
                "RENDER_VALUE_ERROR",
                "RENDER_UNEXPECTED_ERROR",
            ],
            "error_codes_note": (
                "``-32602``: ``INVALID_BASE64``, ``INVALID_ARCHIVE``, "
                "``UNSAFE_ARCHIVE_MEMBER``, ``ARCHIVE_MISSING_REQUIRED_FILES``, "
                "``INVALID_DATA_TYPE``. "
                "``-32603``: template/render failures (``TEMPLATE_*``, "
                "``RENDER_VALUE_ERROR``, ``RENDER_UNEXPECTED_ERROR``)."
            ),
        }

    @classmethod
    def get_result_schema(cls) -> Dict[str, Any]:
        """Structured success payload for tools that merge result schemas."""
        return {
            "type": "object",
            "title": "print_success",
            "properties": {
                "success": {"type": "boolean", "const": True},
                "data": {
                    "type": "object",
                    "properties": {
                        "result_id": {
                            "type": "string",
                            "format": "uuid",
                            "description": (
                                "UUID4 of the rendered file in runtime/output/. "
                                "Filename is <result_id>.docx."
                            ),
                        }
                    },
                    "required": ["result_id"],
                },
            },
            "required": ["success", "data"],
        }

    def _render_error(self, error_code: str, exc: BaseException) -> ErrorResult:
        return ErrorResult(
            message=str(exc),
            code=-32603,
            details={"error_code": error_code, "errstr": str(exc)},
        )

    async def execute(  # type: ignore[override]
        self, **kwargs: Any
    ) -> Union[SuccessResult, ErrorResult]:
        """Decode ZIP, render template, return ``result_id`` or ``ErrorResult``."""
        tlog("print", "01_enter_execute")
        archive_b64 = kwargs.get("archive")
        if not isinstance(archive_b64, str) or not archive_b64.strip():
            tlog("print", "02_fail_invalid_archive_param", reason="not_non_empty_str")
            return ErrorResult(
                message="Parameter 'archive' must be a non-empty string",
                code=-32602,
                details={"error_code": "INVALID_DATA_TYPE", "field": "archive"},
            )

        b64_len = len(archive_b64)
        tlog("print", "03_archive_param_ok", archive_base64_chars=b64_len)
        logger.info(
            "print: start execute archive_base64_chars=%s (if this line never "
            "appears, the HTTP/ASGI layer rejected the body before the command ran)",
            b64_len,
        )

        try:
            raw = base64.b64decode(archive_b64, validate=True)
        except (binascii.Error, ValueError) as exc:
            tlog("print", "04_fail_base64_decode", err=str(exc))
            logger.info("print: base64 decode failed: %s", exc)
            return ErrorResult(
                message="Invalid base64 in 'archive'",
                code=-32602,
                details={"error_code": "INVALID_BASE64", "errstr": str(exc)},
            )

        tlog("print", "05_base64_decoded_ok", zip_bytes=len(raw))
        logger.info(
            "print: decoded zip_bytes=%s (approx JSON-RPC body was ~%s chars for "
            "archive field alone)",
            len(raw),
            b64_len,
        )

        output_dir, work_root = _docprinter_paths()
        output_dir.mkdir(parents=True, exist_ok=True)
        work_root.mkdir(parents=True, exist_ok=True)

        request_uuid = uuid.uuid4()
        work_path = work_root / str(request_uuid)
        work_path.mkdir(parents=True, exist_ok=True)
        tlog(
            "print",
            "06_workdir_ready",
            work_path=str(work_path),
            output_dir=str(output_dir),
        )

        try:
            try:
                zf = zipfile.ZipFile(BytesIO(raw))
            except zipfile.BadZipFile as exc:
                tlog("print", "07_fail_zip_open", err=str(exc))
                logger.info("print: invalid zip: %s", exc)
                return ErrorResult(
                    message="Archive is not a valid ZIP",
                    code=-32602,
                    details={"error_code": "INVALID_ARCHIVE", "errstr": str(exc)},
                )

            with zf:
                names = [n for n in zf.namelist() if n and not n.endswith("/")]
                tlog("print", "08_zip_opened", member_count=len(names))
                logger.info(
                    "print: zip opened members=%s work_dir=%s",
                    len(names),
                    work_path,
                )
                for name in names:
                    if _unsafe_zip_member(name):
                        tlog("print", "09_fail_unsafe_zip_member", member=name)
                        return ErrorResult(
                            message=f"Unsafe archive member: {name!r}",
                            code=-32602,
                            details={
                                "error_code": "UNSAFE_ARCHIVE_MEMBER",
                                "member": name,
                            },
                        )

                file_names = {n for n in names}
                if file_names != REQUIRED_ARCHIVE_MEMBERS:
                    tlog(
                        "print",
                        "10_fail_archive_members_mismatch",
                        found=sorted(file_names),
                        missing=sorted(REQUIRED_ARCHIVE_MEMBERS - file_names),
                    )
                    missing = sorted(REQUIRED_ARCHIVE_MEMBERS - file_names)
                    return ErrorResult(
                        message=(
                            "Archive must contain exactly data.json and template.docx"
                        ),
                        code=-32602,
                        details={
                            "error_code": "ARCHIVE_MISSING_REQUIRED_FILES",
                            "missing": missing,
                            "found": sorted(file_names),
                        },
                    )

                for name in names:
                    zf.extract(name, work_path)

            tlog("print", "11_extracted_zip_to_workdir")
            logger.info("print: extracted required files to work dir")

            data_path = work_path / "data.json"
            try:
                with data_path.open("r", encoding="utf-8-sig") as handle:
                    data_obj = json.load(handle)
            except (json.JSONDecodeError, OSError) as exc:
                tlog("print", "12_fail_data_json_read", err=str(exc))
                return ErrorResult(
                    message="Invalid data.json",
                    code=-32602,
                    details={"error_code": "INVALID_ARCHIVE", "errstr": str(exc)},
                )

            if not isinstance(data_obj, dict):
                tlog(
                    "print",
                    "13_fail_data_json_root_type",
                    received_type=type(data_obj).__name__,
                )
                return ErrorResult(
                    message="data.json root must be a JSON object",
                    code=-32602,
                    details={
                        "error_code": "INVALID_DATA_TYPE",
                        "received_type": type(data_obj).__name__,
                    },
                )

            tlog("print", "14_data_json_ok")
            jinja_context = _jinja_context_from_data_root(data_obj)
            if not isinstance(jinja_context, dict):
                tlog(
                    "print",
                    "15_fail_jinja_context_type",
                    received_type=type(jinja_context).__name__,
                )
                return ErrorResult(
                    message="Resolved Jinja context must be a JSON object",
                    code=-32602,
                    details={
                        "error_code": "INVALID_DATA_TYPE",
                        "received_type": type(jinja_context).__name__,
                    },
                )

            template_path = work_path / "template.docx"
            result_uuid = uuid.uuid4()
            out_path = output_dir / f"{result_uuid}.docx"

            tlog(
                "print",
                "16_render_start",
                result_id=str(result_uuid),
                jinja_keys_sample=list(jinja_context)[:20],
            )
            logger.info(
                "print: rendering template.docx -> %s (jinja keys sample: %s)",
                result_uuid,
                list(jinja_context)[:12],
            )

            try:
                doc = DocxTemplate(str(template_path))
                doc.render(jinja_context)
                with warnings.catch_warnings():
                    warnings.filterwarnings(
                        "ignore", category=UserWarning, module="zipfile"
                    )
                    doc.save(str(out_path))
            except TemplateNotFound as exc:
                tlog("print", "17_fail_TEMPLATE_NOT_FOUND", err=str(exc))
                return self._render_error("TEMPLATE_NOT_FOUND", exc)
            except TemplateAssertionError as exc:
                tlog("print", "17_fail_TEMPLATE_ASSERTION_ERROR", err=str(exc))
                return self._render_error("TEMPLATE_ASSERTION_ERROR", exc)
            except TemplateSyntaxError as exc:
                tlog("print", "17_fail_TEMPLATE_SYNTAX_ERROR", err=str(exc))
                return self._render_error("TEMPLATE_SYNTAX_ERROR", exc)
            except UndefinedError as exc:
                tlog("print", "17_fail_TEMPLATE_UNDEFINED", err=str(exc))
                return self._render_error("TEMPLATE_UNDEFINED", exc)
            except TemplateRuntimeError as exc:
                tlog("print", "17_fail_TEMPLATE_RUNTIME_ERROR", err=str(exc))
                return self._render_error("TEMPLATE_RUNTIME_ERROR", exc)
            except TemplateError as exc:
                tlog("print", "17_fail_TEMPLATE_ERROR", err=str(exc))
                return self._render_error("TEMPLATE_ERROR", exc)
            except ValueError as exc:
                tlog("print", "17_fail_RENDER_VALUE_ERROR", err=str(exc))
                return self._render_error("RENDER_VALUE_ERROR", exc)
            except Exception as exc:  # noqa: BLE001
                tlog("print", "17_fail_RENDER_UNEXPECTED_ERROR", err=str(exc))
                logger.exception("Unexpected render error")
                return self._render_error("RENDER_UNEXPECTED_ERROR", exc)

            out_sz = out_path.stat().st_size if out_path.is_file() else 0
            tlog(
                "print",
                "18_success",
                result_id=str(result_uuid),
                out_bytes=out_sz,
            )
            logger.info(
                "print: success result_id=%s out_bytes=%s",
                result_uuid,
                out_sz,
            )
            return SuccessResult(
                data={"result_id": str(result_uuid)},
                message=None,
            )
        finally:
            tlog("print", "99_finally_cleanup_workdir", work_path=str(work_path))
            shutil.rmtree(work_path, ignore_errors=True)
