Готовлю ТЗ. Делаю его максимально явным — Cursor Auto не любит догадываться.

---

# ТЗ для Cursor Auto: реализация команды `print` в DocPrinter

## Контекст

Проект: `docprinter` (HTTP JSON-RPC сервис на базе `mcp_proxy_adapter`).
Корень: `/home/vasilyvz/projects/tools/docprinter`.
Venv: `.venv` в корне проекта (активируй перед `pip` / `pytest` / `python`).
Стандарты проекта: `docs/PROJECT_RULES.md`, `docs/agents/project_overlay.md`. Соблюдай `CR-*`, `LAYOUT-*`, `NAME-*`. Артефакты — на английском (код, комменты, докстринги).

Сейчас в проекте есть **stub-реализация** команды `print` в `docprinter/commands/print_command.py`, принимающая параметры `template`, `data`, `outfile`. **Этот контракт меняется полностью** — см. ниже.

Старая логика рендера: `scripts-old/plugins/docbytpl.py` (функция `run`, 45 строк, `docxtpl.DocxTemplate(template).render(data); doc.save(outfile)`). **`scripts-old/` не править, не импортировать** — это легаси для справки.

---

## Что нужно сделать

Реализовать новый контракт MCP-команды `print`, добавить runtime-инфраструктуру (output/work каталоги + sweeper по TTL), обновить тесты.

### 1. Новый контракт команды `print`

**Параметры (JSON-RPC `params`):**

| Поле | Тип | Required | Описание |
|------|-----|----------|----------|
| `archive` | `string` (base64) | да | Base64-кодированный ZIP-архив, содержащий **ровно** два файла в корне: `data.json` и `template.docx`. |

`additionalProperties: false`. Других полей быть не должно.

**Поведение `execute`:**

1. Декодировать `archive` из base64. При ошибке → `ErrorResult` с `error_code: "INVALID_BASE64"`, JSON-RPC code `-32602`.
2. Распаковать архив в новый каталог `runtime/work/<request_uuid4>/` (UUID4 сгенерировать через `uuid.uuid4()`).
   - Если архив не ZIP или повреждён → `ErrorResult` с `error_code: "INVALID_ARCHIVE"`, code `-32602`.
   - Защита от zip-slip: каждый member архива должен быть простым именем файла без `/`, `..`, `\`. Иначе → `ErrorResult` `error_code: "UNSAFE_ARCHIVE_MEMBER"`, code `-32602`.
   - В архиве должны быть **именно** `data.json` и `template.docx` (имена строго). Иначе → `ErrorResult` `error_code: "ARCHIVE_MISSING_REQUIRED_FILES"`, code `-32602`, в `details` указать какие файлы отсутствуют.
3. Прочитать `data.json` как JSON-объект. Если корень не объект → `ErrorResult` `error_code: "INVALID_DATA_TYPE"`, code `-32602`.
4. Сгенерировать `result_uuid = uuid.uuid4()`. Целевой путь: `<output_dir>/<result_uuid>.docx`.
5. Выполнить рендер по логике легаси `scripts-old/plugins/docbytpl.py`:
   ```python
   from docxtpl import DocxTemplate
   doc = DocxTemplate(<work_dir>/<request_uuid>/template.docx)
   doc.render(data)
   doc.save(<output_dir>/<result_uuid>.docx)
   ```
   Сохранение выполнять под `warnings.catch_warnings()` с фильтром `UserWarning` для модуля `zipfile` (как в легаси).
6. **Обработка исключений рендера** (мапить на `ErrorResult`, JSON-RPC code `-32603` если не указано иное):

   | Исключение | `error_code` |
   |------------|--------------|
   | `jinja2.exceptions.TemplateNotFound` | `TEMPLATE_NOT_FOUND` |
   | `jinja2.exceptions.TemplateAssertionError` | `TEMPLATE_ASSERTION_ERROR` |
   | `jinja2.exceptions.TemplateSyntaxError` | `TEMPLATE_SYNTAX_ERROR` |
   | `jinja2.exceptions.UndefinedError` | `TEMPLATE_UNDEFINED` |
   | `jinja2.exceptions.TemplateRuntimeError` | `TEMPLATE_RUNTIME_ERROR` |
   | `jinja2.exceptions.TemplateError` | `TEMPLATE_ERROR` |
   | `ValueError` (от рендера) | `RENDER_VALUE_ERROR` |
   | прочие неожиданные | `RENDER_UNEXPECTED_ERROR` |

   В `details` класть `{"error_code": "...", "errstr": str(exc)}`.

7. **Гарантированно** удалить `runtime/work/<request_uuid>/` в `finally` независимо от исхода (использовать `shutil.rmtree(..., ignore_errors=True)`).
8. На успехе вернуть `SuccessResult` с `data: {"result_id": "<result_uuid>"}`. **Никаких путей в ответе.** Имя файла на диске — это `<result_id>.docx` в `output_dir`, но клиент об этом знать не обязан.

**Метаданные команды (`metadata()`):**
- сохранить структуру существующего метода (`name`, `version`, `description`, `detailed_description`, `category`, `author`, `email`, `parameters`, `usage_examples`, `error_codes`, `error_codes_note`);
- `error_codes` — список из таблицы выше + `INVALID_BASE64`, `INVALID_ARCHIVE`, `UNSAFE_ARCHIVE_MEMBER`, `ARCHIVE_MISSING_REQUIRED_FILES`, `INVALID_DATA_TYPE`;
- `version` поднять до `0.2.0`.

**`get_result_schema()`:**
```json
{
  "type": "object",
  "title": "print_success",
  "properties": {
    "success": {"type": "boolean", "const": true},
    "data": {
      "type": "object",
      "properties": {
        "result_id": {
          "type": "string",
          "format": "uuid",
          "description": "UUID4 of the rendered file in runtime/output/. Filename is <result_id>.docx."
        }
      },
      "required": ["result_id"]
    }
  },
  "required": ["success", "data"]
}
```

### 2. Runtime-каталоги

Каталоги уже созданы (`runtime/output/.gitkeep`, `runtime/work/.gitkeep`).

**Команда `print` должна:**
- Получать пути из конфига (см. п. 3).
- На старте выполнения — `pathlib.Path(output_dir).mkdir(parents=True, exist_ok=True)` и аналогично для `work_dir`.

### 3. Конфигурация

В JSON-конфиге (`config/docprinter.server.json`) добавить **новую корневую секцию**:

```json
"docprinter": {
  "output_dir": "runtime/output",
  "work_dir": "runtime/work",
  "output_ttl_seconds": 3600,
  "sweep_interval_seconds": 300
}
```

Эта секция не валидируется `SimpleConfigValidator` (он смотрит только known-секции `server`/`client`/`registration`/`auth`/`queue_manager`/...). После загрузки конфига в `docprinter/main.py` весь JSON попадает в `cfg.config_data` (`cfg = get_config()`), и наша секция доступна оттуда.

**Чтение значений:**
```python
from mcp_proxy_adapter.config import get_config
cfg = get_config()
output_dir = cfg.get("docprinter.output_dir", "runtime/output")
work_dir = cfg.get("docprinter.work_dir", "runtime/work")
ttl = int(cfg.get("docprinter.output_ttl_seconds", 3600))
interval = int(cfg.get("docprinter.sweep_interval_seconds", 300))
```

`Config.get()` поддерживает dotted-path. Если значение в конфиге отсутствует — вернётся default из второго аргумента.

**Пути относительные** (как в примере) — резолвить относительно `cwd` процесса сервера. Дефолты должны работать без правки конфига.

### 4. Sweeper по TTL

Создать модуль `docprinter/runtime/sweeper.py` (создай каталог `docprinter/runtime/` с `__init__.py`).

**Класс `RuntimeSweeper`:**

```python
class RuntimeSweeper:
    """Background thread that evicts stale files in runtime/output/ and stale dirs in runtime/work/."""

    def __init__(
        self,
        output_dir: Path,
        work_dir: Path,
        output_ttl_seconds: int,
        sweep_interval_seconds: int,
    ) -> None: ...

    def start(self) -> None:
        """Start the daemon thread. Idempotent."""

    def stop(self, timeout: float = 5.0) -> None:
        """Signal stop and join."""

    def sweep_once(self) -> dict:
        """Run one sweep iteration. Returns counters: {output_removed, work_removed}."""
```

Реализация:
- `threading.Thread(daemon=True)` + `threading.Event` для сигнала остановки.
- В цикле: `sweep_once()`, затем `event.wait(sweep_interval_seconds)`. Если `event.is_set()` — выйти.
- `sweep_once`:
  - В `output_dir`: для каждого файла с расширением `.docx` если `time.time() - file.stat().st_mtime > output_ttl_seconds` → удалить.
  - В `work_dir`: для каждого подкаталога если `time.time() - dir.stat().st_mtime > output_ttl_seconds` → `shutil.rmtree(..., ignore_errors=True)`. (Тот же TTL — одна шкала, одно правило.)
- Все ошибки I/O ловить и логировать через `logging.getLogger(__name__)`, не падать.

**Запуск/остановка** — в `docprinter/main.py`:
- После `register_docprinter_commands()` и до `engine.run_server(...)` создать и запустить `RuntimeSweeper`.
- Регистрировать `atexit.register(sweeper.stop)` либо использовать `try/finally` вокруг `run_server`. Выбери `try/finally` — детерминированнее.

### 5. Зависимости

В `requirements.txt` добавить:
```
docxtpl>=0.16.0
```

`jinja2` ставится транзитивно с `docxtpl`, отдельно не нужен.

### 6. Тесты — `tests/test_print_command.py`

**Полностью переписать** под новый API. Старые тесты на `template`/`data`/`outfile` удалить.

Покрыть как минимум:

1. `test_print_success_returns_result_id` — собрать tmp ZIP с валидным `data.json` и реальным `.docx`-шаблоном (можно сгенерировать минимальный шаблон через `docxtpl.DocxTemplate` из `python-docx` Document или положить fixture-файл в `tests/fixtures/`); base64; вызвать `await PrintCommand().execute(archive=...)`; проверить:
   - `result["success"] is True`
   - `UUID(result["data"]["result_id"])` парсится
   - файл `<output_dir>/<result_id>.docx` существует
   - `runtime/work/<request_uuid>/` удалён.

2. `test_print_invalid_base64` — `archive="!!!not-base64!!!"` → `error_code: "INVALID_BASE64"`.

3. `test_print_invalid_archive` — base64 от `b"not a zip"` → `error_code: "INVALID_ARCHIVE"`.

4. `test_print_archive_missing_files` — ZIP с одним `data.json` без `template.docx` → `error_code: "ARCHIVE_MISSING_REQUIRED_FILES"`, в `details` упомянут `template.docx`.

5. `test_print_unsafe_archive_member` — ZIP с member `../evil.txt` → `error_code: "UNSAFE_ARCHIVE_MEMBER"`. Файл вне `work_dir` создан **не должен**.

6. `test_print_invalid_data_json` — ZIP, где `data.json` содержит `"just a string"` (не объект) → `error_code: "INVALID_DATA_TYPE"`.

7. `test_print_template_undefined_var` — шаблон ссылается на `{{ missing_var }}`, в `data.json` его нет, `docxtpl` падает с `UndefinedError` → `error_code: "TEMPLATE_UNDEFINED"`.

8. `test_print_schema_required_fields` — `PrintCommand.get_schema()["required"] == ["archive"]`, `additionalProperties is False`.

9. `test_print_result_schema` — `get_result_schema()["title"] == "print_success"`, `required` в `data` содержит `result_id`.

10. `test_work_dir_cleaned_on_error` — на любом из ошибочных путей убедись, что `runtime/work/<request_uuid>/` не существует после вызова.

**Для тестов конфигурируй `output_dir` и `work_dir` через monkeypatching `get_config().config_data["docprinter"]`** или передавай через переменные окружения (если решишь поддержать ENV-override — это опционально, в основном ТЗ не нужно).

**Sweeper тестировать отдельно** — `tests/test_runtime_sweeper.py`:
- `test_sweep_once_removes_old_output` — создать файл в `output_dir`, выставить старый mtime через `os.utime`, вызвать `sweep_once()`, проверить что удалён.
- `test_sweep_once_keeps_fresh_output` — свежий файл не удаляется.
- `test_sweep_once_removes_old_work_subdir` — аналогично для `work_dir`.
- `test_sweeper_thread_lifecycle` — `start()`, sleep маленький, `stop()`, проверить что поток завершился.

### 7. Порядок работ

1. Обнови `requirements.txt`, активируй `.venv`, поставь `pip install -r requirements.txt`.
2. Добавь секцию `docprinter` в `config/docprinter.server.json`.
3. Реализуй `docprinter/runtime/__init__.py` и `docprinter/runtime/sweeper.py`.
4. Перепиши `docprinter/commands/print_command.py` под новый контракт. Обнови `docprinter/commands/registration.py` если фрагменты-описания (`PRINT_LEGACY_DOCBYTPL_NOTE`, `PRINT_SCHEMA_DISCOVERY_SHORT`) больше не подходят — отредактируй их под новый API, не выкидывая идею «общих фрагментов».
5. Подключи `RuntimeSweeper` в `docprinter/main.py` через `try/finally` вокруг `engine.run_server(app, server_config)`.
6. Перепиши `tests/test_print_command.py`, добавь `tests/test_runtime_sweeper.py`, при необходимости `tests/fixtures/` с минимальным `template.docx`.
7. Прогони `pytest`, `black`, `flake8`, `mypy` на изменённых путях. Все findings — пофикси.

### 8. Что **нельзя**

- Менять `scripts-old/`.
- Менять `docs/PROJECT_RULES.md`, `docs/agents/project_overlay.md` (они уже обновлены — `LAYOUT-08`, `LAYOUT-09`, `LAYOUT-10`).
- Использовать `pip install --break-system-packages`.
- Редактировать что-либо вне репозитория `docprinter/`.
- Записывать в `runtime/output/` через `template`/`outfile` — таких параметров больше нет.
- Возвращать клиенту абсолютные пути файловой системы.
- Создавать `runtime/output/` и `runtime/work/` в `docker/Dockerfile` без явного указания (они появятся при первом запуске через `mkdir(parents=True, exist_ok=True)`).

### 9. Acceptance criteria

- `pytest` зелёный, покрытие нового кода ≥ 80%.
- `black .` без изменений, `flake8 docprinter tests` чисто, `mypy docprinter` чисто.
- Ручной smoke: запустить сервер `python -m docprinter --config config/docprinter.server.json`, через `curl` отправить JSON-RPC запрос с реальным base64-архивом → получить `result_id` → файл `<result_id>.docx` появился в `runtime/output/`.
- Через `output_ttl_seconds + sweep_interval_seconds` файл из `runtime/output/` исчезает.
- Все файлы со стандартным заголовком (`Author: Vasiliy Zdanovskiy`, `email: vasilyvz@gmail.com`).

---

Если что-то непонятно — спрашивайте. Если ОК — копируйте в Cursor.