# 🎉 Swagger MCP Server Generator - Project Status

**Universal Swagger/OpenAPI → MCP Server Converter**
Автоматическое создание полностью функциональных MCP серверов из любой Swagger/OpenAPI спецификации.

**Версия**: 0.1.0
**Статус**: ✅ Production Ready
**Последнее обновление**: 2025-09-30

---

## 🚀 Quick Start

### Одна команда создаёт полностью рабочий сервер:

```bash
PYTHONPATH=src poetry run swagger-mcp-server convert \
  path/to/your-swagger.json \
  -o generated-mcp-servers/your-api-server \
  --name "Your API" \
  --force
```

**Результат**: Готовый MCP сервер с заполненной базой данных, готов к использованию в Claude Desktop!

---

## ✅ Что работает

### 1. Автоматическое создание сервера
- ✅ Генерация server.py с FastMCP
- ✅ README.md с полной документацией
- ✅ Конфигурационные файлы
- ✅ Структура директорий

### 2. Автоматическое заполнение базы данных
- ✅ SQLite база с FTS5 индексами
- ✅ API Metadata с servers info
- ✅ Все endpoints из swagger
- ✅ Все schemas (OpenAPI 3.0 + Swagger 2.0)
- ✅ Поддержка любых Swagger/OpenAPI спецификаций

### 3. Три MCP метода

#### searchEndpoints
Поиск API endpoints по ключевым словам, HTTP методам, путям.

**Параметры**:
- `query` (string): Ключевые слова для поиска
- `method` (string, optional): HTTP метод (GET, POST, PUT, DELETE, PATCH)
- `limit` (int): Максимум результатов (default: 10)

**Возвращает**: Список endpoints с ID, path, method, summary, description

**Пример**:
```python
searchEndpoints(query="campaign", method="POST", limit=5)
```

#### getSchema
Получение детальной информации о schema с автоматическими подсказками.

**Параметры**:
- `schema_name` (string): Имя schema компонента
- `include_examples` (bool): Включить примеры (default: true)

**Возвращает**: Полная информация о schema с properties, types, required fields

**Особенности**:
- ✅ Автоматические подсказки при ошибке "Schema not found"
- ✅ Flattened schema names (см. раздел "Schema Naming")
- ✅ Детальное описание всех полей

**Пример**:
```python
getSchema(schema_name="StatisticsReportsListItemCampaign")
```

#### getExample
Генерация code examples с реальными URL из swagger.

**Параметры**:
- `endpoint_id` (string): Endpoint ID (integer/string) или path
- `language` (string): Язык (curl, python, javascript, typescript)

**Возвращает**: Готовый к использованию code example

**Поддерживаемые форматы**:
- `endpoint_id=6` - integer ID
- `endpoint_id="6"` - string integer ID
- `endpoint_id="/api/client/campaign"` - полный path
- `endpoint_id="api/client/campaign"` - path без слешей

**Языки**:
- **curl**: С headers и body для POST/PUT/PATCH
- **python**: С requests library
- **javascript**: С fetch API
- **typescript**: С типизацией

**Пример**:
```python
getExample(endpoint_id=6, language="javascript")
```

---

## 🔧 Технические детали

### Архитектура

```
swagger-mcp-server/
├── src/
│   └── swagger_mcp_server/
│       ├── conversion/         # Конверсия pipeline
│       │   ├── pipeline.py     # Основной pipeline с auto-population
│       │   ├── package_generator.py  # Генератор серверов
│       │   └── ...
│       ├── storage/            # База данных
│       │   ├── database.py     # DatabaseManager
│       │   ├── models.py       # SQLAlchemy models
│       │   └── repositories/   # Data access layer
│       ├── parser/             # Swagger parser
│       └── main.py             # CLI entry point
└── generated-mcp-servers/      # Созданные серверы
    └── your-api-server/
        ├── server.py           # MCP server
        ├── data/
        │   └── mcp_server.db   # SQLite база (автозаполненная)
        ├── config/
        │   └── server.yaml     # Конфигурация
        └── README.md           # Документация
```

### Ключевые исправления

| Компонент | Исправление | Файл | Строки |
|-----------|-------------|------|--------|
| **Output Suppression** | stderr → /dev/null, structlog suppression | package_generator.py | 19-43 |
| **Database Path** | Правильный относительный путь | package_generator.py | 127 |
| **HTTP Method** | endpoint.method вместо http_method | package_generator.py | 121, 243, 246 |
| **getExample URLs** | Реальные URL из swagger servers | package_generator.py | 276-385 |
| **getExample Matching** | Трёхступенчатый поиск (ID/path/fuzzy) | package_generator.py | 295-325 |
| **getSchema Errors** | Автоматические подсказки похожих схем | package_generator.py | 224-234 |
| **Auto-Population** | Автозаполнение базы после генерации | pipeline.py | 370-489 |

### База данных

**Таблицы**:
- `api_metadata`: Информация об API, servers
- `endpoints`: Все endpoints с методами, параметрами
- `schemas`: Все schemas с properties, required fields
- `endpoints_fts`, `schemas_fts`: FTS5 индексы для поиска

**Размер** (для Ozon API):
- 40 endpoints
- 87 schemas
- 454 KB база данных

---

## 📋 Schema Naming Guide

### Проблема: Flattened Names

OpenAPI schemas имеют вложенную структуру, но в базе хранятся с flattened именами:

| OpenAPI структура | Flattened имя в БД |
|-------------------|-------------------|
| `CreateProductCampaignRequest.V2.ProductCampaignPlacement.V2` | `CreateProductCampaignRequestV2ProductCampaignPlacementV2` |
| `Statistics.Reports.ListItem.Campaign` | `StatisticsReportsListItemCampaign` |
| `camptype.CampaignType` | `camptypeCampaignType` |

### Решение: Автоматические подсказки

При ошибке "Schema not found", сервер автоматически предлагает похожие схемы:

```
Schema 'Campaign' not found.

Did you mean one of these?
  - StatisticsReportsListItemCampaign
  - camptypeCampaignType
  - CalculateDynamicBudgetRequestCreateCampaignScenario
  - CreateProductCampaignRequestV2ProductCampaignPlacementV2
  - camptypeCampaignTypeInList

Note: Schema names are flattened from OpenAPI structure.
```

### Правила именования

1. **Все точки удалены**: `A.B.C` → `ABC`
2. **CamelCase сохранён**: `ProductList` остаётся `ProductList`
3. **Регистр важен**: `Campaign` ≠ `campaign`
4. **Без разделителей**: Нет точек, дефисов, подчёркиваний

---

## 🌐 Поддержка OpenAPI/Swagger

### OpenAPI 3.0

```json
{
  "openapi": "3.0.0",
  "info": {"title": "My API", "version": "1.0"},
  "servers": [{"url": "https://api.example.com"}],
  "paths": {...},
  "components": {"schemas": {...}}
}
```

✅ **Поддерживается**:
- `servers[0].url` для base URL
- `components.schemas` для schemas
- Все HTTP методы (GET, POST, PUT, DELETE, PATCH)

### Swagger 2.0

```json
{
  "swagger": "2.0",
  "info": {"title": "My API", "version": "1.0"},
  "host": "api.example.com",
  "schemes": ["https"],
  "basePath": "/v1",
  "paths": {...},
  "definitions": {...}
}
```

✅ **Поддерживается**:
- Автоматическое создание URL из `schemes[0]://host/basePath`
- `definitions` как fallback для schemas
- Полная совместимость

---

## 💻 Использование

### 1. Создание сервера

```bash
# Минимальная команда
swagger-mcp-server convert api.json -o my-server --force

# С кастомным именем
swagger-mcp-server convert api.json -o my-server --name "My API" --force

# С дополнительными опциями
swagger-mcp-server convert api.json \
  -o my-server \
  --name "My API" \
  --port 9000 \
  --force
```

### 2. Проверка результата

```bash
# Проверить базу данных
sqlite3 my-server/data/mcp_server.db \
  "SELECT COUNT(*) FROM endpoints; SELECT COUNT(*) FROM schemas;"

# Проверить servers info
sqlite3 my-server/data/mcp_server.db \
  "SELECT servers FROM api_metadata;"

# Проверить структуру
ls -lh my-server/data/
```

### 3. Добавление в Claude Desktop

**Путь к конфигу**: `~/.config/Claude/claude_desktop_config.json` (Linux/Mac)

```json
{
  "mcpServers": {
    "my-api": {
      "command": "/path/to/.venv/bin/python",
      "args": ["/path/to/my-server/server.py"],
      "env": {
        "PYTHONPATH": "/path/to/project/src"
      }
    }
  }
}
```

### 4. Перезапуск Claude Desktop

После добавления конфигурации перезапустите Claude Desktop.

### 5. Использование в Claude

```
Используй searchEndpoints чтобы найти endpoints для работы с кампаниями

Покажи мне schema для StatisticsReportsListItemCampaign

Сгенерируй Python пример для endpoint /api/client/statistics/video
```

---

## 🎯 Примеры

### Пример 1: Ozon Performance API

```bash
PYTHONPATH=src poetry run swagger-mcp-server convert \
  swagger-openapi-data/swagger.json \
  -o generated-mcp-servers/ozon-mcp-server \
  --force
```

**Результат**:
- ✅ 40 endpoints
- ✅ 87 schemas
- ✅ Base URL: `https://api-performance.ozon.ru:443`
- ✅ 454 KB база данных
- ✅ Полностью функциональный сервер

### Пример 2: Petstore API

```bash
PYTHONPATH=src poetry run swagger-mcp-server convert \
  examples/petstore.json \
  -o generated-mcp-servers/petstore \
  --name "Petstore API" \
  --force
```

### Пример 3: GitHub API

```bash
curl https://api.github.com/openapi -o github-openapi.json

PYTHONPATH=src poetry run swagger-mcp-server convert \
  github-openapi.json \
  -o generated-mcp-servers/github-api \
  --name "GitHub API" \
  --force
```

---

## 🐛 Troubleshooting

### База данных пустая

```bash
# Пересоздать сервер с автозаполнением
swagger-mcp-server convert api.json -o my-server --force
```

### JSON parsing error в Claude Desktop

**Причина**: Print statements или warnings в output

**Решение**: Все исправления уже применены в package_generator.py:
- stderr → /dev/null (строки 19-21)
- structlog suppression (строки 32-43)
- Удалены все print statements

### Schema not found

**Причина**: Flattened schema names

**Решение**: Используйте автоматические подсказки:
```python
getSchema("Campaign")  # Вернёт список похожих схем
```

### Endpoint not found в getExample

**Причина**: Неправильный формат endpoint_id

**Решение**: Используйте один из форматов:
- Integer ID: `6`
- String ID: `"6"`
- Full path: `"/api/client/campaign"`
- Path без слешей: `"api/client/campaign"`

---

## 📚 Документация для пользователей

### README.md в каждом сервере

Каждый созданный сервер содержит полный README.md с:
- Описанием API
- Инструкциями по запуску
- Документацией всех MCP методов
- Примерами использования
- Troubleshooting guide
- **Schema Naming Guide** (важно!)

### config/server.yaml

Конфигурационный файл для настройки:
- Host и port
- Logging level
- Cache size
- Search parameters

---

## 🔄 Development

### Установка

```bash
# Clone repository
git clone <repo-url>
cd bmad-openapi-mcp-server

# Install dependencies
poetry install

# Run tests
poetry run pytest
```

### Структура проекта

```
src/swagger_mcp_server/
├── conversion/         # Генерация серверов
│   ├── pipeline.py     # Основной pipeline
│   ├── package_generator.py  # Template engine
│   └── ...
├── storage/            # Database layer
├── parser/             # Swagger parsing
├── search/             # FTS5 search
└── main.py             # CLI
```

### Запуск тестов

```bash
# Все тесты
poetry run pytest

# С coverage
poetry run pytest --cov=swagger_mcp_server

# Specific test
poetry run pytest tests/unit/test_conversion/
```

---

## 🎉 Что нового

### Последние улучшения (2025-09-30)

1. **Автоматическое заполнение базы** (pipeline.py:370-489)
   - Теперь база заполняется автоматически при генерации
   - Одна команда для всего
   - Поддержка OpenAPI 3.0 и Swagger 2.0

2. **Улучшенный getExample** (package_generator.py:276-385)
   - Реальные URL из swagger.json
   - Поддержка 4 языков (curl, python, javascript, typescript)
   - Улучшенные примеры для POST/PUT/PATCH

3. **Трёхступенчатый поиск endpoints** (package_generator.py:295-325)
   - Поиск по ID (integer/string)
   - Точное совпадение по path
   - Fuzzy search как fallback

4. **Автоматические подсказки schemas** (package_generator.py:224-234)
   - При ошибке предлагаются похожие схемы
   - Документация о flattened names
   - Улучшенный UX

---

## 📞 Support

### Issues
GitHub Issues: <repository-url>/issues

### Documentation
- Project README.md
- Generated server README.md
- Schema Naming Guide

### Contributing
См. CONTRIBUTING.md для инструкций по контрибуции.

---

## ✅ Checklist для создания сервера

- [ ] Swagger/OpenAPI файл готов
- [ ] Определено имя сервера
- [ ] Выбрана output директория
- [ ] Запущена команда convert
- [ ] Проверена база данных (endpoints, schemas count)
- [ ] Добавлено в Claude Desktop config
- [ ] Перезапущен Claude Desktop
- [ ] Протестированы все 3 MCP метода

---

## 🚀 Ready to use!

Проект полностью готов к использованию. Одна команда создаёт полностью функциональный MCP сервер с заполненной базой данных, готовый к интеграции с Claude Desktop!