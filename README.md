# DocPrinter

HTTP service (``mcp_proxy_adapter`` + Hypercorn) with JSON-RPC commands **`print`** (Base64 ZIP of ``data.json`` + ``template.docx`` → stored ``.docx`` keyed by ``result_id``) and **`get_print_result`** (return that file as Base64). Formats and call flow (Russian): **[`docs/PRINT_FORMAT_AND_API.md`](docs/PRINT_FORMAT_AND_API.md)**.

## Layout

- **`docprinter/`** — application package (``python -m docprinter``).
- **`config/`** — sample server JSON for the adapter.
- **`docker/`** — image build and helper scripts (run from repo root).
- **`logs/`** — runtime log directory (contents gitignored).

Rules bundle checklist (portable Cursor/agents template): see ``rules_template_agents_protocols_updated.zip`` → ``rules_template/README.md`` (install, §0/§7, overlay, optional ``projectid``).

## Local run

```bash
source .venv/bin/activate
./docker/run_local.sh
```

Optional overrides: `./docker/run_local.sh --port 9090 --host 127.0.0.1`

## Docker

Build the image, then start the container (**TCP 9001** on host and inside), current user, mounts for **config**, **logs**, **runtime**:

```bash
./docker/build.sh && ./docker/run.sh
```

Overrides for ``run.sh``: ``DOCPRINTER_IMAGE``, ``DOCPRINTER_NAME``, ``DOCPRINTER_PORT`` (default ``9001``). Ensure ``./logs`` and ``./runtime/*`` are writable by your UID.

## JSON-RPC

Endpoint: **`POST /api/jsonrpc`**. Parameters follow each command’s JSON Schema (see ``PrintCommand.get_schema()`` and ``GetPrintResultCommand.get_schema()``).

In short: **`print`** takes **`archive`** (Base64 ZIP with exactly ``data.json`` and ``template.docx`` at the archive root) and returns **`result_id`**; **`get_print_result`** with that id returns **`document_base64`**.

Full format description for ``data.json``, curl examples, and the **`scripts/print_client.py`** helper: **[`docs/PRINT_FORMAT_AND_API.md`](docs/PRINT_FORMAT_AND_API.md)** (document in Russian).

Simplified body form is also accepted: ``{"command":"print","params":{...},"id":1}``.

List methods: **`GET /commands`**. Health: **`GET /health`**.

## Old console flow

See **`scripts-old/`**: ``starter.py`` and ``plugins/docbytpl.py``. Jinja context rules match the new service (see the linked document).

## Command schemas and metadata

Conventions (aligned with **`tools/code_analysis`**): [`docs/command_metadata_standard.md`](docs/command_metadata_standard.md).
