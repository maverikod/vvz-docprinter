<!--
Author: Vasiliy Zdanovskiy
email: vasilyvz@gmail.com
-->

# Project overlay — `docprinter` (this repository)

Repository-specific paths, behavior, and restrictions. Universal layout: [`PROJECT_RULES.md`](../PROJECT_RULES.md) section 3 (`LAYOUT-*`).

## Functional context

- **Role:** Python **HTTP JSON-RPC** service (``mcp_proxy_adapter``) for printing Word (``.docx``) documents from Jinja-style templates and JSON context data. Rendering pipeline is **not** implemented yet; the ``print`` command validates inputs and returns a stub response.
- **Installable package:** [`docprinter/`](../../docprinter/) — server entrypoint and commands.
- **Tests:** under [`tests/`](../../tests/) (pytest). Operational wrappers live under [`docker/`](../../docker/) and [`scripts/`](../../scripts/) per **LAYOUT-07** (non-pytest harnesses).

## Directories and files beyond the universal skeleton

| Path | Note |
|------|------|
| `projectid` | Repo root JSON (**CR-003**): keys `id` (UUID4) and `description`. |
| `config/` | Sample **mcp_proxy_adapter** SimpleConfig JSON (HTTP). Universal template often uses `configs/`; this repo standardizes on **`config/`** at repo root. |
| `docker/` | `Dockerfile`, `build.sh`, `run.sh` (container), `run_local.sh` (venv, not Docker). **Invoke from repo root**, e.g. `./docker/build.sh && ./docker/run.sh`. |
| `logs/` | Runtime logs; tracked placeholder via `logs/.gitkeep`; contents ignored by git. |
| `scripts-old/` | Legacy console starter + plugins (reference only; not part of the runtime package). |
| [`docs/command_metadata_standard.md`](../command_metadata_standard.md) | How MCP commands define **class fields**, **`get_schema()`**, **`metadata()`**, and **SuccessResult / ErrorResult** (aligned with `tools/code_analysis`). |
| `runtime/output/` | Rendered `.docx` files named `<uuid4>.docx`. Background sweeper removes files older than configured TTL. Tracked placeholder via `runtime/output/.gitkeep`; contents ignored by git. |
| `runtime/work/` | Per-request scratch dirs (`runtime/work/<uuid4>/`) for unpacking input archives. Each command must remove its subdirectory on completion. Tracked placeholder via `runtime/work/.gitkeep`; contents ignored by git. |

## Project-specific restrictions

- **Secrets:** Never commit real credentials, API keys, or production TLS private keys.
- **Scope:** Changes stay within **this** repository unless the user explicitly allows otherwise.
- **Legacy code:** Do not extend `scripts-old/` for new features; port behavior into `docprinter/` when ready.

## Filled profile pointer

Concrete profile values: [`PROJECT_RULES.md`](../PROJECT_RULES.md) **section 7**.