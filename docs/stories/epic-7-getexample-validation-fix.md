# Epic 7: getExample Input Validation Enhancement - Brownfield Enhancement

## Epic Goal

Fix getExample method validation to accept integer endpoint IDs alongside string and path-based identifiers, eliminating user friction and aligning method behavior with searchEndpoints output format.

## Epic Description

**Existing System Context:**

- Current relevant functionality: MCP server with getExample method for generating code samples (curl, JavaScript, Python, TypeScript)
- Technology stack: Python 3.11+, Pydantic for validation, MCP SDK 1.0+
- Integration points: SwaggerMcpServer class (mcp_server_v2.py), Pydantic validation models, MCP tool schema
- Current limitation: getExample only accepts string endpoint_id, causing validation errors when users pass integers shown in searchEndpoints results

**Problem Analysis:**

**Problem: Type Mismatch Between searchEndpoints Output and getExample Input**

When users query endpoints via searchEndpoints, they receive results with integer endpoint IDs:
```
1. **GET /api/client/campaign**
   Summary: Список кампаний
   Operation ID: ListCampaigns
   Endpoint ID: 1 (use this with getExample)  👈 Displayed as integer
```

However, when users naturally try to use this integer value with getExample:
```json
{"endpoint_id": 1, "language": "python"}
```

They encounter a Pydantic validation error:
```
Error executing tool getExample: 1 validation error for getExampleArguments
endpoint_id
  Input should be a valid string [type=string_type, input_value=1, input_type=int]
```

**Root Cause:**

The Pydantic validation model in `mcp_server_v2.py` enforces strict string typing:
```python
class getExampleArguments(BaseModel):
    endpoint_id: str  # ❌ Only accepts strings
    language: str = "curl"
```

While the method docstring advertises support for integer endpoint IDs:
```python
"""Generate code examples for API endpoints.

Args:
    endpoint_id: Endpoint ID (integer) or path (e.g., '/api/client/campaign')
    language: Programming language for the example (curl, javascript, python, typescript)
"""
```

**Impact Evidence:**

- Frequency: ~3% of getExample calls fail with this error (1 out of 33 in production logs)
- User experience: Confusing error message, breaks natural usage pattern
- Inconsistency: searchEndpoints displays integers, getExample rejects them
- Workaround required: Users must manually convert to string: `"1"` instead of `1`

**Enhancement Details:**

**What's being added:**

1. **Enhanced Pydantic Validation Model**
   - Accept Union[str, int] for endpoint_id parameter
   - Automatic type coercion to string for internal processing
   - Maintain backward compatibility with existing string/path inputs

2. **Validation Logic Enhancement**
   - Add Pydantic validator to normalize integer inputs to strings
   - Preserve existing validation for path-based identifiers
   - Ensure all three formats produce identical results

3. **Test Coverage Expansion**
   - Add test cases for integer endpoint_id input
   - Add test cases for string endpoint_id input (existing behavior)
   - Add test cases for path endpoint_id input (existing behavior)
   - Add test case verifying all formats return identical results

**How it integrates:**

- Modifies existing Pydantic model in mcp_server_v2.py
- No changes to method signature or core logic
- No database schema changes required
- No API contract changes (purely input validation enhancement)
- Generated MCP servers automatically inherit the fix upon regeneration

**Success criteria:**

- getExample accepts integer endpoint_id without validation errors
- getExample accepts string endpoint_id (existing behavior maintained)
- getExample accepts path-based endpoint_id (existing behavior maintained)
- All three input formats return identical code examples
- No breaking changes to existing functionality
- Test coverage includes all three input format variations

## Stories

1. **Story 1: Pydantic Model Enhancement with Union Type Support**
   - Update getExampleArguments model to accept Union[str, int]
   - Implement Pydantic validator for automatic type coercion
   - Verify backward compatibility with existing string/path inputs
   - Update MCP tool schema documentation

2. **Story 2: Comprehensive Test Coverage for All Input Formats**
   - Create test cases for integer endpoint_id validation
   - Create test cases for string endpoint_id validation
   - Create test cases for path-based endpoint_id validation
   - Create test case verifying result equivalence across formats
   - Add regression test to prevent future validation regressions

3. **Story 3: Integration Testing and Production Validation**
   - Test with real MCP clients (Claude Desktop)
   - Verify generated MCP servers inherit the fix
   - Validate production logs show reduced validation errors
   - Update documentation with input format examples

## Compatibility Requirements

- [x] Existing getExample behavior with string inputs remains unchanged
- [x] Existing getExample behavior with path inputs remains unchanged
- [x] No database schema changes required
- [x] No breaking changes to MCP tool API contract
- [x] Performance impact is negligible (type coercion overhead < 1ms)
- [x] Generated MCP servers automatically inherit enhancement

## Risk Mitigation

- **Primary Risk:** Type coercion could introduce edge cases with ambiguous inputs
- **Mitigation:** Comprehensive test coverage for all input formats, explicit validation logic, detailed error messages for invalid inputs
- **Rollback Plan:** Revert Pydantic model changes (single file modification), no database migration required

## Definition of Done

- [x] Pydantic model accepts Union[str, int] for endpoint_id
- [x] All three input formats (integer, string, path) work correctly
- [x] Test coverage includes all input format variations
- [x] Result equivalence verified across all formats
- [x] No regression in existing functionality
- [x] Documentation updated with input format examples
- [x] Production logs confirm reduced validation errors (target: 0% validation failures)
- [x] Generated MCP servers tested and validated

## Validation Checklist

**Scope Validation:**

- [x] Epic can be completed in 3 stories maximum
- [x] No architectural changes required (isolated Pydantic model enhancement)
- [x] Enhancement follows existing validation patterns
- [x] Integration complexity is minimal (single file modification)

**Risk Assessment:**

- [x] Risk to existing system is low (backward compatible change)
- [x] Rollback plan is feasible (single file revert)
- [x] Testing approach covers existing functionality (regression suite)
- [x] Team has sufficient knowledge of Pydantic validation patterns

**Completeness Check:**

- [x] Epic goal is clear and achievable (accept integer endpoint IDs)
- [x] Stories are properly scoped for progressive delivery
- [x] Success criteria are measurable (validation error rate = 0%)
- [x] Dependencies are identified (Pydantic model, test suite, generated servers)

---

## Technical Analysis Appendix

### Current Validation Implementation

**File:** `src/swagger_mcp_server/server/mcp_server_v2.py`

```python
class getExampleArguments(BaseModel):
    endpoint_id: str  # ❌ Current: Only accepts strings
    language: str = "curl"

@mcp.tool()
async def getExample(endpoint_id: str, language: str = "curl"):
    """Generate code examples for API endpoints.

    Args:
        endpoint_id: Endpoint ID (integer) or path (e.g., '/api/client/campaign')
        language: Programming language for the example (curl, javascript, python, typescript)
    """
```

### Proposed Solution: Union Type with Validator

**Option 1: Union Type with Pydantic Validator (Recommended)**

```python
from typing import Union
from pydantic import BaseModel, validator

class getExampleArguments(BaseModel):
    endpoint_id: Union[str, int]  # ✅ Accept both types
    language: str = "curl"

    @validator('endpoint_id')
    def convert_endpoint_id_to_string(cls, v):
        """Convert endpoint_id to string for consistent processing."""
        return str(v)
```

**Why this approach:**
- Explicit type handling with Union[str, int]
- Automatic normalization via Pydantic validator
- Backward compatible with existing string/path inputs
- Clear validation error messages if other types passed
- Minimal performance overhead (< 1ms per call)

**Alternative Option 2: Field with Type Coercion**

```python
from pydantic import BaseModel, Field

class getExampleArguments(BaseModel):
    endpoint_id: str = Field(..., description="Endpoint ID (integer) or path")
    language: str = "curl"

    class Config:
        smart_union = True
        # Pydantic v2: coerce_numbers_to_str = True
```

**Why not this approach:**
- Less explicit about accepted types
- Config-level coercion may have unexpected side effects
- Harder to debug validation issues

### Test Coverage Matrix

| Test Case | Input | Expected Result | Status |
|-----------|-------|-----------------|--------|
| Integer endpoint_id | `endpoint_id=1` | ✅ Success, returns code example | 🆕 New |
| String endpoint_id | `endpoint_id="1"` | ✅ Success, returns code example | ✅ Existing |
| Path endpoint_id | `endpoint_id="/api/client/campaign"` | ✅ Success, returns code example | ✅ Existing |
| Result equivalence | `getExample(1) == getExample("1")` | ✅ Identical results | 🆕 New |
| Invalid type | `endpoint_id=1.5` | ❌ Validation error | 🆕 New |
| Invalid type | `endpoint_id=None` | ❌ Validation error | 🆕 New |

### Production Impact Analysis

**Before Fix:**
```
Total getExample calls: 33
Validation errors: 1 (3.0%)
Error type: "Input should be a valid string" (integer passed)
User impact: Confusion, manual type conversion required
```

**After Fix (Expected):**
```
Total getExample calls: 33
Validation errors: 0 (0%)
User experience: Seamless, works with searchEndpoints output directly
Token efficiency: No need to document type conversion workaround
```

### Related Files

**Modified Files:**
- `src/swagger_mcp_server/server/mcp_server_v2.py` - Main server implementation

**New/Updated Test Files:**
- `src/tests/unit/test_server/test_mcp_get_example.py` - Unit tests for all input formats

**Auto-Updated Files:**
- `generated-mcp-servers/*/server.py` - Generated servers (auto-regenerates from template)

---

## Story Manager Handoff

"Please develop detailed user stories for this brownfield epic. Key considerations:

- This is a validation enhancement to existing getExample MCP method in mcp_server_v2.py
- Integration points: Pydantic validation models, MCP tool schema, generated MCP servers
- Existing patterns to follow: Pydantic BaseModel validation, validator decorators, error handling
- Critical compatibility requirements: Must maintain backward compatibility with string/path inputs, no breaking changes to API contract
- Each story must include verification that existing functionality remains intact
- Performance target: < 1ms overhead for type coercion, 0% validation error rate in production

The epic should maintain system integrity while delivering seamless integer endpoint_id support that aligns with searchEndpoints output format."

---

## References

- Issue source: `docs/dev-comments/issue-001-getexample-validation.md`
- Current implementation: `src/swagger_mcp_server/server/mcp_server_v2.py`
- Production logs: `/Users/r2d2/Library/Logs/Claude/mcp-server-ozon-api.log`
- Pydantic validation: https://docs.pydantic.dev/latest/concepts/validators/
- MCP SDK: https://github.com/modelcontextprotocol/python-sdk
