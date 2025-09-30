# Issue #004: Category Filtering Validation and Verification Needed

**Status:** 🟡 Investigation Required
**Priority:** Medium
**Severity:** Low
**Category:** Quality Assurance / Validation
**Component:** MCP Server - searchEndpoints category filter
**Detected:** 2025-09-30 21:23:01 UTC
**Environment:** Production MCP Server (ozon-api)
**Related Epic:** Epic 6.3 - Enhanced Search Endpoints with Category Filter

---

## 📋 Problem Description

The `searchEndpoints` method accepts a `category` parameter (implemented in Epic 6.3), but its behavior needs validation because:

1. The `endpoint_categories` table is empty (Issue #002)
2. Category filtering still appears to work in logs
3. It's unclear if the filtering is using the correct data source
4. Results may be inaccurate or using fallback logic

**This is NOT a confirmed bug** - it's a validation task to ensure category filtering works correctly after Issues #002 and #003 are resolved.

---

## 🔍 Evidence from Logs

**Log File:** `/Users/r2d2/Library/Logs/Claude/mcp-server-ozon-api.log`

### Test 1: Valid Category Filter

**Request at 21:23:01:**
```json
{
  "method": "tools/call",
  "params": {
    "name": "searchEndpoints",
    "arguments": {
      "query": "campaign",
      "category": "statistics",
      "limit": 5
    }
  },
  "id": 34
}
```

**Response:**
```
Found 5 endpoints:
1. GET /api/client/campaign (ListCampaigns)
2. GET /api/client/campaign/{campaignId}/objects
3. POST /api/client/min/sku
4. POST /api/client/statistics/video  👈 Has "statistics" in path
5. GET /api/client/statistics/report  👈 Has "statistics" in path
```

**Observation:** Results include BOTH campaign and statistics endpoints. Is this correct behavior or a bug?

### Test 2: Different Category Filter

**Request at 21:23:08:**
```json
{
  "method": "tools/call",
  "params": {
    "name": "searchEndpoints",
    "arguments": {
      "query": "list",
      "category": "campaigns",
      "limit": 5
    }
  },
  "id": 35
}
```

**Response:**
```
Found 5 endpoints:
1. GET /api/client/campaign
2. GET /api/client/campaign/{campaignId}/objects
3. GET /api/client/limits/list
4. GET /api/client/statistics/list      👈 "statistics" not "campaigns"
5. GET /api/client/statistics/externallist
```

**Observation:** Again mixing categories. Expected only "campaign" category endpoints.

### Test 3: Non-existent Category

**Request at 21:23:53:**
```json
{
  "method": "tools/call",
  "params": {
    "name": "searchEndpoints",
    "arguments": {
      "query": "test",
      "category": "nonexistent",
      "limit": 3
    }
  },
  "id": 38
}
```

**Response:**
```
Found 0 endpoints:
```

**Observation:** ✅ Correctly returns empty for invalid category.

---

## 🎯 Investigation Questions

### Question 1: What is the Current Filtering Logic?

**Possible implementations:**

**Option A: Database Table (Ideal)**
```python
# Filter using endpoint_categories table
SELECT e.* FROM endpoints e
JOIN endpoint_categories ec ON e.category_id = ec.id
WHERE ec.category_name = ?
```

**Option B: Tag-based Fallback (Likely Current)**
```python
# Filter using OpenAPI tags from endpoints table
SELECT * FROM endpoints
WHERE tags LIKE '%category_name%'
```

**Option C: Keyword Matching (Suboptimal)**
```python
# Filter by path or description keywords
SELECT * FROM endpoints
WHERE path LIKE '%category_name%'
   OR description LIKE '%category_name%'
```

### Question 2: Why Mixed Results?

The results show endpoints from multiple categories when filtering by one category. Possible explanations:

1. **Keyword-based filtering:** Searching for "campaign" + "statistics" matches endpoints with either term
2. **Fuzzy matching:** Query term "campaign" partially matches "statistics/campaign" paths
3. **Tag overlap:** Endpoints have multiple tags, causing cross-category matches
4. **Bug in filter logic:** AND vs OR condition error

### Question 3: What Happens After Issue #002 is Fixed?

Once `endpoint_categories` table is populated:
- Will the logic automatically switch to database-based filtering?
- Will it require code changes?
- Will existing behavior change?

---

## 📊 Expected vs Actual Behavior

### Expected Behavior:

**When searching with `category="statistics"`:**
```
✅ POST /api/client/statistics
✅ POST /api/client/statistics/video
✅ GET /api/client/statistics/{UUID}
❌ GET /api/client/campaign           # Different category
❌ POST /api/client/min/sku           # Different category
```

### Actual Behavior:

**Current results mix categories:**
```
✅ POST /api/client/statistics/video
✅ GET /api/client/statistics/report
❌ GET /api/client/campaign           # Should be filtered out?
❌ POST /api/client/min/sku           # Should be filtered out?
```

---

## 🔧 Investigation Tasks

### Phase 1: Code Review

**File:** `src/swagger_mcp_server/server/mcp_server_v2.py`

**Review `searchEndpoints` implementation:**
```python
@mcp.tool()
async def searchEndpoints(
    query: str,
    method: Optional[str] = None,
    category: Optional[str] = None,  # 👈 How is this used?
    limit: int = 10
):
    """Search API endpoints..."""
    # TODO: Find filtering logic
```

**Check for:**
1. How `category` parameter is processed
2. SQL query or search logic
3. Fallback behavior when table is empty
4. AND vs OR logic in filters

### Phase 2: Database Schema Review

**Verify endpoint-category relationship:**
```sql
-- Check if endpoints have category foreign key
.schema endpoints

-- Expected:
-- category_id INTEGER,
-- FOREIGN KEY(category_id) REFERENCES endpoint_categories(id)

-- Check actual relationship
SELECT name, sql FROM sqlite_master WHERE type='table' AND name='endpoints';
```

### Phase 3: Test Different Scenarios

**Test Matrix:**

| Query | Category | Expected Results | Actual Results | Status |
|-------|----------|------------------|----------------|--------|
| "campaign" | "statistics" | Only statistics endpoints | Mixed | ❓ |
| "list" | "campaign" | Only campaign endpoints | Mixed | ❓ |
| "test" | "nonexistent" | Empty | Empty | ✅ |
| "campaign" | null | All matching | ? | ❓ |
| "" | "statistics" | All statistics | ? | ❓ |

### Phase 4: Compare Before/After Issue #002 Fix

1. Document current behavior (table empty)
2. Fix Issue #002 (populate table)
3. Test same scenarios again
4. Document new behavior
5. Ensure no regressions

---

## ✅ Acceptance Criteria

### After Issues #002 and #003 are Fixed:

1. **Exact Category Matching:**
   - `category="statistics"` returns ONLY statistics endpoints
   - No cross-category contamination

2. **Category + Query Combination:**
   - Both filters applied with AND logic
   - `query="campaign" + category="statistics"` returns statistics endpoints matching "campaign"

3. **Invalid Category Handling:**
   - Non-existent categories return empty results
   - Clear error message or empty response

4. **Null Category Behavior:**
   - `category=null` returns all results matching query
   - Same as not specifying category parameter

5. **Performance:**
   - Uses database index for category filtering
   - No full-table scans
   - Response time < 100ms for 1000+ endpoints

---

## 🧪 Test Cases

### Test Suite 1: Category Filter Accuracy

```python
def test_category_filter_exact_match():
    """Only return endpoints in specified category"""
    results = searchEndpoints(query="", category="statistics")

    assert len(results) > 0
    assert all(e.category == "statistics" for e in results)

def test_category_filter_excludes_others():
    """Exclude endpoints from other categories"""
    results = searchEndpoints(query="", category="campaign")

    # Should NOT include statistics endpoints
    paths = [e.path for e in results]
    assert "/api/client/statistics" not in paths
```

### Test Suite 2: Query + Category Combination

```python
def test_query_and_category_both_apply():
    """Both query and category filters should apply"""
    results = searchEndpoints(
        query="campaign",
        category="statistics"
    )

    # Results should:
    # 1. Be in "statistics" category
    # 2. Match "campaign" in path/description
    assert all(e.category == "statistics" for e in results)
    assert all("campaign" in e.path.lower() or
               "campaign" in e.description.lower()
               for e in results)
```

### Test Suite 3: Edge Cases

```python
def test_nonexistent_category():
    """Handle invalid category gracefully"""
    results = searchEndpoints(query="test", category="invalid_cat")
    assert len(results) == 0

def test_null_category():
    """Null category returns all matching results"""
    with_category = searchEndpoints(query="campaign", category="statistics")
    without_category = searchEndpoints(query="campaign", category=None)

    assert len(without_category) >= len(with_category)

def test_empty_query_with_category():
    """Category filter works without query"""
    results = searchEndpoints(query="", category="campaign")

    assert len(results) > 0
    assert all(e.category == "campaign" for e in results)
```

---

## 📝 Related Files

**Implementation:**
- `src/swagger_mcp_server/server/mcp_server_v2.py` - searchEndpoints method
- `src/swagger_mcp_server/storage/database.py` - Database query logic

**Tests:**
- `src/tests/unit/test_server/test_search_endpoints_category_filter.py` - Unit tests
- `src/tests/integration/test_enhanced_search_category_filter.py` - Integration tests

**Documentation:**
- `docs/stories/6.3.enhanced-search-endpoints-category-filter.md` - Story definition
- `docs/qa/gates/6.3-enhanced-search-endpoints-category-filter.yml` - QA gates

---

## 🔗 Dependencies

**Depends On:**
- ⚠️ Issue #002: Must be resolved first to test proper category filtering
- ⚠️ Issue #003: getEndpointCategories needed to verify available categories

**Blocks:**
- None - This is a validation task, not blocking other work

---

## 📅 Recommendations

**Priority:** Medium - Validation after critical bugs fixed
**Effort:** 4-6 hours (investigation + testing + documentation)
**Risk:** Low - Primarily a testing/validation task

### Investigation Approach:

1. **Phase 1: Understand Current State (1-2 hours)**
   - Review searchEndpoints implementation
   - Document current filtering logic
   - Identify data source (table vs tags)

2. **Phase 2: Fix Dependencies (Block on #002, #003)**
   - Wait for endpoint_categories to be populated
   - Wait for getEndpointCategories to be registered

3. **Phase 3: Test and Validate (2-3 hours)**
   - Run comprehensive test matrix
   - Compare before/after behavior
   - Document any changes or bugs

4. **Phase 4: Report Findings (1 hour)**
   - Create detailed test report
   - Update QA gates
   - File new bugs if found

### Next Steps for PO:

1. ⏳ **Wait for Issues #002 and #003** to be resolved
2. Schedule validation sprint after fixes
3. Update Epic 6.3 acceptance criteria if needed

### Next Steps for QA:

1. Prepare comprehensive test scenarios
2. Set up test data with clear category boundaries
3. Create before/after comparison baseline
4. Document expected behavior for each scenario
5. Test with Claude Desktop after all fixes deployed

---

## 🎯 Success Metrics

**After validation, we should have:**

1. ✅ Documented proof that category filtering works correctly
2. ✅ Comprehensive test coverage for all scenarios
3. ✅ Clear understanding of AND vs OR logic
4. ✅ Performance benchmarks for large APIs
5. ✅ Updated QA gates with actual behavior
6. ✅ Confidence to mark Epic 6.3 as "Production Ready"
