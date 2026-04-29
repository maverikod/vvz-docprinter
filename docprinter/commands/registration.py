"""
Shared schema / discovery fragments for DocPrinter MCP commands.

Same idea as ``code_analysis.commands.registration``: long, reusable
paragraphs are kept in one place and concatenated into JSON Schema
``description`` fields so models and humans see consistent routing context.

Author: Vasiliy Zdanovskiy
email: vasilyvz@gmail.com
"""

# Legacy console plugin (scripts-old/plugins/docbytpl.py) — render semantics only.
PRINT_LEGACY_DOCBYTPL_NOTE = (
    "Render semantics match the legacy ``DocxTemplate(template).render(data); save`` "
    "flow from ``scripts-old/plugins/docbytpl.py``; the MCP contract uses a single "
    "base64 ZIP payload instead of server-side paths."
)

# Short line for embedding at the end of schema descriptions.
PRINT_SCHEMA_DISCOVERY_SHORT = (
    "Discovery: GET /commands lists schemas; help JSON-RPC with cmdname "
    "returns schema + compact metadata."
)

# Companion to ``print`` / ``get_print_result`` (fetch by ``result_id``).
PRINT_RESULT_COMPANION_NOTE = (
    "Pairs with command ``print``: use the returned ``result_id`` here. "
    "Files live under ``docprinter.output_dir`` as ``<result_id>.docx`` until "
    "removed by the TTL sweeper."
)
