#!/usr/bin/env python3
"""
Smoke-test a remote DocPrinter HTTP service.

Checks ``GET /health``, ``GET /commands``, and a minimal ``print`` +
``get_print_result`` round trip.

Usage::

    python scripts/test-remote-server.py
    python scripts/test-remote-server.py --host 192.168.253.1 --port 9001

Requires Python 3.10+ (stdlib only).

Author: Vasiliy Zdanovskiy
email: vasilyvz@gmail.com
"""

from __future__ import annotations

import argparse
import base64
import json
import sys
import urllib.error
import urllib.request
import xml.sax.saxutils
import zipfile
from io import BytesIO
from typing import Any, Dict, List, Tuple

JsonDict = Dict[str, Any]


def _minimal_docx_bytes(body: str) -> bytes:
    """Build a tiny valid .docx containing plain text (Jinja placeholders allowed)."""
    escaped = xml.sax.saxutils.escape(body)
    document_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p>
      <w:r><w:t xml:space="preserve">{escaped}</w:t></w:r>
    </w:p>
  </w:body>
</w:document>"""
    content_types = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml"
    ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>"""
    rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1"
    Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"
    Target="word/document.xml"/>
</Relationships>"""
    doc_rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"/>"""

    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", rels)
        zf.writestr("word/document.xml", document_xml)
        zf.writestr("word/_rels/document.xml.rels", doc_rels)
    return buf.getvalue()


def _build_archive_b64(context: JsonDict, template_body: str) -> str:
    zbuf = BytesIO()
    with zipfile.ZipFile(zbuf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("data.json", json.dumps(context, ensure_ascii=False).encode("utf-8"))
        zf.writestr("template.docx", _minimal_docx_bytes(template_body))
    return base64.b64encode(zbuf.getvalue()).decode("ascii")


def _http_get(url: str, timeout: float) -> Tuple[int, str]:
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"GET {url} failed: HTTP {exc.code}\n{body}") from exc
    except urllib.error.URLError as exc:
        raise SystemExit(f"GET {url} failed: {exc.reason}") from exc


def _post_jsonrpc(url: str, payload: JsonDict, timeout: float) -> JsonDict:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        text = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"POST {url} failed: HTTP {exc.code}\n{text}") from exc
    except urllib.error.URLError as exc:
        raise SystemExit(f"POST {url} failed: {exc.reason}") from exc
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Non-JSON response from {url}: {raw[:500]!r}") from exc


def _ok(label: str) -> None:
    print(f"OK  {label}")


def _fail(label: str, detail: str) -> None:
    print(f"FAIL {label}: {detail}", file=sys.stderr)
    raise SystemExit(1)


def check_health(base: str, timeout: float) -> None:
    status, body = _http_get(f"{base}/health", timeout)
    if status != 200:
        _fail("health", f"expected HTTP 200, got {status}")
    if not body.strip():
        _fail("health", "empty response body")
    _ok(f"GET /health ({status})")


def check_commands(base: str, timeout: float) -> None:
    status, body = _http_get(f"{base}/commands", timeout)
    if status != 200:
        _fail("commands", f"expected HTTP 200, got {status}")
    try:
        data = json.loads(body)
    except json.JSONDecodeError as exc:
        _fail("commands", f"invalid JSON: {exc}")

    names: List[str] = []
    if isinstance(data, dict):
        for key in ("commands", "data", "result"):
            block = data.get(key)
            if isinstance(block, list):
                for item in block:
                    if isinstance(item, dict) and "name" in item:
                        names.append(str(item["name"]))
                    elif isinstance(item, str):
                        names.append(item)
            elif isinstance(block, dict):
                names.extend(str(k) for k in block.keys())
        if not names and "print" in data:
            names = list(data.keys())
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, dict) and "name" in item:
                names.append(str(item["name"]))
            elif isinstance(item, str):
                names.append(item)

    required = {"print", "get_print_result"}
    missing = required - set(names)
    if missing:
        _fail("commands", f"missing {sorted(missing)}; found: {sorted(set(names))}")
    _ok(f"GET /commands (print, get_print_result registered)")


def check_print_roundtrip(rpc_url: str, timeout: float) -> None:
    archive_b64 = _build_archive_b64({"name": "remote-test"}, "Hello {{ name }}")

    print_resp = _post_jsonrpc(
        rpc_url,
        {
            "jsonrpc": "2.0",
            "method": "print",
            "params": {"archive": archive_b64},
            "id": 1,
        },
        timeout,
    )
    if print_resp.get("error"):
        _fail("print", json.dumps(print_resp["error"], ensure_ascii=False))

    result = print_resp.get("result")
    if not isinstance(result, dict) or result.get("success") is not True:
        _fail("print", json.dumps(result, ensure_ascii=False))

    data = result.get("data") or {}
    result_id = data.get("result_id")
    if not isinstance(result_id, str) or not result_id.strip():
        _fail("print", "missing result_id in success payload")
    _ok(f"print -> result_id={result_id}")

    get_resp = _post_jsonrpc(
        rpc_url,
        {
            "jsonrpc": "2.0",
            "method": "get_print_result",
            "params": {"result_id": result_id},
            "id": 2,
        },
        timeout,
    )
    if get_resp.get("error"):
        _fail("get_print_result", json.dumps(get_resp["error"], ensure_ascii=False))

    get_result = get_resp.get("result")
    if not isinstance(get_result, dict) or get_result.get("success") is not True:
        _fail("get_print_result", json.dumps(get_result, ensure_ascii=False))

    doc_b64 = (get_result.get("data") or {}).get("document_base64")
    if not isinstance(doc_b64, str) or not doc_b64.strip():
        _fail("get_print_result", "missing document_base64")

    doc_bytes = base64.b64decode(doc_b64)
    if not doc_bytes.startswith(b"PK"):
        _fail("get_print_result", "decoded payload is not a ZIP/.docx")
    if len(doc_bytes) < 100:
        _fail("get_print_result", f"document too small ({len(doc_bytes)} bytes)")

    _ok(f"get_print_result -> {len(doc_bytes)} byte .docx")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Smoke-test a remote DocPrinter HTTP service."
    )
    parser.add_argument(
        "--host",
        default="192.168.253.1",
        help="Server host (default: %(default)s)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=9001,
        help="Server port (default: %(default)s)",
    )
    parser.add_argument(
        "--scheme",
        default="http",
        choices=("http", "https"),
        help="URL scheme (default: %(default)s)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=120.0,
        help="HTTP timeout in seconds (default: %(default)s)",
    )
    parser.add_argument(
        "--skip-print",
        action="store_true",
        help="Only check /health and /commands",
    )
    args = parser.parse_args()

    base = f"{args.scheme}://{args.host}:{args.port}"
    rpc_url = f"{base}/api/jsonrpc"

    print(f"Testing DocPrinter at {base}")
    check_health(base, args.timeout)
    check_commands(base, args.timeout)
    if not args.skip_print:
        check_print_roundtrip(rpc_url, args.timeout)
    print("All checks passed.")


if __name__ == "__main__":
    main()
