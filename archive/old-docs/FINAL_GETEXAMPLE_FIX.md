# ✅ getExample Исправление - Реальные URL из Swagger

## Проблема
getExample генерировал примеры с hardcoded URL `https://api.example.com` вместо реального адреса API из swagger.json.

## Решение

### 1. Обновлён package_generator.py (строки 276-385)

**Добавлено**:
- Получение APIMetadata через MetadataRepository
- Извлечение base URL из `api_metadata.servers[0].url` (OpenAPI 3.0)
- Fallback на `api_metadata.base_url` (Swagger 2.0)
- Улучшенная генерация примеров для разных языков

**Ключевой код**:
```python
# Get API metadata for base URL
api_metadata = await metadata_repo.get_by_id(endpoint.api_id)

# Determine base URL
base_url = "https://api.example.com"
if api_metadata:
    if api_metadata.servers:
        import json
        servers = json.loads(api_metadata.servers) if isinstance(api_metadata.servers, str) else api_metadata.servers
        if servers and len(servers) > 0:
            base_url = servers[0].get("url", base_url)
    elif api_metadata.base_url:
        base_url = api_metadata.base_url

# Build full URL
full_url = f"{base_url}{endpoint.path}"
```

### 2. Улучшена генерация примеров

**Поддерживаемые языки**:
- **curl**: С headers и body для POST/PUT/PATCH
- **python**: С requests library и правильной структурой
- **javascript**: С fetch API и обработкой ответа
- **typescript**: С типизацией и async/await

**Пример для POST endpoint**:

**curl**:
```bash
curl -X POST 'https://api-performance.ozon.ru:443/api/client/statistics/video' \
  -H 'Content-Type: application/json' \
  -d '{}'
```

**python**:
```python
import requests

url = 'https://api-performance.ozon.ru:443/api/client/statistics/video'
headers = {'Content-Type': 'application/json'}
data = {}

response = requests.post(url, headers=headers, json=data)
print(response.json())
```

**javascript**:
```javascript
const url = 'https://api-performance.ozon.ru:443/api/client/statistics/video';

fetch(url, {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({})
})
  .then(response => response.json())
  .then(data => console.log(data));
```

**typescript**:
```typescript
const url: string = 'https://api-performance.ozon.ru:443/api/client/statistics/video';

const response = await fetch(url, {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({})
});

const data = await response.json();
console.log(data);
```

### 3. Populate script с servers info

Создан скрипт `populate_ozon_server.py` который:
- Извлекает `servers` из OpenAPI 3.0 spec
- Fallback для Swagger 2.0 (создаёт servers из `host` + `schemes`)
- Сохраняет servers info в APIMetadata

**Код извлечения**:
```python
# Extract servers from OpenAPI 3.0
servers = swagger.get('servers', [])
if not servers and swagger.get('host'):
    # Fallback for Swagger 2.0
    scheme = swagger.get('schemes', ['https'])[0]
    host = swagger.get('host')
    base_path = swagger.get('basePath', '')
    servers = [{"url": f"{scheme}://{host}{base_path}"}]

api = APIMetadata(
    ...
    servers=json.dumps(servers) if servers else None
)
```

## Результаты

### База данных
```sql
SELECT servers FROM api_metadata WHERE id=1;
-- "[{\"url\": \"https://api-performance.ozon.ru:443\"}]"
```

### Тест getExample
```python
# Запрос
getExample(endpoint_id='/api/client/statistics/video', language='javascript')

# Ответ
# JAVASCRIPT example for POST /api/client/statistics/video

const url = 'https://api-performance.ozon.ru:443/api/client/statistics/video';

fetch(url, {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({})
})
  .then(response => response.json())
  .then(data => console.log(data));
```

## Универсальность

Решение работает для любых Swagger/OpenAPI спецификаций:

1. **OpenAPI 3.0**: Использует `servers[0].url`
2. **Swagger 2.0**: Создаёт URL из `schemes[0]://host/basePath`
3. **Fallback**: `https://api.example.com` если ничего не найдено

## Файлы изменены

- ✅ `src/swagger_mcp_server/conversion/package_generator.py` (строки 276-385)
- ✅ `generated-mcp-servers/ozon-mcp-server/server.py` (автогенерирован)
- ✅ База данных с servers info (444 KB)

## Готово к использованию! 🎉

Перезапустите Claude Desktop и проверьте getExample - теперь все примеры будут использовать реальные URL из вашего Swagger файла.