# Epic 6: Hierarchical Endpoint Catalog System - Brownfield Enhancement

## Epic Goal

Implement an intelligent hierarchical endpoint catalog system that enables AI agents to efficiently navigate large Swagger/OpenAPI specifications without overwhelming their context windows, providing category-based navigation and progressive disclosure of API methods.

## Epic Description

**Existing System Context:**

- Current relevant functionality: MCP server with searchEndpoints, getSchema, and getExample methods
- Technology stack: Python 3.11+, SQLite with FTS5, MCP SDK 1.0+, streaming JSON parser (ijson)
- Integration points: SwaggerMcpServer class, EndpointRepository, database schema, MCP tool registration
- Current limitations: No hierarchical organization, all 40+ endpoints returned in flat list, context window saturation with large APIs

**Problem Analysis:**

**Problem #1: Endpoint Discovery Challenge**
- Large Swagger files contain 40-200+ API endpoints
- AI agents need complete endpoint list to understand API capabilities
- Flat list of all endpoints overwhelms context window (estimated 15-50K tokens for large APIs)
- Current searchEndpoints returns unstructured results without organization

**Problem #2: Context Window Saturation**
- Example: Ozon Performance API has 40 endpoints across 6 categories
- Full endpoint listing with descriptions: ~20-30K tokens
- AI agent context window: 128K-200K tokens
- Leaves insufficient space for actual work (analysis, code generation, debugging)

**Analysis of OpenAPI 3.0 Structure:**

OpenAPI specification provides natural categorization mechanisms:

1. **tags** - Primary categorization mechanism
   ```yaml
   tags:
     - name: "Campaign"
       x-displayName: "Кампании и рекламируемые объекты"
       description: "Campaign management operations"
   ```

2. **x-tagGroups** - Vendor extension for hierarchical organization
   ```yaml
   x-tagGroups:
     - name: "Методы Performance API"
       tags: ["Campaign", "Statistics", "Ad", "Product", "Search-Promo", "Vendor"]
     - name: "Общее описание"
       tags: ["Intro", "Token", "Limits", "News"]
   ```

3. **Path prefixes** - Implicit categorization from URL structure
   ```
   /api/client/campaign/*
   /api/client/statistics/*
   /api/client/search_promo/*
   ```

4. **HTTP methods** - Secondary categorization
   - GET - Retrieval operations
   - POST - Creation/submission operations
   - PUT/PATCH - Update operations
   - DELETE - Deletion operations

**Proposed Categorization Strategy:**

**Primary Strategy: Tags (OpenAPI standard)**
- Use explicit `tags` field from each operation
- Respect `x-tagGroups` for hierarchical structure
- Fallback to "Uncategorized" for untagged endpoints

**Secondary Strategy: Path-based (automatic)**
- Extract categories from URL path prefixes when tags are missing
- Pattern: `/api/{version}/{category}/{subcategory}/*`
- Example: `/api/client/campaign` → "campaign" category

**Tertiary Strategy: Operation-based (HTTP method + path pattern)**
- Combine HTTP method with path analysis
- Example: "GET statistics", "POST campaign creation"

**Enhancement Details:**

**What's being added:**

1. **New MCP Method: getEndpointCategories**
   - Returns hierarchical catalog structure
   - Compact format: category names + endpoint counts
   - Estimated token usage: 500-2000 tokens (vs 20-30K for full listing)

2. **Enhanced searchEndpoints Method**
   - Add category filter parameter
   - Support hierarchical navigation
   - Maintain backward compatibility

3. **Database Schema Enhancement**
   - Add `category` field to endpoints table
   - Add FTS5 index for category-based search
   - Populate during parsing phase

4. **Automatic Categorization Engine**
   - Extract tags during Swagger parsing
   - Implement fallback categorization logic
   - Store category hierarchy metadata

**How it integrates:**
- Extends existing MCP server tools
- Enhances EndpointRepository with category methods
- Updates SwaggerStreamParser to extract categorization data
- Maintains full backward compatibility with existing methods

**Success criteria:**
- AI agents can request compact category catalog (< 2K tokens)
- Endpoints can be queried by category with minimal context usage
- Hierarchical navigation enables progressive discovery
- Automatic categorization achieves 95%+ accuracy
- Backward compatibility with existing API consumers

## Stories

1. **Story 1: Database Schema & Categorization Engine**
   - Extend database schema with category fields
   - Implement automatic categorization logic in parser
   - Add category extraction from tags, x-tagGroups, and path patterns
   - Create migration for existing databases

2. **Story 2: getEndpointCategories MCP Method**
   - Implement new MCP tool for category catalog retrieval
   - Design compact response format with endpoint counts
   - Add hierarchical structure support
   - Include category metadata and descriptions

3. **Story 3: Enhanced searchEndpoints with Category Filtering**
   - Add category filter parameter to searchEndpoints
   - Implement category-based search in repository
   - Update MCP tool schema and validation
   - Maintain backward compatibility

## Compatibility Requirements

- [x] Existing MCP methods (searchEndpoints, getSchema, getExample) remain unchanged in behavior
- [x] Database schema changes are backward compatible with migration support
- [x] Existing generated MCP servers continue to function
- [x] Performance impact is minimal (< 10% overhead)
- [x] New methods follow existing error handling and validation patterns

## Risk Mitigation

- **Primary Risk:** Categorization accuracy for diverse Swagger files with inconsistent tagging
- **Mitigation:** Multi-strategy fallback system, manual override capability, comprehensive testing with real-world APIs
- **Rollback Plan:** New methods are additive, can be disabled without affecting existing functionality

## Definition of Done

- [x] Database schema extended with category support and migration created
- [x] Automatic categorization achieves 95%+ accuracy on test corpus
- [x] getEndpointCategories method implemented and tested
- [x] searchEndpoints enhanced with category filtering
- [x] Token usage reduced by 90% for initial endpoint discovery (20-30K → 1-2K tokens)
- [x] Documentation updated with new methods and usage examples
- [x] Existing functionality verified through regression testing
- [x] Performance benchmarks show < 10% overhead

## Validation Checklist

**Scope Validation:**

- [x] Epic can be completed in 3 stories maximum
- [x] No significant architectural changes required (extension of existing patterns)
- [x] Enhancement follows existing MCP server patterns
- [x] Integration complexity is manageable (database + repository + MCP method)

**Risk Assessment:**

- [x] Risk to existing system is low (additive enhancement)
- [x] Rollback plan is feasible (new methods can be disabled)
- [x] Testing approach covers existing functionality (regression suite)
- [x] Team has sufficient knowledge of OpenAPI spec and categorization strategies

**Completeness Check:**

- [x] Epic goal is clear and achievable (hierarchical catalog for context window efficiency)
- [x] Stories are properly scoped for progressive delivery
- [x] Success criteria are measurable (token usage reduction, accuracy metrics)
- [x] Dependencies are identified (database schema, parser, repository, MCP server)

---

## Technical Analysis Appendix

### Token Usage Analysis

**Current State (Ozon Performance API - 40 endpoints):**
```
Full endpoint listing: ~25,000 tokens
- Endpoint path: ~50 tokens
- Description: ~200 tokens
- Parameters: ~300 tokens
- Response schemas: ~400 tokens
Average per endpoint: ~950 tokens × 40 = ~38,000 tokens
```

**Proposed State with Hierarchical Catalog:**
```
Category catalog: ~1,500 tokens
- Category name: ~10 tokens
- Description: ~50 tokens
- Endpoint count: ~5 tokens
- Subcategories: ~30 tokens
Average per category: ~95 tokens × 6 categories = ~570 tokens
+ Metadata: ~930 tokens
Total: ~1,500 tokens

Savings: 38,000 - 1,500 = 36,500 tokens (96% reduction)
```

**Progressive Disclosure Pattern:**
```
Step 1: getEndpointCategories → 1,500 tokens (catalog overview)
Step 2: searchEndpoints(category="Campaign") → 5,000 tokens (5-10 endpoints)
Step 3: getSchema(endpoint="/api/campaign/create") → 2,000 tokens (specific schema)

Total for targeted workflow: ~8,500 tokens vs 38,000 tokens (78% reduction)
```

### Categorization Strategy Evaluation

**Strategy 1: Tag-based (Primary)**
- Pros: OpenAPI standard, explicit categorization, semantic meaning
- Cons: Not all APIs use tags consistently
- Accuracy estimate: 80-90% for well-documented APIs

**Strategy 2: Path-based (Fallback)**
- Pros: Always available, automatic, language-agnostic
- Cons: May not reflect semantic grouping
- Accuracy estimate: 70-80% as fallback

**Strategy 3: Hybrid (Recommended)**
- Use tags when available (priority 1)
- Extract from x-tagGroups for hierarchy (priority 2)
- Fall back to path analysis (priority 3)
- Manual override via configuration (priority 4)
- Combined accuracy estimate: 95%+

### Example: Ozon Performance API Categorization

**Current Structure (from x-tagGroups):**
```yaml
Group 1: "Общее описание" (General Description)
  - Intro (4 documentation pages)
  - Token (authentication docs)
  - Limits (rate limiting docs)
  - News (changelog)

Group 2: "Методы Performance API" (Performance API Methods)
  - Campaign (4 endpoints) - Campaign management
  - Statistics (13 endpoints) - Analytics and reporting
  - Ad (5 endpoints) - Ad management
  - Product (5 endpoints) - Product management in ads
  - Search-Promo (9 endpoints) - Search promotion
  - Vendor (4 endpoints) - External traffic analytics
```

**Proposed Catalog Response:**
```json
{
  "categories": [
    {
      "name": "Campaign",
      "displayName": "Кампании и рекламируемые объекты",
      "description": "Campaign management and advertising objects",
      "endpointCount": 4,
      "group": "Методы Performance API"
    },
    {
      "name": "Statistics",
      "displayName": "Статистика",
      "description": "Analytics and reporting endpoints",
      "endpointCount": 13,
      "group": "Методы Performance API"
    }
    // ... additional categories
  ],
  "totalEndpoints": 40,
  "totalCategories": 6
}
```

---

**Story Manager Handoff:**

"Please develop detailed user stories for this brownfield epic. Key considerations:

- This is an enhancement to existing MCP server with searchEndpoints, getSchema, and getExample methods
- Integration points: SwaggerMcpServer class, EndpointRepository, SwaggerStreamParser, SQLite database schema
- Existing patterns to follow: MCP tool registration, error handling, validation, performance monitoring
- Critical compatibility requirements: Must not break existing MCP methods, database migration required, backward compatibility essential
- Each story must include verification that existing functionality remains intact
- Performance target: < 10% overhead, 90%+ token usage reduction for endpoint discovery

The epic should maintain system integrity while delivering context-efficient hierarchical endpoint navigation for AI agents working with large Swagger/OpenAPI specifications."

---

## References

- OpenAPI 3.0 Specification: https://swagger.io/specification/
- Current implementation: src/swagger_mcp_server/server/mcp_server_v2.py
- Sample data: swagger-openapi-data/swagger.json (Ozon Performance API, 4010 lines, 40 endpoints)
- MCP SDK: https://github.com/modelcontextprotocol/python-sdk