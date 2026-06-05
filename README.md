# DocPrinter

HTTP service (``mcp_proxy_adapter`` + Hypercorn) with JSON-RPC commands **`print`** (Base64 ZIP of ``data.json`` + ``template.docx`` → stored ``.docx`` keyed by ``result_id``) and **`get_print_result`** (return that file as Base64). Formats and call flow (Russian): **[`docs/PRINT_FORMAT_AND_API.md`](docs/PRINT_FORMAT_AND_API.md)**.

## Layout

- **`docprinter/`** — application package (``python -m docprinter``).
- **`config/`** — sample server JSON for the adapter.
- **`docker/`** — image build and helper scripts (run from repo root).
- **`scripts/`** — helpers, including **`build-deb.sh`** (checks build deps; as root installs them via ``apt-get`` and runs ``dpkg-buildpackage``).
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

### Docker Hub

Publish the image (requires ``docker login``):

```bash
chmod +x docker/push.sh
./docker/push.sh
```

Default registry image: **``vasilyvz/docprinter:latest``** (override with ``DOCPRINTER_HUB_IMAGE``).

### Debian package (Ubuntu 22.04 / 26.04)

Build the ``.deb`` — **always** builds and pushes ``vasilyvz/docprinter:<version>`` to Docker Hub, where ``<version>`` equals the Debian package version from ``debian/changelog`` (e.g. package ``0.2.0-12`` → image ``vasilyvz/docprinter:0.2.0-12``). Needs ``docker login``.

```bash
./scripts/build-deb.sh          # or: sudo ./scripts/build-deb.sh
```

Install on a clean host (pulls ``vasilyvz/docprinter:<same-version>`` on configure):

```bash
sudo apt install ./docprinter_0.2.0-21_all.deb
# or: sudo dpkg -i ../docprinter_0.2.0-12_all.deb && sudo apt-get install -f
```

The package depends on **``docker.io``** or **``docker-ce``**, **``adduser``**, **``systemd``**. On configure it checks the Docker daemon, creates user **``docprinter``** in group **``docker``**, host directories, and runs **``docker pull``** for the image in ``/etc/default/docprinter``.

| Host path | Role |
|-----------|------|
| ``/etc/docprinter/conf.json`` | Service config (mounted read-only into the container) |
| ``/var/log/docprinter/`` | Application and container log stream |
| ``/var/docprinter/`` | Runtime cache (``output/``, ``work/``, ``uploads/``) |

Service: ``systemctl status docprinter`` — HTTP on **127.0.0.1:9001** by default (``DOCPRINTER_BIND=127.0.0.1``, ``DOCPRINTER_HOST_PORT=9001`` in ``/etc/default/docprinter``). Set ``DOCPRINTER_BIND=0.0.0.0`` or a specific host IP to listen on all interfaces or one address.

If ``docker -p`` fails on the host, ``run-container.sh`` retries with ``--network host`` and saves ``DOCPRINTER_NETWORK=host`` in ``/etc/default/docprinter``.

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
