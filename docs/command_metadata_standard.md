# Command metadata and JSON Schema standard (DocPrinter)

This repository follows the same **convention as `tools/code_analysis`**: MCP commands are classes on top of `mcp_proxy_adapter.commands.base.Command`, with **three coordinated layers** so humans, help tools, and JSON-RPC validation stay aligned.

## 1. Class-level fields (registry and compact help)

Set these **class attributes** on every command class:

| Field | Role |
|--------|------|
| `name` | RPC / JSON-RPC method name (snake_case). |
| `version` | Semver string for the command contract. |
| `descr` | Short, single-purpose summary (used by the default registry as `metadata.summary` when no `CommandInfo` manager is installed). |
| `category` | Logical group (e.g. `docprinter`, `file_management`). |
| `author`, `email` | Attribution (see `PROJECT_RULES` CR-012). |
| `use_queue` | `False` unless the command is intentionally queued. |

**Rule:** `descr` stays relatively short; long prose belongs in `get_schema()` and `metadata()`.

## 2. `get_schema()` — authoritative JSON Schema for `params`

Return a **draft-04-style** JSON object (what `mcp_proxy_adapter` validates against):

- **`type`**: `"object"`.
- **`title`**: usually the same as `name` (stable identifier for generators and docs).
- **`description`**: full narrative: behavior, defaults, edge cases, security/path notes, and pointers to other modules if discovery lives elsewhere (compare `UniversalFileReadCommand.get_schema()` in code_analysis).
- **`properties`**: one entry per parameter. Each property should have:
  - `type` (and `minimum` / `maximum` / `enum` where relevant),
  - `description` (what it means, units, path semantics),
  - optional **`examples`** (string or list) for LLM-friendly discovery.
- **`required`**: explicit list; omit keys that are truly optional.
- **`additionalProperties`**: **`false`** for strict commands unless proxy routing requires extra keys (then document why).
- **`examples`**: optional top-level array of **full param objects** (not only `examples` inside each property).

**Rule:** Anything that must be machine-validated belongs here. Downstream `/commands` and `help` read this schema from the registry.

## 3. `metadata()` — rich discovery for humans and doc generators

Provide a **`@classmethod def metadata(cls) -> dict[str, Any]`** (same pattern as `read_project_text_file`, `universal_file_read`, etc. in code_analysis).

Recommended keys (extend when useful):

| Key | Content |
|-----|---------|
| `name`, `version`, `category`, `author`, `email` | Mirror class attributes. |
| `description` | Same text as `descr` (compact). |
| `detailed_description` | Markdown-capable prose: flow, delegation, response shape. |
| `parameters` | Per-argument blurbs and `required: bool` for readers (JSON Schema in `get_schema()` remains authoritative for types). |
| `usage_examples` | List of `{ "description": str, "params": { ... } }`. |
| `error_codes` | List of stable string codes the command may surface (in `ErrorResult.details` and/or messages). |
| `error_codes_note` | Short legend mapping codes to situations. |

**Note:** The stock `mcp_proxy_adapter` registry (`_info is None`) only exposes `metadata.summary` from `descr` plus `schema` in `help` / `get_commands_list`. Rich `metadata()` is still **required in this repo** so it matches code_analysis and can be consumed by **doc generators** (e.g. `generate_command_docs.py` pattern) or future `CommandInfo` wiring.

## 4. Execution results

Prefer **`SuccessResult`** / **`ErrorResult`** from `mcp_proxy_adapter.commands.result` (code_analysis style):

- Return **`ErrorResult(message=..., code=..., details={...})`** for expected failures (missing file, bad type, …) instead of raising, when the failure is part of the contract.
- Return **`SuccessResult(data={...}, message=...)`** on success.
- Reserve exceptions for truly unexpected bugs (they still map to JSON-RPC errors via `Command.run`).

Document public **`details`** shapes under `error_codes` / `error_codes_note` in `metadata()`.

**Typing:** `mcp_proxy_adapter.commands.base.Command` still annotates `execute` as returning the legacy **`CommandResult`** type. Subclasses that return **`SuccessResult` / `ErrorResult`** may need a targeted `# type: ignore[override]` on `execute` until the framework unifies result types (same situation as in code_analysis commands).

## 5. Result shape documentation

- Prefer documenting success/error payloads in **`metadata()["detailed_description"]`** and in **`error_codes` / `error_codes_note`**.
- Optionally override **`get_result_schema()`** on the command class if OpenAPI or clients need a structured success schema beyond the generic `SuccessResult` schema.

## 6. Shared fragments

When several commands share the same long paragraph (registry pointers, legacy notes), extract **module-level constants** and concatenate them inside `get_schema()["description"]` (see `MCP_FILE_MANAGEMENT_REGISTRY_HELP` / `REGISTRY_SCHEMA_DISCOVERY_SHORT` in `code_analysis/commands/registration.py`).

---

**References in this repo:** `docprinter/commands/print_command.py`.  
**External reference:** `tools/code_analysis/code_analysis/commands/universal_file_read_command.py`, `read_project_text_file_command.py`, `registration.py`.
