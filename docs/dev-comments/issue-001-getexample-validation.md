# Issue #001: getExample Validation Error with Integer endpoint_id

**Status:** 🔴 Bug
**Priority:** High
**Severity:** Medium
**Category:** API Validation
**Component:** MCP Server - getExample method
**Detected:** 2025-09-30 21:10:02 UTC
**Environment:** Production MCP Server (ozon-api)

---

## 📋 Problem Description

The `getExample` MCP method throws a Pydantic validation error when users pass `endpoint_id` as an integer instead of a string. This creates poor user experience as the endpoint IDs displayed in `searchEndpoints` results are integers.

### User Experience Issue

When users see results from `searchEndpoints`:
```
1. **GET /api/client/campaign**
   Summary: Список кампаний
   Operation ID: ListCampaigns
   Endpoint ID: 1 (use this with getExample)  👈 Displayed as integer
```

They naturally try to use the integer value:
```json
{"method":"tools/call","params":{"name":"getExample","arguments":{"endpoint_id":1,"language":"python"}}}
```

But receive a validation error:
```
Error executing tool getExample: 1 validation error for getExampleArguments
endpoint_id
  Input should be a valid string [type=string_type, input_value=1, input_type=int]
```

---

## 🔍 Evidence from Logs

**Log File:** `/Users/r2d2/Library/Logs/Claude/mcp-server-ozon-api.log`

**Request at 21:10:02:**
```json
{
  "method": "tools/call",
  "params": {
    "name": "getExample",
    "arguments": {
      "endpoint_id": 1,
      "language": "python"
    }
  },
  "jsonrpc": "2.0",
  "id": 32
}
```

**Error Response:**
```json
{
  "jsonrpc": "2.0",
  "id": 32,
  "result": {
    "content": [{
      "type": "text",
      "text": "Error executing tool getExample: 1 validation error for getExampleArguments\nendpoint_id\n  Input should be a valid string [type=string_type, input_value=1, input_type=int]\n    For further information visit https://errors.pydantic.dev/2.11/v/string_type"
    }],
    "isError": true
  }
}
```

---

## 🎯 Root Cause

**File:** `src/swagger_mcp_server/server/mcp_server_v2.py`

The Pydantic model for `getExample` currently enforces strict string typing:

```python
class getExampleArguments(BaseModel):
    endpoint_id: str  # ❌ Only accepts strings
    language: str = "curl"
```

The MCP schema declares `endpoint_id` as string type:
```python
@mcp.tool()
async def getExample(endpoint_id: str, language: str = "curl"):
    """Generate code examples for API endpoints.

    Args:
        endpoint_id: Endpoint ID (integer) or path (e.g., '/api/client/campaign')
        language: Programming language for the example (curl, javascript, python, typescript)
    """
```

**Mismatch:** The docstring says "Endpoint ID (integer) or path" but type annotation only accepts `str`.

---

## ✅ Expected Behavior

The `getExample` method should accept:
- ✅ Integer endpoint IDs: `1`, `2`, `10`
- ✅ String endpoint IDs: `"1"`, `"2"`, `"10"`
- ✅ Path-based IDs: `"/api/client/campaign"`, `"/api/client/statistics"`

All three formats should work seamlessly.

---

## 🔧 Proposed Solution

### Option 1: Union Type with Automatic Conversion (Recommended)

```python
from typing import Union

class getExampleArguments(BaseModel):
    endpoint_id: Union[str, int]  # Accept both types
    language: str = "curl"

    @validator('endpoint_id')
    def convert_to_string(cls, v):
        return str(v)
```

### Option 2: Pydantic Field with Coercion

```python
from pydantic import Field

class getExampleArguments(BaseModel):
    endpoint_id: str = Field(..., description="Endpoint ID or path")
    language: str = "curl"

    class Config:
        smart_union = True
```

---

## 📊 Impact Assessment

**Affected Users:** All MCP clients using integer endpoint IDs
**Frequency:** ~3% of getExample calls (1 out of 33 in logs)
**Workaround:** Users must manually convert to string: `"1"` instead of `1`

**User Impact:**
- ❌ Confusing error message
- ❌ Breaks natural usage pattern
- ❌ Inconsistent with searchEndpoints display format

---

## ✅ Acceptance Criteria

1. `getExample` accepts integer endpoint_id without error
2. `getExample` accepts string endpoint_id (existing behavior)
3. `getExample` accepts path-based endpoint_id (existing behavior)
4. All three formats return identical results
5. No breaking changes to existing functionality
6. Updated tests cover all three input formats

---

## 🧪 Test Cases

```python
# Test Case 1: Integer endpoint_id
getExample(endpoint_id=1, language="python")
# Expected: ✅ Success

# Test Case 2: String endpoint_id
getExample(endpoint_id="1", language="python")
# Expected: ✅ Success

# Test Case 3: Path endpoint_id
getExample(endpoint_id="/api/client/campaign", language="python")
# Expected: ✅ Success

# Test Case 4: All formats return same result
result1 = getExample(endpoint_id=1, language="curl")
result2 = getExample(endpoint_id="1", language="curl")
assert result1 == result2
# Expected: ✅ Pass
```

---

## 📝 Related Files

- `src/swagger_mcp_server/server/mcp_server_v2.py` - Main server implementation
- `src/tests/unit/test_server/test_mcp_get_example.py` - Unit tests (needs update)
- `generated-mcp-servers/ozon-mcp-server/server.py` - Generated server (auto-regenerates)

---

## 🔗 Dependencies

**None** - This is an isolated validation fix

---

## 📅 Recommendations

**Priority:** High - Poor UX, easy fix
**Effort:** 1-2 hours (code + tests + validation)
**Risk:** Low - Backward compatible change

**Next Steps for PO:**
1. Create story for validation fix
2. Include in next sprint
3. Add regression tests for all input formats

**Next Steps for QA:**
1. Prepare test scenarios for all endpoint_id formats
2. Verify backward compatibility
3. Test with real MCP clients (Claude Desktop)
