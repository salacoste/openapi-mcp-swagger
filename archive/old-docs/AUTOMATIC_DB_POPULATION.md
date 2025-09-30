# ✅ Автоматическое заполнение базы данных

## Проблема

Раньше требовалось:
1. Запустить команду convert для создания сервера
2. Вручную создать скрипт populate
3. Запустить скрипт для заполнения базы

## Решение

Теперь **всё происходит автоматически** одной командой!

### Одна команда для всего:

```bash
PYTHONPATH=src poetry run swagger-mcp-server convert \
  swagger-openapi-data/swagger.json \
  -o generated-mcp-servers/my-api-server \
  --force
```

## Что происходит автоматически

### 1. Создание сервера
- Генерация server.py с всеми исправлениями
- Создание README.md и конфигурации
- Настройка структуры директорий

### 2. Автоматическое заполнение базы
- ✅ Инициализация SQLite базы данных
- ✅ Создание APIMetadata с servers info
- ✅ Вставка всех endpoints (40)
- ✅ Вставка всех schemas (87)
- ✅ FTS5 индексы для поиска

### 3. Проверка результатов
```bash
sqlite3 generated-mcp-servers/my-api-server/data/mcp_server.db \
  "SELECT COUNT(*) FROM endpoints; SELECT COUNT(*) FROM schemas;"
```

## Реализация

### pipeline.py (строки 105-106, 370-489)

**Добавлена фаза 3.5**: Автоматическое заполнение базы после генерации сервера

```python
# Phase 3.5: Populate real database with API data
await self._populate_database(parsed_data)
```

**Метод `_populate_database`**:
1. Удаляет mock database если существует
2. Инициализирует реальную SQLite базу
3. Загружает swagger.json
4. Извлекает servers (OpenAPI 3.0) или создаёт из host/schemes (Swagger 2.0)
5. Создаёт APIMetadata с servers info
6. Вставляет все endpoints
7. Вставляет все schemas (OpenAPI 3.0 или Swagger 2.0)
8. Коммитит транзакцию

**Логирование**:
```
2025-09-30 03:22:13 [info] Initializing database...
2025-09-30 03:22:13 [info] FTS5 tables and triggers created successfully
2025-09-30 03:22:13 [debug] Entity created entity_id=1 entity_type=APIMetadata
2025-09-30 03:22:13 [debug] Entity created entity_id=1 entity_type=Endpoint
... (40 endpoints)
2025-09-30 03:22:13 [debug] Entity created entity_id=1 entity_type=Schema
... (87 schemas)
2025-09-30 03:22:13 [info] Database populated successfully endpoints=40 schemas=87
```

## Универсальность

Работает для **любых** Swagger/OpenAPI спецификаций:

### OpenAPI 3.0
```json
{
  "openapi": "3.0.0",
  "servers": [{"url": "https://api.example.com"}]
}
```
→ Использует `servers[0].url`

### Swagger 2.0
```json
{
  "swagger": "2.0",
  "host": "api.example.com",
  "schemes": ["https"],
  "basePath": "/v1"
}
```
→ Создаёт URL: `https://api.example.com/v1`

### Без servers
→ Fallback: `https://api.example.com`

## Примеры использования

### Пример 1: Ozon API
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

### Пример 2: Custom API
```bash
PYTHONPATH=src poetry run swagger-mcp-server convert \
  /path/to/your-api.json \
  -o generated-mcp-servers/your-api-server \
  --name "Your API Server" \
  --force
```

**Результат**: Готовый к использованию MCP сервер с заполненной базой!

### Пример 3: С кастомным именем
```bash
PYTHONPATH=src poetry run swagger-mcp-server convert \
  petstore.json \
  -o generated-mcp-servers/petstore \
  --name "Petstore API" \
  --force
```

## Команды для пользователя

### Простой вариант:
```bash
swagger-mcp-server convert <swagger_file> -o <output_dir> --force
```

### С кастомным именем:
```bash
swagger-mcp-server convert <swagger_file> -o <output_dir> --name "My API" --force
```

### Параметры:
- `<swagger_file>`: Путь к вашему swagger.json или openapi.json
- `<output_dir>`: Директория для созданного сервера
- `--name`: Опциональное имя для сервера (по умолчанию из API title)
- `--force`: Перезаписать если директория существует

## Результат

После выполнения команды вы получаете **полностью готовый MCP сервер**:
- ✅ Сервер создан
- ✅ База данных заполнена
- ✅ Все endpoints доступны
- ✅ Все schemas доступны
- ✅ Реальные URL из swagger
- ✅ Готов к использованию в Claude Desktop

### Запуск сервера:
```bash
cd <output_dir>
python server.py
```

### Добавление в Claude Desktop:
```json
{
  "mcpServers": {
    "my-api": {
      "command": "/path/.venv/bin/python",
      "args": ["/path/output_dir/server.py"],
      "env": {"PYTHONPATH": "/path/src"}
    }
  }
}
```

## Готово! 🎉

Теперь для создания полностью рабочего MCP сервера нужна всего **одна команда**!