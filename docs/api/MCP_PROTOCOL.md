# MCP Protocol Integration

> Complete guide to integrating with swagger-mcp-server using the Model Context Protocol

The swagger-mcp-server implements the Model Context Protocol (MCP) to enable AI agents to intelligently query API documentation. This guide covers all available methods, parameters, and integration patterns.

## Protocol Overview

### Connection Details
- **Protocol**: JSON-RPC 2.0 over HTTP
- **Content-Type**: `application/json`
- **Default Endpoint**: `http://localhost:8080`
- **Methods**: `searchEndpoints`, `getSchema`, `getExample`

### Request Format
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "methodName",
  "params": {
    "parameter": "value"
  }
}
```

### Response Format
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "data": "response_data"
  }
}
```

---

## Available Methods

### `searchEndpoints`

Search for API endpoints using keywords, HTTP methods, tags, and other filters.

#### Request Parameters

| Parameter | Type | Required | Description | Default |
|-----------|------|----------|-------------|---------|
| `keywords` | string | Yes | Search keywords (space-separated) | - |
| `httpMethods` | array[string] | No | Filter by HTTP methods | All methods |
| `tags` | array[string] | No | Filter by OpenAPI tags | All tags |
| `deprecated` | boolean | No | Include deprecated endpoints | true |
| `maxResults` | integer | No | Maximum results to return (1-1000) | 50 |
| `offset` | integer | No | Pagination offset | 0 |
| `includeExamples` | boolean | No | Include request/response examples | false |
| `sortBy` | string | No | Sort order: `relevance`, `path`, `method` | `relevance` |

#### Example Request
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "searchEndpoints",
  "params": {
    "keywords": "user authentication login",
    "httpMethods": ["POST"],
    "deprecated": false,
    "maxResults": 10,
    "includeExamples": true
  }
}
```

#### Response Structure
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "endpoints": [
      {
        "endpoint_id": "authenticateUser",
        "path": "/auth/login",
        "method": "POST",
        "summary": "Authenticate user with credentials",
        "description": "Validates user credentials and returns access token",
        "tags": ["authentication", "security"],
        "deprecated": false,
        "score": 0.95,
        "parameters": [
          {
            "name": "email",
            "in": "body",
            "required": true,
            "type": "string",
            "description": "User email address"
          },
          {
            "name": "password",
            "in": "body",
            "required": true,
            "type": "string",
            "description": "User password"
          }
        ],
        "responses": {
          "200": {
            "description": "Authentication successful",
            "schema": {
              "$ref": "#/components/schemas/AuthResponse"
            }
          },
          "401": {
            "description": "Invalid credentials"
          }
        },
        "security": [
          {
            "apiKey": []
          }
        ],
        "examples": {
          "request": {
            "email": "user@example.com",
            "password": "securePassword123"
          },
          "response": {
            "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
            "token_type": "Bearer",
            "expires_in": 3600
          }
        }
      }
    ],
    "total": 3,
    "offset": 0,
    "hasMore": false,
    "searchTime": 0.023,
    "filters": {
      "httpMethods": ["POST"],
      "deprecated": false
    }
  }
}
```

#### Search Tips

**Keyword Strategies:**
- Use specific terms: `"user authentication"` vs `"auth"`
- Combine concepts: `"payment credit card validation"`
- Include HTTP verbs: `"create user POST"`
- Use domain terms: `"inventory stock quantity"`

**Advanced Filtering:**
```json
{
  "keywords": "order payment",
  "httpMethods": ["POST", "PUT"],
  "tags": ["orders", "payments"],
  "deprecated": false,
  "maxResults": 20
}
```

---

### `getSchema`

Retrieve detailed schema information for OpenAPI components.

#### Request Parameters

| Parameter | Type | Required | Description | Default |
|-----------|------|----------|-------------|---------|
| `componentName` | string | Yes | Schema component name | - |
| `includeExamples` | boolean | No | Include example values | true |
| `maxDepth` | integer | No | Maximum reference depth (1-10) | 5 |
| `format` | string | No | Response format: `json`, `yaml` | `json` |

#### Example Request
```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "getSchema",
  "params": {
    "componentName": "User",
    "includeExamples": true,
    "maxDepth": 3
  }
}
```

#### Response Structure
```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "result": {
    "componentName": "User",
    "schema": {
      "type": "object",
      "required": ["id", "email", "name"],
      "properties": {
        "id": {
          "type": "integer",
          "format": "int64",
          "description": "Unique user identifier",
          "example": 12345
        },
        "email": {
          "type": "string",
          "format": "email",
          "description": "User email address",
          "example": "user@example.com"
        },
        "name": {
          "type": "string",
          "minLength": 1,
          "maxLength": 100,
          "description": "User full name",
          "example": "John Doe"
        },
        "profile": {
          "$ref": "#/components/schemas/UserProfile"
        },
        "createdAt": {
          "type": "string",
          "format": "date-time",
          "description": "Account creation timestamp",
          "example": "2023-01-15T10:30:00Z"
        },
        "isActive": {
          "type": "boolean",
          "description": "Account active status",
          "example": true
        }
      }
    },
    "referencedSchemas": {
      "UserProfile": {
        "type": "object",
        "properties": {
          "avatar": {
            "type": "string",
            "format": "uri",
            "example": "https://api.example.com/avatars/user123.jpg"
          },
          "bio": {
            "type": "string",
            "maxLength": 500,
            "example": "Software developer and API enthusiast"
          }
        }
      }
    },
    "usedBy": [
      {
        "endpoint": "/users/{id}",
        "method": "GET",
        "context": "response"
      },
      {
        "endpoint": "/users",
        "method": "POST",
        "context": "request"
      }
    ],
    "validationRules": {
      "required": ["id", "email", "name"],
      "emailValidation": true,
      "lengthConstraints": {
        "name": {"min": 1, "max": 100},
        "bio": {"max": 500}
      }
    }
  }
}
```

#### Schema Component Types

The system recognizes these component types:
- **Schemas**: Data models and objects
- **Parameters**: Reusable parameter definitions
- **Headers**: Reusable header definitions
- **RequestBodies**: Reusable request body definitions
- **Responses**: Reusable response definitions
- **SecuritySchemes**: Authentication schemes

---

### `getExample`

Generate practical code examples for API endpoints.

#### Request Parameters

| Parameter | Type | Required | Description | Default |
|-----------|------|----------|-------------|---------|
| `endpointId` | string | Yes | Endpoint identifier from search results | - |
| `language` | string | No | Programming language/tool | `curl` |
| `includeAuth` | boolean | No | Include authentication in examples | true |
| `style` | string | No | Example style: `minimal`, `complete`, `production` | `complete` |

#### Supported Languages

| Language | Description | Features |
|----------|-------------|----------|
| `curl` | cURL command-line tool | Headers, authentication, request body |
| `javascript` | JavaScript/Node.js | Fetch API, async/await, error handling |
| `python` | Python requests library | Session handling, error handling |
| `java` | Java with OkHttp | Builder pattern, type safety |
| `go` | Go with net/http | Struct definitions, error handling |
| `php` | PHP with cURL | Array handling, JSON encoding |
| `ruby` | Ruby with Net::HTTP | Hash handling, response parsing |
| `csharp` | C# with HttpClient | Async/await, strong typing |

#### Example Request
```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "method": "getExample",
  "params": {
    "endpointId": "createUser",
    "language": "javascript",
    "style": "production",
    "includeAuth": true
  }
}
```

#### Response Structure
```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "result": {
    "endpointId": "createUser",
    "language": "javascript",
    "style": "production",
    "examples": {
      "request": {
        "code": "const axios = require('axios');\n\nasync function createUser(userData) {\n  try {\n    const response = await axios.post('https://api.example.com/users', {\n      name: userData.name,\n      email: userData.email,\n      profile: {\n        bio: userData.bio\n      }\n    }, {\n      headers: {\n        'Authorization': `Bearer ${process.env.API_TOKEN}`,\n        'Content-Type': 'application/json'\n      },\n      timeout: 10000\n    });\n    \n    return response.data;\n  } catch (error) {\n    if (error.response) {\n      console.error('API Error:', error.response.data);\n      throw new Error(`User creation failed: ${error.response.status}`);\n    } else {\n      console.error('Network Error:', error.message);\n      throw new Error('Failed to connect to API');\n    }\n  }\n}\n\n// Usage example\nconst newUser = {\n  name: 'John Doe',\n  email: 'john@example.com',\n  bio: 'Software developer'\n};\n\ncreateUser(newUser)\n  .then(user => console.log('User created:', user))\n  .catch(error => console.error('Error:', error.message));",
        "description": "Production-ready JavaScript function with error handling and timeout"
      },
      "response": {
        "code": "{\n  \"id\": 12345,\n  \"name\": \"John Doe\",\n  \"email\": \"john@example.com\",\n  \"profile\": {\n    \"bio\": \"Software developer\",\n    \"avatar\": null\n  },\n  \"createdAt\": \"2023-01-15T10:30:00Z\",\n  \"isActive\": true\n}",
        "description": "Example successful response with created user data"
      }
    },
    "metadata": {
      "endpoint": {
        "path": "/users",
        "method": "POST",
        "summary": "Create a new user account"
      },
      "authentication": {
        "type": "Bearer Token",
        "header": "Authorization",
        "example": "Bearer your_api_token_here"
      },
      "dependencies": {
        "javascript": ["axios", "dotenv"]
      },
      "notes": [
        "Store API tokens in environment variables",
        "Implement proper error handling for production use",
        "Consider rate limiting and retry logic"
      ]
    }
  }
}
```

---

## Error Handling

### Error Response Format
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "error": {
    "code": -32000,
    "message": "Invalid search parameters",
    "data": {
      "details": "Keywords parameter is required",
      "field": "keywords",
      "provided": null
    }
  }
}
```

### Error Codes

| Code | Message | Description |
|------|---------|-------------|
| -32700 | Parse error | Invalid JSON in request |
| -32600 | Invalid Request | Invalid JSON-RPC format |
| -32601 | Method not found | Unknown method name |
| -32602 | Invalid params | Invalid method parameters |
| -32603 | Internal error | Server internal error |
| -32000 | Server error | Application-specific error |

### Common Errors

#### Invalid Keywords Parameter
```json
{
  "error": {
    "code": -32000,
    "message": "Keywords parameter is required and must not be empty",
    "data": {"field": "keywords"}
  }
}
```

#### Component Not Found
```json
{
  "error": {
    "code": -32000,
    "message": "Schema component not found: 'NonExistentModel'",
    "data": {"componentName": "NonExistentModel"}
  }
}
```

#### Language Not Supported
```json
{
  "error": {
    "code": -32000,
    "message": "Language 'pascal' is not supported",
    "data": {
      "language": "pascal",
      "supportedLanguages": ["curl", "javascript", "python", "java", "go"]
    }
  }
}
```

---

## Integration Examples

### JavaScript/Node.js Client

```javascript
class SwaggerMCPClient {
  constructor(baseUrl = 'http://localhost:8080') {
    this.baseUrl = baseUrl;
    this.requestId = 1;
  }

  async request(method, params = {}) {
    const response = await fetch(this.baseUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        jsonrpc: '2.0',
        id: this.requestId++,
        method,
        params
      })
    });

    const result = await response.json();

    if (result.error) {
      throw new Error(`MCP Error: ${result.error.message}`);
    }

    return result.result;
  }

  async searchEndpoints(keywords, options = {}) {
    return this.request('searchEndpoints', {
      keywords,
      ...options
    });
  }

  async getSchema(componentName, options = {}) {
    return this.request('getSchema', {
      componentName,
      ...options
    });
  }

  async getExample(endpointId, language = 'curl', options = {}) {
    return this.request('getExample', {
      endpointId,
      language,
      ...options
    });
  }
}

// Usage
const client = new SwaggerMCPClient();

// Search for authentication endpoints
const authEndpoints = await client.searchEndpoints('authentication', {
  httpMethods: ['POST'],
  maxResults: 5
});

// Get user schema
const userSchema = await client.getSchema('User');

// Generate Python example
const pythonExample = await client.getExample('createUser', 'python');
```

### Python Client

```python
import requests
import json

class SwaggerMCPClient:
    def __init__(self, base_url='http://localhost:8080'):
        self.base_url = base_url
        self.request_id = 1
        self.session = requests.Session()
        self.session.headers.update({'Content-Type': 'application/json'})

    def request(self, method, params=None):
        payload = {
            'jsonrpc': '2.0',
            'id': self.request_id,
            'method': method,
            'params': params or {}
        }
        self.request_id += 1

        response = self.session.post(self.base_url, json=payload)
        response.raise_for_status()

        result = response.json()

        if 'error' in result:
            raise Exception(f"MCP Error: {result['error']['message']}")

        return result['result']

    def search_endpoints(self, keywords, **options):
        params = {'keywords': keywords}
        params.update(options)
        return self.request('searchEndpoints', params)

    def get_schema(self, component_name, **options):
        params = {'componentName': component_name}
        params.update(options)
        return self.request('getSchema', params)

    def get_example(self, endpoint_id, language='curl', **options):
        params = {
            'endpointId': endpoint_id,
            'language': language
        }
        params.update(options)
        return self.request('getExample', params)

# Usage
client = SwaggerMCPClient()

# Search for payment endpoints
payments = client.search_endpoints(
    'payment credit card',
    httpMethods=['POST', 'PUT'],
    maxResults=10
)

# Get payment schema
payment_schema = client.get_schema('Payment', includeExamples=True)

# Generate cURL example
curl_example = client.get_example('processPayment', 'curl')
```

### Go Client

```go
package main

import (
    "bytes"
    "encoding/json"
    "fmt"
    "net/http"
)

type MCPClient struct {
    BaseURL   string
    RequestID int
    Client    *http.Client
}

type MCPRequest struct {
    JSONRPC string      `json:"jsonrpc"`
    ID      int         `json:"id"`
    Method  string      `json:"method"`
    Params  interface{} `json:"params"`
}

type MCPResponse struct {
    JSONRPC string          `json:"jsonrpc"`
    ID      int             `json:"id"`
    Result  json.RawMessage `json:"result,omitempty"`
    Error   *MCPError       `json:"error,omitempty"`
}

type MCPError struct {
    Code    int         `json:"code"`
    Message string      `json:"message"`
    Data    interface{} `json:"data,omitempty"`
}

func NewMCPClient(baseURL string) *MCPClient {
    return &MCPClient{
        BaseURL:   baseURL,
        RequestID: 1,
        Client:    &http.Client{},
    }
}

func (c *MCPClient) Request(method string, params interface{}) (json.RawMessage, error) {
    req := MCPRequest{
        JSONRPC: "2.0",
        ID:      c.RequestID,
        Method:  method,
        Params:  params,
    }
    c.RequestID++

    reqBody, err := json.Marshal(req)
    if err != nil {
        return nil, err
    }

    resp, err := c.Client.Post(c.BaseURL, "application/json", bytes.NewBuffer(reqBody))
    if err != nil {
        return nil, err
    }
    defer resp.Body.Close()

    var mcpResp MCPResponse
    if err := json.NewDecoder(resp.Body).Decode(&mcpResp); err != nil {
        return nil, err
    }

    if mcpResp.Error != nil {
        return nil, fmt.Errorf("MCP Error: %s", mcpResp.Error.Message)
    }

    return mcpResp.Result, nil
}

func (c *MCPClient) SearchEndpoints(keywords string, options map[string]interface{}) (json.RawMessage, error) {
    params := map[string]interface{}{
        "keywords": keywords,
    }
    for k, v := range options {
        params[k] = v
    }

    return c.Request("searchEndpoints", params)
}

// Usage
func main() {
    client := NewMCPClient("http://localhost:8080")

    result, err := client.SearchEndpoints("user management", map[string]interface{}{
        "httpMethods": []string{"GET", "POST"},
        "maxResults": 10,
    })

    if err != nil {
        fmt.Printf("Error: %v\n", err)
        return
    }

    fmt.Printf("Result: %s\n", result)
}
```

---

## Best Practices

### Performance Optimization

1. **Use specific keywords**: More specific searches return better results faster
2. **Limit results**: Use `maxResults` to avoid large responses
3. **Cache responses**: Cache schema and example responses client-side
4. **Batch requests**: Group related queries when possible

### Error Handling

```javascript
async function robustSearch(client, keywords, retries = 3) {
  for (let i = 0; i < retries; i++) {
    try {
      return await client.searchEndpoints(keywords);
    } catch (error) {
      if (i === retries - 1) throw error;
      await new Promise(resolve => setTimeout(resolve, 1000 * Math.pow(2, i)));
    }
  }
}
```

### Authentication

```javascript
// If MCP server requires authentication
const client = new SwaggerMCPClient('http://localhost:8080');
client.setAuth('Bearer', 'your-api-token');

// Or with custom headers
client.setHeaders({
  'X-API-Key': 'your-api-key',
  'User-Agent': 'MyApp/1.0'
});
```

### Connection Management

```python
# Use session pooling for multiple requests
with requests.Session() as session:
    client = SwaggerMCPClient(session=session)

    # Multiple requests reuse connection
    endpoints = client.search_endpoints('user')
    schema = client.get_schema('User')
    example = client.get_example('createUser', 'python')
```

---

## Rate Limiting and Quotas

### Default Limits
- **Requests per minute**: 60 (configurable)
- **Concurrent connections**: 10 (configurable)
- **Response size limit**: 10MB (configurable)

### Headers
```
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 45
X-RateLimit-Reset: 1640995200
```

### Handling Rate Limits
```javascript
async function handleRateLimit(requestFn) {
  try {
    return await requestFn();
  } catch (error) {
    if (error.code === 429) {
      const resetTime = new Date(error.headers['X-RateLimit-Reset'] * 1000);
      const waitTime = resetTime - new Date();

      await new Promise(resolve => setTimeout(resolve, waitTime));
      return requestFn();
    }
    throw error;
  }
}
```

This completes the MCP Protocol integration guide. The protocol provides a powerful, flexible way for AI agents to query API documentation intelligently and efficiently.