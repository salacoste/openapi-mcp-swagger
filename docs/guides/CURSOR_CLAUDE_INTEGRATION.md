# Интеграция с Cursor и Claude Code

> Пошаговое руководство по использованию MCP сервера в Cursor IDE и Claude Code без внешних AI API ключей

## 🎯 Что вы получите

- ✅ Интеллектуальный поиск по Ozon Performance API
- ✅ Автогенерация кода на JavaScript/Python
- ✅ Быстрый доступ к схемам данных API
- ✅ Контекстные подсказки и примеры
- ✅ Без необходимости в API ключах OpenAI/Anthropic

## 🚀 Быстрый старт

### 1. Подготовка

```bash
# Клонируйте репозиторий
git clone https://github.com/salacoste/openapi-mcp-swagger.git
cd openapi-mcp-swagger

# Сделайте скрипт исполняемым
chmod +x scripts/standalone-mcp.py

# Протестируйте работу
python3 scripts/standalone-mcp.py swagger-openapi-data/swagger.json
```

### 2. Настройка для Cursor IDE

#### Способ 1: Автоматическая настройка

Скопируйте конфигурацию:
```bash
cp configs/cursor-mcp.json .cursor-mcp/config.json
```

#### Способ 2: Ручная настройка

1. Откройте Cursor IDE
2. Нажмите `Cmd/Ctrl + Shift + P`
3. Введите "MCP Settings" и выберите настройки
4. Добавьте конфигурацию:

```json
{
  "mcpServers": {
    "ozon-performance": {
      "command": "python3",
      "args": [
        "./scripts/standalone-mcp.py",
        "./swagger-openapi-data/swagger.json",
        "--stdio"
      ]
    }
  }
}
```

### 3. Настройка для Claude Code

1. Откройте Claude Code
2. Перейдите в Settings > Extensions > MCP Servers
3. Нажмите "Add MCP Server"
4. Загрузите файл `configs/claude-code-mcp.json`

## 💡 Практические примеры

### В Cursor IDE

После настройки вы можете использовать следующие команды в чате:

#### Поиск endpoints

```
/ozon-search campaign management

# Результат:
🎯 Найдены endpoints для управления кампаниями:
- POST /api/client/campaign - Создание кампании
- GET /api/client/campaign - Получение списка кампаний
- PUT /api/client/campaign - Обновление кампании
```

#### Получение схем

```
/ozon-schema Campaign

# Результат:
📋 Схема Campaign:
{
  "type": "object",
  "properties": {
    "title": {"type": "string", "description": "Название кампании"},
    "advObjectType": {"type": "string", "enum": ["SKU", "BRAND"]},
    "weekBudget": {"type": "number", "description": "Недельный бюджет"}
  }
}
```

#### Генерация кода

```
/ozon-example createCampaign

# Результат: Полный JavaScript код для создания кампании
```

### В Claude Code

Используйте инструменты MCP прямо в чате:

```
Найди все методы для работы со статистикой в Ozon API

@mcp:searchEndpoints keywords="statistics" httpMethods=["GET","POST"]

Создай TypeScript интерфейс для создания рекламной кампании

@mcp:getSchema componentName="Campaign"
```

## 🔥 Продвинутые возможности

### 1. Умный поиск с фильтрами

```
Найди все POST методы для работы с рекламными объявлениями

# Cursor автоматически вызовет:
# searchEndpoints(keywords="advertisement", httpMethods=["POST"])
```

### 2. Автогенерация полных модулей

```
Создай полный TypeScript модуль для работы с Ozon Performance API включая:
- Аутентификацию
- Управление кампаниями
- Получение статистики
- Обработку ошибок

# Результат: Полный модуль с типами, классами и методами
```

### 3. Анализ и рекомендации

```
Проанализируй Ozon Performance API и предложи архитектуру клиентского приложения

# Получите детальный анализ с рекомендациями по архитектуре
```

## 🛠️ Отладка и диагностика

### Проверка работы MCP сервера

```bash
# Тестирование в интерактивном режиме
python3 scripts/standalone-mcp.py swagger-openapi-data/swagger.json

# Ввод для тестирования:
{"method": "searchEndpoints", "params": {"keywords": "campaign"}}
```

### Проверка конфигурации Cursor

1. Откройте Developer Tools в Cursor (`Cmd/Ctrl + Shift + I`)
2. Перейдите на вкладку Console
3. Посмотрите на ошибки MCP подключения

### Логи Claude Code

1. В Claude Code откройте Output Panel
2. Выберите "MCP Server" в dropdown
3. Проверьте логи подключения

## 📚 Справочник команд

### Cursor Slash Commands

| Команда | Описание | Пример |
|---------|----------|---------|
| `/ozon-search <keywords>` | Поиск endpoints | `/ozon-search campaign` |
| `/ozon-schema <name>` | Получение схемы | `/ozon-schema Campaign` |
| `/ozon-example <endpoint>` | Генерация примера | `/ozon-example createCampaign` |

### Claude Code Tools

| Инструмент | Параметры | Описание |
|------------|-----------|----------|
| `searchEndpoints` | keywords, httpMethods, maxResults | Поиск API endpoints |
| `getSchema` | componentName, maxDepth | Получение схем данных |
| `getExample` | endpointId, language, style | Генерация примеров кода |

## 🔧 Настройка под ваши потребности

### Добавление новых языков программирования

Отредактируйте `scripts/standalone-mcp.py`, добавьте новые шаблоны в метод `get_example()`:

```python
"go": {
    "auth": '''
package main

import (
    "bytes"
    "encoding/json"
    "net/http"
)

func getOzonAuthToken(clientID, clientSecret string) (*AuthResponse, error) {
    // Go implementation
}'''
}
```

### Добавление новых API

Просто замените файл swagger:

```bash
# Для другого API
python3 scripts/standalone-mcp.py your-api-swagger.json --stdio
```

### Кастомизация ответов

Модифицируйте методы в `StandaloneMCPServer` для изменения формата ответов под ваши нужды.

## 💭 Примеры реальных задач

### Задача 1: Создание системы мониторинга кампаний

```
Создай систему мониторинга рекламных кампаний Ozon с:
- Автоматическим получением статистики каждый час
- Уведомлениями при превышении бюджета
- Dashboard с графиками эффективности
- Автоматической паузой неэффективных кампаний
```

### Задача 2: Интеграция с CRM

```
Создай интеграцию Ozon Performance API с CRM системой:
- Синхронизация данных о продуктах
- Автоматическое создание кампаний для новых товаров
- Отчеты по ROI в разрезе товарных категорий
```

### Задача 3: A/B тестирование объявлений

```
Разработай систему A/B тестирования рекламных кампаний:
- Автоматическое создание вариантов объявлений
- Статистически значимое сравнение результатов
- Автоматическое переключение на победивший вариант
```

Теперь вы можете эффективно работать с Ozon Performance API прямо в Cursor и Claude Code без необходимости настройки внешних AI API! 🚀