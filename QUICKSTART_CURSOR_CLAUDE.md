# 🚀 Быстрый старт: MCP сервер для Cursor и Claude Code

> **5 минут до полной интеграции с Ozon Performance API**

## ⚡ Мгновенная настройка

### 1. Клонируйте и подготовьте

```bash
git clone https://github.com/salacoste/openapi-mcp-swagger.git
cd openapi-mcp-swagger
chmod +x scripts/standalone-mcp.py
```

### 2. Проверьте работу

```bash
# Тест поиска endpoints
echo '{"method": "searchEndpoints", "params": {"keywords": "campaign"}}' | \
python3 scripts/standalone-mcp.py swagger-openapi-data/swagger.json --stdio

# Тест генерации кода
echo '{"method": "getExample", "params": {"endpointId": "auth", "language": "javascript"}}' | \
python3 scripts/standalone-mcp.py swagger-openapi-data/swagger.json --stdio
```

## 🎯 Cursor IDE - настройка за 30 секунд

### Автоматическая настройка

```bash
# Создайте директорию для MCP конфигурации
mkdir -p .cursor-mcp

# Скопируйте готовую конфигурацию
cp configs/cursor-mcp.json .cursor-mcp/config.json

# Готово! Перезапустите Cursor
```

### Проверьте работу в Cursor

После перезапуска Cursor попробуйте в чате:

```
/ozon-search campaign

/ozon-schema Campaign

/ozon-example createCampaign
```

## 🤖 Claude Code - настройка за 1 минуту

### Способ 1: Автоимпорт конфигурации

1. Откройте Claude Code
2. Settings → Extensions → MCP Servers
3. "Import Configuration"
4. Выберите файл `configs/claude-code-mcp.json`

### Способ 2: Ручная настройка

В настройках Claude Code добавьте:

```json
{
  "claude.mcpServers": [
    {
      "name": "ozon-performance",
      "command": "python3",
      "args": [
        "./scripts/standalone-mcp.py",
        "./swagger-openapi-data/swagger.json",
        "--stdio"
      ]
    }
  ]
}
```

### Проверьте работу в Claude Code

```
Найди все методы для работы с кампаниями

@mcp:searchEndpoints keywords="statistics"

Создай TypeScript класс для работы с Ozon API
```

## 🔥 Что вы можете делать прямо сейчас

### 1. Интеллектуальный поиск API

```
# В Cursor:
/ozon-search "получение статистики"

# В Claude Code:
Найди все endpoints для работы со статистикой кампаний
```

**Результат:** Список релевантных API endpoints с описаниями

### 2. Автогенерация кода

```
# В любом инструменте:
Создай функцию для авторизации в Ozon Performance API

# Или конкретнее:
Создай TypeScript класс OzonClient с методами:
- получения токена
- создания кампании
- получения статистики
```

**Результат:** Полный рабочий код с типами и обработкой ошибок

### 3. Быстрый доступ к схемам

```
Покажи схему данных для создания рекламной кампании
```

**Результат:** JSON Schema с описанием всех полей

### 4. Создание полных модулей

```
Создай полный модуль для интеграции с Ozon Performance API включая:
- Аутентификацию с автообновлением токена
- CRUD операции для кампаний
- Получение статистики с фильтрами
- Обработку ошибок и retry логику
- TypeScript типы
```

**Результат:** Производственно-готовый модуль

## 🛠️ Диагностика проблем

### Проблема: MCP сервер не запускается

```bash
# Проверьте Python
python3 --version

# Проверьте скрипт
python3 scripts/standalone-mcp.py swagger-openapi-data/swagger.json

# Если ошибки, установите зависимости
pip install -r requirements.txt
```

### Проблема: Cursor не видит MCP сервер

1. Проверьте файл `.cursor-mcp/config.json`
2. Перезапустите Cursor полностью
3. Проверьте Developer Console (`Cmd/Ctrl + Shift + I`)

### Проблема: Claude Code не подключается

1. Settings → Extensions → MCP Servers
2. Проверьте статус сервера
3. Output Panel → MCP Server (проверьте логи)

## 🎊 Готовые примеры

### JavaScript - Полный клиент Ozon API

```javascript
class OzonPerformanceClient {
  constructor(clientId, clientSecret) {
    this.clientId = clientId;
    this.clientSecret = clientSecret;
    this.baseUrl = 'https://api-performance.ozon.ru';
    this.accessToken = null;
    this.tokenExpiry = null;
  }

  async getAuthToken() {
    const response = await fetch(`${this.baseUrl}/api/client/token`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        client_id: this.clientId,
        client_secret: this.clientSecret,
        grant_type: 'client_credentials'
      })
    });

    const data = await response.json();
    this.accessToken = data.access_token;
    this.tokenExpiry = Date.now() + (data.expires_in * 1000);
    return data;
  }

  async ensureValidToken() {
    if (!this.accessToken || Date.now() >= this.tokenExpiry) {
      await this.getAuthToken();
    }
  }

  async apiCall(endpoint, method = 'GET', data = null) {
    await this.ensureValidToken();

    const options = {
      method,
      headers: {
        'Authorization': `Bearer ${this.accessToken}`,
        'Content-Type': 'application/json'
      }
    };

    if (data) {
      options.body = JSON.stringify(data);
    }

    return fetch(`${this.baseUrl}${endpoint}`, options);
  }

  // Методы для работы с кампаниями
  async getCampaigns() {
    return this.apiCall('/api/client/campaign');
  }

  async createCampaign(campaignData) {
    return this.apiCall('/api/client/campaign', 'POST', campaignData);
  }

  async getStatistics(params) {
    return this.apiCall('/api/client/statistics/daily', 'POST', params);
  }
}
```

### Python - Async клиент с типами

```python
import asyncio
import aiohttp
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

class OzonPerformanceClient:
    def __init__(self, client_id: str, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.base_url = "https://api-performance.ozon.ru"
        self.access_token: Optional[str] = None
        self.token_expiry: Optional[datetime] = None
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def get_auth_token(self) -> Dict[str, Any]:
        async with self.session.post(
            f"{self.base_url}/api/client/token",
            json={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "grant_type": "client_credentials"
            }
        ) as response:
            data = await response.json()
            self.access_token = data["access_token"]
            self.token_expiry = datetime.now() + timedelta(seconds=data["expires_in"])
            return data

    async def ensure_valid_token(self):
        if not self.access_token or datetime.now() >= self.token_expiry:
            await self.get_auth_token()

    async def api_call(self, endpoint: str, method: str = "GET", data: Dict = None):
        await self.ensure_valid_token()

        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }

        async with self.session.request(
            method,
            f"{self.base_url}{endpoint}",
            json=data,
            headers=headers
        ) as response:
            return await response.json()

# Использование:
# async with OzonPerformanceClient(client_id, client_secret) as client:
#     campaigns = await client.api_call("/api/client/campaign")
```

## 🚀 Следующие шаги

1. **Изучите полную документацию**: [`docs/guides/CURSOR_CLAUDE_INTEGRATION.md`](docs/guides/CURSOR_CLAUDE_INTEGRATION.md)

2. **Настройте для своего API**: Замените `swagger-openapi-data/swagger.json` на ваш Swagger файл

3. **Создайте продакшн систему**: Используйте полный MCP сервер с базой данных и поиском

4. **Поделитесь результатом**: Создайте issue в репозитории с вашими кейсами использования

**🎉 Готово! Теперь у вас есть интеллектуальный помощник для работы с любым API прямо в вашем любимом редакторе!**