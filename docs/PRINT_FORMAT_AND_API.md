# Форматы данных и вызов конвертации (JSON → DOCX)

Сервис **DocPrinter** по HTTP отдаёт JSON-RPC. Конвертация «данные + шаблон Word → заполненный `.docx`» выполняется парой команд **`print`** и **`get_print_result`**.

---

## Куда обращаться

| Что | Значение по умолчанию |
|-----|------------------------|
| Базовый URL | `http://127.0.0.1:8080` (хост/порт из секции `server` в JSON-конфиге) |
| JSON-RPC | **`POST /api/jsonrpc`** (`Content-Type: application/json`) |
| Упрощённый вызов | То же тело с полями `command` и `params` вместо `jsonrpc`/`method` (см. адаптер) |
| Список команд | **`GET /commands`** |
| Проверка живости | **`GET /health`** |

### Пример развёрнутого сервиса (HTTPS, порт 443)

Хост **`cvtdoc.techsup.od.ua`**, TLS на стандартном порту **443** (в браузере и в `curl` порт обычно не указывают).

| Ресурс | URL |
|--------|-----|
| JSON-RPC | `https://cvtdoc.techsup.od.ua/api/jsonrpc` |
| Список команд | `https://cvtdoc.techsup.od.ua/commands` |
| Health | `https://cvtdoc.techsup.od.ua/health` |

Вызов **`print_client`** на этот хост:

```bash
python scripts/print_client.py путь/к/data.json путь/к/template.docx -o результат.docx \
  --url https://cvtdoc.techsup.od.ua/api/jsonrpc
```

Если стоит свой TLS-сертификат (корпоративный CA), убедитесь, что клиентское окружение ему доверяет; иначе `urllib` завершится ошибкой проверки цепочки.

Параметры каждой команды строго по JSON Schema: для разработки удобно смотреть `PrintCommand.get_schema()` и `GetPrintResultCommand.get_schema()` в коде, либо ответ **`GET /commands`** после регистрации плагинов.

---

## Общая схема конвертации

1. Клиент собирает **ZIP-архив** из ровно двух файлов в **корне** архива (без подпапок и без лишних имён):
   - `data.json` — UTF-8 JSON с контекстом (см. ниже);
   - `template.docx` — шаблон Word с плейсхолдерами **Jinja2** в духе **docxtpl** (как в старом `scripts-old/plugins/docbytpl.py`).
2. Клиент кодирует ZIP в **Base64** (стандартный алфавит, без переносов строк внутри строки) и вызывает **`print`** с полем **`archive`**.
3. В ответе при успехе приходит **`result_id`** (UUID строкой) — идентификатор файла на сервере, **не путь в ФС клиента**.
4. Клиент вызывает **`get_print_result`** с тем же **`result_id`** и получает **`document_base64`** — тело готового `.docx`.
5. Клиент декодирует Base64 и сохраняет файл у себя.

Файлы результата лежат на сервере в каталоге **`docprinter.output_dir`** (по умолчанию `runtime/output/`), имя файла: `<result_id>.docx`. Старые файлы могут удаляться фоновой уборкой по **`docprinter.output_ttl_seconds`** — запрашивайте результат сразу после `print`.

---

## Формат архива (`print.params.archive`)

- Один параметр: строка **`archive`** — Base64 от **ZIP**.
- Внутри ZIP **только** два члена с именами **точно** `data.json` и `template.docx` (регистр и имя важны).
- Пути вида `folder/file.json` **запрещены** — только корень архива.

---

## Формат `data.json`

Корень JSON — **объект** (`{}`). Дальше сервер определяет, что передать в **`DocxTemplate.render()`**:

### 1. Полный job (как файл для старого `starter.py`)

Типичный сохранённый сценарий: есть **`cmd`**, на верхнем уровне могут быть **`outfile`**, **`lng`**, **`logfile`**, а полезная тройка лежит в **`data`**:

```json
{
  "cmd": "docbytpl",
  "outfile": "/tmp/log.json",
  "lng": "uk_ua",
  "data": {
    "template": "/path/to/template.docx",
    "outfile": "/path/to/out.docx",
    "data": {
      "Поле1": "значение",
      "Список": []
    }
  }
}
```

Для **`print`** пути **`template`/`outfile`** в JSON **не используются** для чтения/записи на диске сервера: шаблон всегда берётся из **`template.docx`** внутри ZIP, результат отдаётся только через **`get_print_result`**. Важно лишь наличие вложенного объекта **`data.data`** — его сервер передаёт в Jinja, как старый **`doc.render(data["data"])`**.

### 2. Только тройка docbytpl (как то, что старый `starter` передаёт в плагин)

Корень файла — объект с **`template`**, опционально **`outfile`**, и **`data`** (внутренний словарь переменных):

```json
{
  "template": "/ignored/on/server.docx",
  "outfile": "/ignored/on/server.docx",
  "data": { "Поле1": "значение" }
}
```

В Jinja уходит объект **`data`**.

### 3. Обёртка ответа `read_json` / `plugin_result`

Если в ZIP попал объект вида:

```json
{
  "exitcode": 0,
  "data": { "cmd": "docbytpl", "data": { ... } },
  "errstr": ""
}
```

сервер сначала «снимает» оболочку и дальше обрабатывает внутренний job как в п. 1.

### 4. Плоский контекст Jinja

Если структура **не** похожа на тройку docbytpl (нет строкового **`template`** с путём к `.docx` и вложенного **`data`** в ожидаемом виде), **весь корень** `data.json` считается словарём переменных для шаблона.

---

## JSON-RPC: `print`

Пример тела запроса (подставьте свой Base64 вместо многоточия):

```json
{
  "jsonrpc": "2.0",
  "method": "print",
  "params": {
    "archive": "<base64 ZIP с data.json и template.docx>"
  },
  "id": 1
}
```

Успешный результат (упрощённо):

```json
{
  "jsonrpc": "2.0",
  "result": {
    "success": true,
    "data": { "result_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" }
  },
  "id": 1
}
```

При ошибке: `success: false`, код и детали в объекте ошибки (см. схему команды и `error_code` в `PrintCommand.metadata()`).

---

## JSON-RPC: `get_print_result`

```json
{
  "jsonrpc": "2.0",
  "method": "get_print_result",
  "params": {
    "result_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
  },
  "id": 2
}
```

Успех: в `result.data` есть **`document_base64`**, **`content_type`**, повтор **`result_id`**. Если файл уже удалён по TTL или id неверный — ошибка с кодом вроде **`RESULT_NOT_FOUND`**.

---

## Локальный клиент без ручного curl

Из корня репозитория (нужен Python 3.10+, только стандартная библиотека):

```bash
python scripts/print_client.py путь/к/data.json путь/к/template.docx -o результат.docx
```

Скрипт сам собирает ZIP, вызывает `print`, затем `get_print_result` и пишет файл. Параметры:

- **`--url`** — полный URL JSON-RPC (локально по умолчанию `http://127.0.0.1:8080/api/jsonrpc`; для развёрнутого сервиса, например: `https://cvtdoc.techsup.od.ua/api/jsonrpc`);
- **`-o` / `--output`** — куда сохранить `.docx`;
- **`--no-download`** — только `print`, в stdout выводится `result_id`;
- **`--dump-request`** — проверить тело запроса без HTTP.

Примеры с тестовыми данными см. в **`test-data/README.md`**.

---

## Конфигурация сервера (секция `docprinter`)

В общем JSON-конфиге (например `config/config.json`) обычно задают:

- **`output_dir`** — где хранятся `<result_id>.docx`;
- **`work_dir`** — временная распаковка архива;
- **`output_ttl_seconds`** — через сколько секунд уборщик может удалить старый файл;
- **`sweep_interval_seconds`** — период проверки.

---

## Быстрая диагностика «пустой» документ

Для проверочного набора **`test-data/v8_GOPJOV_5a.json`** и шаблона **UNI** корректный размер заполненного файла порядка **20 269** байт. Если получилось **18 420** байт — в шаблон ушёл **весь корень** `data.json` вместо внутреннего объекта данных: обновите сервер до актуального `print` и перезапустите процесс; в логе старта должна быть строка **`Loaded print_command from ... (command version ...)`** с путём к модулю из **этого** репозитория.

---

## Связь со старым конвейером

| Старый (`scripts-old`) | Новый DocPrinter |
|------------------------|------------------|
| JSON-файл на диске, `starter.py` вызывает `docbytpl` | Тот же JSON (или его части) как **`data.json`** в ZIP |
| Путь к шаблону из поля `data.template` | Файл шаблона всегда **`template.docx`** в ZIP (имена полей в JSON могут остаться, но пути на сервере не читаются) |
| `DocxTemplate(...).render(data["data"])` | То же семантически после разбора формата |
| `save(outfile)` | Результат через **`get_print_result`** и Base64 |

---

Author: Vasiliy Zdanovskiy  
email: vasilyvz@gmail.com
