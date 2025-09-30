# Issue #003: getEndpointCategories Not Registered as MCP Tool

**Status:** 🔴 Bug
**Priority:** High
**Severity:** Medium
**Category:** API Registration
**Component:** MCP Server - Tool Registration
**Detected:** 2025-09-30 20:58:46 UTC
**Environment:** Production MCP Server (ozon-api)
**Related Epic:** Epic 6.2 - Get Endpoint Categories MCP Method

---

## 📋 Problem Description

The `getEndpointCategories` method was implemented as part of Epic 6.2, but it is not appearing in the list of available MCP tools when the server initializes. This makes the method completely inaccessible to MCP clients (like Claude Desktop).

### Current Server Tools List

When the MCP server initializes, it responds with only 3 tools:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "tools": [
      {
        "name": "searchEndpoints",
        "description": "Search API endpoints by keyword...",
        "inputSchema": {...}
      },
      {
        "name": "getSchema",
        "description": "Get detailed schema definition...",
        "inputSchema": {...}
      },
      {
        "name": "getExample",
        "description": "Generate code examples...",
        "inputSchema": {...}
      }
    ]
  }
}
```

### Missing Tool

**Expected but not present:**
```json
{
  "name": "getEndpointCategories",
  "description": "Get list of endpoint categories...",
  "inputSchema": {...}
}
```

---

## 🔍 Evidence from Logs

**Log File:** `/Users/r2d2/Library/Logs/Claude/mcp-server-ozon-api.log`

**Server Initialization at 20:58:46:**
```json
2025-09-30T20:58:46.195Z [ozon-api] [info] Message from client: {
  "method": "tools/list",
  "params": {},
  "jsonrpc": "2.0",
  "id": 1
}

2025-09-30T20:58:46.197Z [ozon-api] [info] Message from server: {
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "tools": [
      {"name": "searchEndpoints", ...},
      {"name": "getSchema", ...},
      {"name": "getExample", ...}
    ]
  }
}
```

**Observation:** No `getEndpointCategories` in the tools list.

**Client Behavior:** Throughout the entire session (38 requests), there are ZERO calls to `getEndpointCategories`, suggesting clients cannot discover or use this method.

---

## 🎯 Root Cause Analysis

### Hypothesis 1: Missing @mcp.tool() Decorator ⭐ MOST LIKELY

The FastMCP framework requires methods to be decorated with `@mcp.tool()` to be exposed as MCP tools.

**Suspect Code in `src/swagger_mcp_server/server/mcp_server_v2.py`:**

```python
# ✅ Correctly registered tools:

@mcp.tool()
async def searchEndpoints(query: str, method: Optional[str] = None, limit: int = 10):
    """Search API endpoints..."""
    # Implementation

@mcp.tool()
async def getSchema(schema_name: str, include_examples: bool = True):
    """Get detailed schema definition..."""
    # Implementation

@mcp.tool()
async def getExample(endpoint_id: str, language: str = "curl"):
    """Generate code examples..."""
    # Implementation

# ❌ Possibly missing decorator:

async def getEndpointCategories():  # Missing @mcp.tool() ?
    """Get list of endpoint categories..."""
    # Implementation
```

### Hypothesis 2: Method Exists But Not in Server Scope

The method might be implemented in a different module/class but not properly imported or registered in the main server instance.

**Check:**
- Is `getEndpointCategories` defined in a helper module?
- Is it a class method not bound to the MCP server instance?

### Hypothesis 3: Conditional Registration Issue

The method might be registered conditionally based on configuration or feature flags that are disabled.

**Check:**
```python
if config.enable_categories:  # ❌ Maybe this is False?
    @mcp.tool()
    async def getEndpointCategories():
        ...
```

---

## 📂 Investigation Checklist

### Files to Examine:

1. **`src/swagger_mcp_server/server/mcp_server_v2.py`**
   - Search for `getEndpointCategories` function definition
   - Verify `@mcp.tool()` decorator is present
   - Check if method is inside correct scope

2. **`generated-mcp-servers/ozon-mcp-server/server.py`**
   - Check if generated server includes the method
   - Verify server.py is in sync with source templates

3. **`src/tests/unit/test_server/test_mcp_get_endpoint_categories.py`**
   - Check if tests exist for this method
   - Review test setup for registration patterns

4. **FastMCP Documentation:**
   - Verify correct decorator usage
   - Check if there are any registration requirements we're missing

---

## 🔧 Required Code Changes

### Expected Implementation Pattern:

```python
from mcp.server.fastmcp import FastMCP
from typing import Optional

mcp = FastMCP("swagger-mcp-server")

# ✅ Correct registration pattern:

@mcp.tool()
async def getEndpointCategories(
    include_counts: bool = True,
    include_methods: bool = True
) -> list[dict]:
    """
    Get list of all endpoint categories with metadata.

    Args:
        include_counts: Include endpoint count per category
        include_methods: Include HTTP methods per category

    Returns:
        List of category objects with name, count, methods, etc.
    """
    try:
        db_manager = get_database_manager()
        categories = db_manager.get_endpoint_categories()

        result = []
        for category in categories:
            cat_dict = {
                "name": category.category_name,
                "display_name": category.display_name or category.category_name
            }

            if include_counts:
                cat_dict["count"] = category.endpoint_count

            if include_methods:
                cat_dict["methods"] = category.http_methods or []

            result.append(cat_dict)

        return result

    except Exception as e:
        logger.error(f"Error retrieving categories: {e}")
        return []
```

### Expected MCP Schema:

```json
{
  "name": "getEndpointCategories",
  "description": "Get list of all endpoint categories with metadata.\n\nArgs:\n    include_counts: Include endpoint count per category\n    include_methods: Include HTTP methods per category\n\nReturns:\n    List of category objects with name, count, methods, etc.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "include_counts": {
        "type": "boolean",
        "default": true,
        "title": "Include Counts"
      },
      "include_methods": {
        "type": "boolean",
        "default": true,
        "title": "Include Methods"
      }
    },
    "title": "getEndpointCategoriesArguments"
  }
}
```

---

## 📊 Impact Assessment

### Current Impact:

1. **Epic 6.2 Completely Blocked:**
   - ❌ Method implemented but not accessible
   - ❌ Users cannot discover categories
   - ❌ Progressive disclosure workflow broken

2. **User Experience:**
   - ❌ No category navigation in MCP clients
   - ❌ Cannot explore API structure
   - ❌ Missing metadata for large APIs

3. **Documentation:**
   - ⚠️ Story 6.2 marked "Complete" but feature not working
   - ⚠️ Tests may be passing but integration broken

### Cascading Effects:

- Issue #002 (Empty categories table) makes this method useless even if registered
- Epic 6.3 (category filtering) depends on this for discovery

---

## ✅ Acceptance Criteria

1. `getEndpointCategories` appears in MCP tools list on server initialization
2. Method is callable via MCP protocol
3. Method returns expected schema format
4. Integration tests verify tool registration
5. Generated servers include the method automatically
6. Claude Desktop can discover and call the method

---

## 🧪 Test Cases

### Registration Tests:

```python
def test_get_endpoint_categories_registered():
    """Verify method is registered as MCP tool"""
    mcp_server = create_mcp_server()
    tools = mcp_server.list_tools()

    tool_names = [t["name"] for t in tools]
    assert "getEndpointCategories" in tool_names

def test_get_endpoint_categories_schema():
    """Verify method has correct MCP schema"""
    tools = mcp_server.list_tools()
    get_cats = next(t for t in tools if t["name"] == "getEndpointCategories")

    assert "description" in get_cats
    assert "inputSchema" in get_cats
    assert get_cats["inputSchema"]["type"] == "object"
```

### Integration Tests:

```python
async def test_get_endpoint_categories_callable():
    """Verify method can be called via MCP"""
    result = await mcp_server.call_tool("getEndpointCategories", {
        "include_counts": True,
        "include_methods": True
    })

    assert isinstance(result, list)
    assert len(result) > 0
    assert "name" in result[0]
    assert "count" in result[0]
```

### MCP Client Tests:

```python
async def test_claude_desktop_can_call():
    """Verify Claude Desktop can discover and call method"""
    # Simulate Claude Desktop initialization
    client = MCPClient()
    await client.initialize()

    tools = await client.list_tools()
    assert "getEndpointCategories" in [t.name for t in tools]

    # Call the method
    categories = await client.call_tool("getEndpointCategories")
    assert len(categories) > 0
```

---

## 📝 Related Files

**Core Implementation:**
- `src/swagger_mcp_server/server/mcp_server_v2.py` - Main server with tool registration
- `generated-mcp-servers/ozon-mcp-server/server.py` - Generated server instance

**Tests:**
- `src/tests/unit/test_server/test_mcp_get_endpoint_categories.py` - Unit tests
- `src/tests/integration/test_mcp_endpoint_categories_workflow.py` - Integration tests

**Documentation:**
- `docs/stories/6.2.get-endpoint-categories-mcp-method.md` - Story definition
- `docs/qa/gates/6.2-get-endpoint-categories-mcp-method.yml` - QA gates

---

## 🔗 Dependencies

**Depends On:**
- Issue #002: endpoint_categories table must be populated for this to return data

**Blocks:**
- Epic 6.2: Complete feature delivery
- Progressive disclosure workflow
- Category-based API navigation

---

## 📅 Recommendations

**Priority:** High - Implemented feature not accessible
**Effort:** 1-2 hours (add decorator + verify + regenerate server)
**Risk:** Low - Simple registration fix

### Fix Approach:

1. **Phase 1: Locate Method (15 min)**
   - Search for `getEndpointCategories` in codebase
   - Verify implementation exists

2. **Phase 2: Add Decorator (15 min)**
   - Add `@mcp.tool()` decorator
   - Verify FastMCP registration pattern
   - Check method signature and docstring

3. **Phase 3: Regenerate Server (15 min)**
   - Regenerate Ozon MCP server
   - Verify method appears in tools list
   - Test with Claude Desktop

4. **Phase 4: Testing (30 min)**
   - Run unit tests
   - Run integration tests
   - Manual testing with MCP client

### Next Steps for PO:

1. Create bug fix story (link to Epic 6.2)
2. Update Epic 6.2 status to "In Progress" (was incorrectly marked complete)
3. Add acceptance test for tool registration to DoD

### Next Steps for QA:

1. Update test plan to include tool registration verification
2. Create MCP client integration test
3. Test with real Claude Desktop instance
4. Verify all 4 tools appear in tools list after fix
