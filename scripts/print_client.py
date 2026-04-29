#!/usr/bin/env python3
"""
CLI client: pack ``data.json`` + ``template.docx``, call ``print``, then
``get_print_result`` and write the rendered ``.docx`` locally.

Usage::

    python scripts/print_client.py CONTEXT.json TEMPLATE.docx
    python scripts/print_client.py data.json tpl.docx -o out.docx

Requires Python 3.10+ (stdlib only: no extra pip packages).

Author: Vasiliy Zdanovskiy
email: vasilyvz@gmail.com
"""

from __future__ import annotations

import argparse
import base64
import binascii
import json
import sys
import time
import urllib.error
import urllib.request
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, Tuple

JsonDict = Dict[str, Any]


def _vlog(verbose: bool, message: str) -> None:
    if not verbose:
        return
    ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    print(f"[{ts}] {message}", file=sys.stderr)


def _build_archive_bytes(data_path: Path, template_path: Path) -> bytes:
    """ZIP with exactly ``data.json`` and ``template.docx`` (server contract)."""
    data_bytes = data_path.read_bytes()
    try:
        parsed = json.loads(data_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Invalid JSON in {data_path}: {exc}") from exc
    if not isinstance(parsed, dict):
        raise SystemExit(
            f"{data_path} must contain a JSON object at the root (got "
            f"{type(parsed).__name__})."
        )

    tpl_bytes = template_path.read_bytes()
    if not tpl_bytes.startswith(b"PK"):
        print(
            f"Warning: {template_path} does not look like a .docx (ZIP) file.",
            file=sys.stderr,
        )

    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("data.json", data_bytes)
        zf.writestr("template.docx", tpl_bytes)
    return buf.getvalue()


def _post_jsonrpc(
    url: str,
    payload: JsonDict,
    timeout: float,
    *,
    verbose: bool = False,
    label: str = "jsonrpc",
) -> JsonDict:
    body = json.dumps(payload).encode("utf-8")
    _vlog(
        verbose,
        f"{label}: POST {url} request_body_bytes={len(body)} "
        f"timeout_s={timeout}",
    )
    t0 = time.monotonic()
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            _vlog(
                verbose,
                f"{label}: HTTP {resp.status} response_bytes={len(raw)} "
                f"elapsed_s={time.monotonic() - t0:.3f}",
            )
    except urllib.error.HTTPError as exc:
        text = exc.read().decode("utf-8", errors="replace")
        hdrs = getattr(exc, "headers", None)
        hdr_dump = ""
        if hdrs:
            hdr_dump = "".join(f"\n  {k}: {v}" for k, v in hdrs.items())
        _vlog(
            verbose,
            f"{label}: HTTP {exc.code} after_s={time.monotonic() - t0:.3f}"
            f"{hdr_dump}",
        )
        detail = text or exc.reason
        if len(detail) > 2000:
            detail = detail[:2000] + "…(truncated)"
        raise SystemExit(
            f"HTTP {exc.code}: {detail or exc.reason}"
        ) from exc
    except urllib.error.URLError as exc:
        _vlog(
            verbose,
            f"{label}: connection error after_s={time.monotonic() - t0:.3f}: {exc}",
        )
        raise SystemExit(f"Request failed: {exc.reason}") from exc

    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Non-JSON response: {raw[:500]!r}") from exc


def _interpret_print_response(obj: JsonDict) -> Tuple[bool, str]:
    """Return (ok, result_id or error text)."""
    if "error" in obj and obj["error"] is not None:
        err = obj["error"]
        return False, json.dumps(err, indent=2, ensure_ascii=False)

    result = obj.get("result")
    if not isinstance(result, dict):
        return False, f"Unexpected JSON-RPC result: {result!r}"

    if result.get("success") is True:
        data = result.get("data") or {}
        rid = data.get("result_id")
        if rid:
            return True, str(rid)
        return True, json.dumps(result, indent=2, ensure_ascii=False)

    if result.get("success") is False and isinstance(result.get("error"), dict):
        return False, json.dumps(result["error"], indent=2, ensure_ascii=False)

    return False, json.dumps(result, indent=2, ensure_ascii=False)


def _interpret_get_print_result(obj: JsonDict) -> Tuple[bool, str, bytes]:
    """
    Return (ok, error_text_or_empty, document_bytes).

    On success error text is empty and bytes are the ``.docx`` payload.
    """
    if "error" in obj and obj["error"] is not None:
        err = obj["error"]
        return False, json.dumps(err, indent=2, ensure_ascii=False), b""

    result = obj.get("result")
    if not isinstance(result, dict):
        return False, f"Unexpected JSON-RPC result: {result!r}", b""

    if result.get("success") is True:
        data = result.get("data") or {}
        b64 = data.get("document_base64")
        if not isinstance(b64, str) or not b64.strip():
            return (
                False,
                "get_print_result: missing document_base64 in success payload",
                b"",
            )
        try:
            raw = base64.b64decode(b64, validate=True)
        except (binascii.Error, ValueError) as exc:
            return False, f"Invalid base64 in document_base64: {exc}", b""
        return True, "", raw

    if result.get("success") is False and isinstance(result.get("error"), dict):
        return False, json.dumps(result["error"], indent=2, ensure_ascii=False), b""

    return False, json.dumps(result, indent=2, ensure_ascii=False), b""


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Send JSON + template to DocPrinter (``print``), then fetch the "
            "rendered ``.docx`` with ``get_print_result`` and save it locally."
        )
    )
    parser.add_argument(
        "data_json",
        type=Path,
        help="Path to JSON file (becomes data.json inside the archive).",
    )
    parser.add_argument(
        "template_docx",
        type=Path,
        help="Path to Word template (becomes template.docx inside the archive).",
    )
    parser.add_argument(
        "--url",
        default="http://127.0.0.1:8080/api/jsonrpc",
        help="JSON-RPC endpoint (default: %(default)s)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=120.0,
        help="HTTP timeout in seconds for each RPC call (default: %(default)s)",
    )
    parser.add_argument(
        "--request-id",
        type=int,
        default=1,
        dest="request_id",
        help="JSON-RPC id for ``print`` (``get_print_result`` uses id+1).",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help=(
            "Where to save the rendered ``.docx``. Default: "
            "``<template_stem>_<first8 of result_id>.docx`` in the current directory."
        ),
    )
    parser.add_argument(
        "--no-download",
        action="store_true",
        help="Only run ``print`` and print ``result_id`` to stdout (no fetch).",
    )
    parser.add_argument(
        "--dump-request",
        action="store_true",
        help="Print JSON-RPC body to stderr (no HTTP call).",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Log request sizes and timing to stderr (diagnose HTTP 400/timeouts).",
    )
    args = parser.parse_args()

    data_path = args.data_json.expanduser().resolve()
    template_path = args.template_docx.expanduser().resolve()

    if not data_path.is_file():
        raise SystemExit(f"Not a file: {data_path}")
    if not template_path.is_file():
        raise SystemExit(f"Not a file: {template_path}")

    archive_bytes = _build_archive_bytes(data_path, template_path)
    archive_b64 = base64.b64encode(archive_bytes).decode("ascii")
    _vlog(
        args.verbose,
        "local: zip_bytes=%s archive_base64_chars=%s (JSON body will be larger)"
        % (len(archive_bytes), len(archive_b64)),
    )

    payload_print: JsonDict = {
        "jsonrpc": "2.0",
        "method": "print",
        "params": {"archive": archive_b64},
        "id": args.request_id,
    }

    if args.dump_request:
        preview = {
            **payload_print,
            "params": {"archive": f"<{len(archive_b64)} chars>"},
        }
        print(json.dumps(preview, indent=2), file=sys.stderr)
        print(
            f"(archive size: {len(archive_bytes)} bytes, base64: {len(archive_b64)})",
            file=sys.stderr,
        )
        return

    response = _post_jsonrpc(
        args.url,
        payload_print,
        args.timeout,
        verbose=args.verbose,
        label="print",
    )
    ok, text = _interpret_print_response(response)
    if not ok:
        print(text, file=sys.stderr)
        raise SystemExit(1)

    result_id = text
    print(result_id, file=sys.stdout)

    if args.no_download:
        return

    payload_get: JsonDict = {
        "jsonrpc": "2.0",
        "method": "get_print_result",
        "params": {"result_id": result_id},
        "id": args.request_id + 1,
    }
    resp2 = _post_jsonrpc(
        args.url,
        payload_get,
        args.timeout,
        verbose=args.verbose,
        label="get_print_result",
    )
    ok2, err2, doc_bytes = _interpret_get_print_result(resp2)
    if not ok2:
        print(err2, file=sys.stderr)
        raise SystemExit(1)

    if args.output is not None:
        out_path = args.output.expanduser().resolve()
    else:
        short = result_id.replace("-", "")[:8]
        out_path = (Path.cwd() / f"{template_path.stem}_{short}.docx").resolve()

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(doc_bytes)
    print(str(out_path), file=sys.stderr)
    print(
        f"Wrote {len(doc_bytes)} bytes to {out_path}",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
