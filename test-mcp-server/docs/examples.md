# Usage Examples for Документация Ozon Performance API MCP Server

This document provides comprehensive examples for using the generated MCP server.

## Connection Examples

### Python MCP Client
```python
import asyncio
from mcp_client import MCPClient

async def main():
    client = MCPClient("http://localhost:8080")
    await client.connect()

    # Search for endpoints
    results = await client.searchEndpoints("user management")
    print(f"Found {len(results['results'])} endpoints")

    # Get schema information
    schema = await client.getSchema("User")
    print(f"User schema: {schema}")

    # Generate code example
    example = await client.getExample("/api/v1/users", "python")
    print(f"Python example:\n{example}")

    await client.disconnect()

asyncio.run(main())
```

### JavaScript/Node.js MCP Client
```javascript
const { MCPClient } = require('mcp-client');

async function main() {
    const client = new MCPClient('http://localhost:8080');
    await client.connect();

    // Search for endpoints
    const results = await client.searchEndpoints('user management');
    console.log(`Found ${results.results.length} endpoints`);

    // Get schema information
    const schema = await client.getSchema('User');
    console.log('User schema:', schema);

    // Generate code example
    const example = await client.getExample('/api/v1/users', 'javascript');
    console.log('JavaScript example:\n', example);

    await client.disconnect();
}

main().catch(console.error);
```

## Search Examples

### Basic Endpoint Search
```python
# Search for user-related functionality
results = await client.searchEndpoints("user profile management")

# Search for authentication endpoints
auth_results = await client.searchEndpoints("login logout authentication")

# Search for file operations
file_results = await client.searchEndpoints("upload download file")
```

### Filtered Search
```python
# Only GET endpoints
get_endpoints = await client.searchEndpoints(
    "user data",
    httpMethods=["GET"]
)

# Only POST and PUT endpoints
modify_endpoints = await client.searchEndpoints(
    "user creation update",
    httpMethods=["POST", "PUT"]
)

# Search by tags
tagged_endpoints = await client.searchEndpoints(
    "user management",
    tags=["users", "admin"]
)
```

### Advanced Search Patterns
```python
# Search for specific functionality
payment_endpoints = await client.searchEndpoints("payment processing checkout")
notification_endpoints = await client.searchEndpoints("notification email sms")
reporting_endpoints = await client.searchEndpoints("reports analytics statistics")

# Search for CRUD operations
crud_examples = [
    await client.searchEndpoints("create new user", ["POST"]),
    await client.searchEndpoints("get user details", ["GET"]),
    await client.searchEndpoints("update user profile", ["PUT", "PATCH"]),
    await client.searchEndpoints("delete user account", ["DELETE"])
]
```

## Schema Examples

### Basic Schema Retrieval
```python
# Get complete schema with all relationships
user_schema = await client.getSchema("User")

# Get schema with limited depth to avoid deep nesting
profile_schema = await client.getSchema("UserProfile", maxDepth=2)

# Get multiple related schemas
schemas = []
for schema_name in ["User", "Address", "ContactInfo"]:
    schema = await client.getSchema(schema_name)
    schemas.append(schema)
```

### Working with Schema Data
```python
# Extract schema properties
user_schema = await client.getSchema("User")
properties = user_schema.get("schema", {}).get("properties", {})

print("User properties:")
for prop_name, prop_def in properties.items():
    prop_type = prop_def.get("type", "unknown")
    required = prop_name in user_schema.get("schema", {}).get("required", [])
    print(f"  {prop_name}: {prop_type} {'(required)' if required else ''}")
```

## Code Generation Examples

### cURL Examples
```python
# GET request example
curl_get = await client.getExample("/api/v1/users/{id}", "curl", "GET")
print(curl_get)
# Output: curl -X GET "http://api.example.com/api/v1/users/123" -H "Accept: application/json"

# POST request example
curl_post = await client.getExample("/api/v1/users", "curl", "POST")
print(curl_post)
# Output: curl -X POST "http://api.example.com/api/v1/users" -H "Content-Type: application/json" -d '{"name": "John Doe", "email": "john@example.com"}'
```

### Python Examples
```python
# Python requests example
python_example = await client.getExample("/api/v1/users", "python", "POST")
print(python_example)
# Output:
# import requests
#
# url = "http://api.example.com/api/v1/users"
# payload = {"name": "John Doe", "email": "john@example.com"}
# response = requests.post(url, json=payload)
# print(response.json())
```

### JavaScript Examples
```python
# JavaScript fetch example
js_example = await client.getExample("/api/v1/users/{id}", "javascript", "GET")
print(js_example)
# Output:
# fetch('http://api.example.com/api/v1/users/123', {
#   method: 'GET',
#   headers: {
#     'Accept': 'application/json'
#   }
# })
# .then(response => response.json())
# .then(data => console.log(data));
```

## Integration Patterns

### AI Agent Integration
```python
class APIAssistant:
    def __init__(self, mcp_client):
        self.client = mcp_client

    async def find_endpoint_for_task(self, task_description):
        """Find the best endpoint for a given task."""
        results = await self.client.searchEndpoints(task_description)

        if results['results']:
            best_match = results['results'][0]  # Highest ranked result

            # Get code example for the endpoint
            example = await self.client.getExample(
                best_match['path'],
                "python",
                best_match['method']
            )

            return {
                'endpoint': best_match,
                'code_example': example,
                'confidence': best_match.get('score', 0)
            }

        return None

# Usage
assistant = APIAssistant(mcp_client)
result = await assistant.find_endpoint_for_task("create a new user account")
```

### Batch Processing
```python
async def process_multiple_queries(client, queries):
    """Process multiple search queries efficiently."""
    tasks = []

    for query in queries:
        task = client.searchEndpoints(query)
        tasks.append(task)

    results = await asyncio.gather(*tasks)

    return dict(zip(queries, results))

# Example usage
queries = [
    "user authentication",
    "file upload",
    "payment processing",
    "email notifications"
]

batch_results = await process_multiple_queries(client, queries)
```

## Error Handling

### Connection Errors
```python
from mcp_client import MCPClient, ConnectionError

async def robust_connection():
    client = MCPClient("http://localhost:8080")

    try:
        await client.connect()
        return client
    except ConnectionError:
        print("Server not running. Please start the MCP server first.")
        return None
    except Exception as e:
        print(f"Unexpected connection error: {e}")
        return None
```

### Query Errors
```python
async def safe_search(client, query):
    try:
        results = await client.searchEndpoints(query)
        return results
    except ValueError as e:
        print(f"Invalid query: {e}")
        return {'results': [], 'error': str(e)}
    except Exception as e:
        print(f"Search error: {e}")
        return {'results': [], 'error': str(e)}
```

## Performance Tips

### Connection Pooling
```python
class MCPPool:
    def __init__(self, server_url, pool_size=5):
        self.server_url = server_url
        self.pool_size = pool_size
        self.clients = []
        self.available = asyncio.Queue()

    async def initialize(self):
        for _ in range(self.pool_size):
            client = MCPClient(self.server_url)
            await client.connect()
            self.clients.append(client)
            await self.available.put(client)

    async def get_client(self):
        return await self.available.get()

    async def return_client(self, client):
        await self.available.put(client)
```

### Caching Results
```python
from functools import lru_cache
import asyncio

class CachedMCPClient:
    def __init__(self, client):
        self.client = client
        self.schema_cache = {}

    async def searchEndpoints(self, query, **kwargs):
        # Searches are dynamic, don't cache
        return await self.client.searchEndpoints(query, **kwargs)

    async def getSchema(self, component_name, max_depth=None):
        cache_key = f"{component_name}:{max_depth}"

        if cache_key not in self.schema_cache:
            result = await self.client.getSchema(component_name, max_depth)
            self.schema_cache[cache_key] = result

        return self.schema_cache[cache_key]
```

This completes the usage examples for your generated MCP server.
