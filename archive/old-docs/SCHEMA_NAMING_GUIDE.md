# Schema Naming Guide for Ozon MCP Server

## Проблема: Flattened Schema Names

OpenAPI спецификация имеет вложенную структуру схем, но в SQLite базе они хранятся с "flattened" именами.

## Примеры преобразования

| OpenAPI структура | Flattened имя в БД |
|-------------------|-------------------|
| `CreateProductCampaignRequest.V2.ProductCampaignPlacement.V2` | `CreateProductCampaignRequestV2ProductCampaignPlacementV2` |
| `Statistics.Reports.ListItem.Campaign` | `StatisticsReportsListItemCampaign` |
| `camptype.CampaignType` | `camptypeCampaignType` |

## Как найти правильное имя схемы

### Способ 1: Использовать подсказки сервера

```python
# В Claude Desktop попробуйте:
getSchema('Campaign')

# Ответ:
# Schema 'Campaign' not found.
#
# Did you mean one of these?
#   - StatisticsReportsListItemCampaign
#   - camptypeCampaignType
#   - CalculateDynamicBudgetRequestCreateCampaignScenario
```

### Способ 2: Поиск через searchEndpoints

```python
# Найдите endpoint, который возвращает нужную схему
searchEndpoints('campaign list')

# В ответах увидите schemas в responses
```

### Способ 3: SQL запрос

```bash
sqlite3 generated-mcp-servers/ozon-mcp-server/data/mcp_server.db \
  "SELECT name FROM schemas WHERE name LIKE '%Campaign%';"
```

## Правила именования

1. **Все точки удалены**: `A.B.C` → `ABC`
2. **CamelCase сохранён**: `ProductList` остаётся `ProductList`
3. **Регистр важен**: `Campaign` ≠ `campaign`
4. **Без разделителей**: Нет точек, дефисов, подчёркиваний между частями

## Часто запрашиваемые схемы

```
❌ Campaign
✅ StatisticsReportsListItemCampaign
✅ camptypeCampaignType

❌ CampaignListResponse
✅ (проверьте через getSchema('CampaignListResponse') для подсказок)

❌ ErrorResponse
✅ (проверьте через getSchema('ErrorResponse') для подсказок)

❌ ProductCampaignPlacement
✅ CreateProductCampaignRequestV2ProductCampaignPlacementV2
```

## Если схема не найдена

1. **Попробуйте getSchema** - сервер предложит похожие имена
2. **Проверьте регистр** - имена чувствительны к регистру
3. **Используйте SQL** - посмотрите все доступные схемы:
   ```sql
   SELECT name FROM schemas ORDER BY name;
   ```
4. **Проверьте OpenAPI спец** - файл `swagger-openapi-data/swagger.json`
   в секции `components.schemas`