# VS Code + Continue Integration

> Connect swagger-mcp-server with Continue for intelligent API assistance in VS Code

[Continue](https://continue.dev) is an open-source AI coding assistant for VS Code that supports MCP server integration. This guide shows how to connect your swagger-mcp-server instance for intelligent API documentation assistance.

## Prerequisites

- VS Code installed
- Continue extension installed
- swagger-mcp-server running locally
- An API converted to MCP server format

## Installation

### 1. Install Continue Extension

```bash
# Option 1: Install from VS Code marketplace
# Search for "Continue" in VS Code extensions

# Option 2: Install from command line
code --install-extension continue.continue
```

### 2. Start Your MCP Server

```bash
# Convert your API if not already done
swagger-mcp-server convert your-api.json --name my-api

# Start the server
cd mcp-server-my-api
swagger-mcp-server serve --port 8080
```

### 3. Configure Continue

Open Continue configuration by:
1. Press `Ctrl+Shift+P` (Windows/Linux) or `Cmd+Shift+P` (macOS)
2. Type "Continue: Open config.json"
3. Select the command

## Configuration

### Basic Configuration

Add your MCP server to the Continue config:

```json
{
  "models": [
    {
      "title": "GPT-4",
      "provider": "openai",
      "model": "gpt-4",
      "apiKey": "your-openai-api-key"
    }
  ],
  "mcpServers": {
    "my-api": {
      "command": "node",
      "args": ["-e", "
        const http = require('http');
        const url = 'http://localhost:8080';

        process.stdin.on('data', async (data) => {
          try {
            const response = await fetch(url, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: data.toString()
            });
            const result = await response.text();
            process.stdout.write(result);
          } catch (error) {
            process.stdout.write(JSON.stringify({
              jsonrpc: '2.0',
              id: 1,
              error: { code: -32000, message: error.message }
            }));
          }
        });
      "]
    }
  },
  "contextProviders": [
    {
      "name": "mcp",
      "params": {
        "serverName": "my-api"
      }
    }
  ]
}
```

### Advanced Configuration

For production use with authentication and custom settings:

```json
{
  "models": [
    {
      "title": "GPT-4 with API Context",
      "provider": "openai",
      "model": "gpt-4",
      "apiKey": "your-openai-api-key",
      "systemMessage": "You are an expert developer with access to API documentation. Use the MCP server to get accurate, up-to-date information about API endpoints, schemas, and examples."
    }
  ],
  "mcpServers": {
    "production-api": {
      "command": "curl",
      "args": [
        "-X", "POST",
        "-H", "Content-Type: application/json",
        "-H", "X-API-Key: your-mcp-api-key",
        "--data-binary", "@-",
        "https://your-production-mcp-server.com"
      ],
      "env": {
        "MCP_SERVER_URL": "https://your-production-mcp-server.com",
        "MCP_API_KEY": "your-mcp-api-key"
      }
    }
  },
  "contextProviders": [
    {
      "name": "mcp",
      "params": {
        "serverName": "production-api",
        "description": "Production API documentation server"
      }
    },
    {
      "name": "files",
      "params": {}
    }
  ],
  "slashCommands": [
    {
      "name": "api",
      "description": "Search API documentation",
      "run": "mcp:searchEndpoints"
    },
    {
      "name": "schema",
      "description": "Get schema information",
      "run": "mcp:getSchema"
    }
  ]
}
```

## Usage Examples

### 1. Search for API Endpoints

In VS Code chat, you can now ask:

```
@continue Search for user authentication endpoints in our API

# Continue will use MCP to search and respond with:
# - Available authentication endpoints
# - Required parameters
# - Response formats
# - Example code
```

### 2. Generate API Integration Code

```
@continue Generate a JavaScript function to create a new user using our API

# Continue will:
# 1. Search for user creation endpoints
# 2. Get the User schema
# 3. Generate complete JavaScript code with error handling
```

### 3. Understand API Responses

```
@continue What does the User schema look like in our API and how do I handle the response?

# Continue will:
# 1. Retrieve the User schema
# 2. Show all properties and types
# 3. Provide response handling examples
```

### 4. Debug API Integration

```
@continue I'm getting a 400 error when calling POST /users. What could be wrong?

# Continue will:
# 1. Look up the endpoint requirements
# 2. Show required parameters and formats
# 3. Suggest common fixes
```

## Custom Slash Commands

Add API-specific slash commands to your Continue config:

```json
{
  "slashCommands": [
    {
      "name": "find-endpoint",
      "description": "Find API endpoints by keyword",
      "run": "async (input) => {
        const response = await mcp.searchEndpoints({
          keywords: input,
          maxResults: 5
        });
        return `Found ${response.total} endpoints:\n` +
               response.endpoints.map(e =>
                 `• ${e.method} ${e.path} - ${e.summary}`
               ).join('\n');
      }"
    },
    {
      "name": "api-example",
      "description": "Get code example for an endpoint",
      "run": "async (endpointId) => {
        const example = await mcp.getExample({
          endpointId,
          language: 'javascript',
          style: 'production'
        });
        return '```javascript\n' + example.examples.request.code + '\n```';
      }"
    }
  ]
}
```

## Workflow Integration

### Code Generation Workflow

1. **Identify API Need**: Use natural language to describe what you want to do
2. **Endpoint Discovery**: Continue searches the API documentation
3. **Schema Retrieval**: Gets detailed type information
4. **Code Generation**: Creates complete, working code
5. **Error Handling**: Includes proper error handling and validation

### Example Workflow

```typescript
// 1. Ask Continue: "Create a TypeScript service for user management"

// 2. Continue generates:
interface User {
  id: number;
  email: string;
  name: string;
  profile?: UserProfile;
  createdAt: string;
  isActive: boolean;
}

interface UserProfile {
  avatar?: string;
  bio?: string;
}

class UserService {
  private baseUrl = 'https://api.example.com';
  private apiKey = process.env.API_KEY;

  async createUser(userData: Partial<User>): Promise<User> {
    const response = await fetch(`${this.baseUrl}/users`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${this.apiKey}`
      },
      body: JSON.stringify(userData)
    });

    if (!response.ok) {
      throw new Error(`User creation failed: ${response.status}`);
    }

    return response.json();
  }

  async getUser(id: number): Promise<User> {
    const response = await fetch(`${this.baseUrl}/users/${id}`, {
      headers: {
        'Authorization': `Bearer ${this.apiKey}`
      }
    });

    if (!response.ok) {
      if (response.status === 404) {
        throw new Error('User not found');
      }
      throw new Error(`Failed to get user: ${response.status}`);
    }

    return response.json();
  }
}
```

## Best Practices

### 1. Descriptive Queries

Instead of:
```
"Get user data"
```

Use:
```
"Create a function to retrieve user profile data including avatar and bio from our API, with proper error handling for 404 and auth errors"
```

### 2. Context Awareness

Continue remembers previous conversations, so you can:

```
# First query
"Show me all user-related endpoints"

# Follow-up
"Now generate a complete CRUD service for users using TypeScript"

# Another follow-up
"Add input validation and rate limiting to that service"
```

### 3. Iterative Refinement

```
# Initial request
"Generate API client for payments"

# Refinement
"Add retry logic for network failures"

# Further refinement
"Include webhook signature validation"
```

## Troubleshooting

### MCP Server Connection Issues

**Problem**: Continue can't connect to MCP server

**Solution**:
```bash
# Check if MCP server is running
curl http://localhost:8080/health

# Check Continue logs
# VS Code → Output → Continue
```

### Configuration Issues

**Problem**: MCP server not recognized in Continue

**Solution**:
```json
// Ensure correct config structure
{
  "mcpServers": {
    "server-name": {
      "command": "...",
      "args": [...]
    }
  },
  "contextProviders": [
    {
      "name": "mcp",
      "params": {
        "serverName": "server-name"  // Must match mcpServers key
      }
    }
  ]
}
```

### Performance Issues

**Problem**: Slow response times

**Solution**:
```json
// Add caching to MCP server config
{
  "mcpServers": {
    "my-api": {
      "command": "...",
      "env": {
        "CACHE_TTL": "300",  // 5 minute cache
        "MAX_RESULTS": "20"   // Limit results
      }
    }
  }
}
```

## Advanced Features

### Multi-API Integration

```json
{
  "mcpServers": {
    "user-api": {
      "command": "...",
      "args": ["http://localhost:8080"]
    },
    "payment-api": {
      "command": "...",
      "args": ["http://localhost:8081"]
    },
    "notification-api": {
      "command": "...",
      "args": ["http://localhost:8082"]
    }
  },
  "contextProviders": [
    {
      "name": "mcp",
      "params": {
        "serverName": "user-api",
        "description": "User management and authentication"
      }
    },
    {
      "name": "mcp",
      "params": {
        "serverName": "payment-api",
        "description": "Payment processing and billing"
      }
    }
  ]
}
```

### Custom Prompt Templates

```json
{
  "customCommands": [
    {
      "name": "api-integration",
      "prompt": "Using the available API documentation, create a {language} {component} that {action}. Include:\n- Proper error handling\n- Input validation\n- TypeScript types if applicable\n- JSDoc comments\n- Rate limiting consideration\n\nRequirements: {requirements}",
      "description": "Generate API integration code with best practices"
    }
  ]
}
```

### Team Configuration

For team use, store config in project root:

```bash
# Project root
├── .continue/
│   ├── config.json      # Team MCP server config
│   └── models.json      # Team model preferences
├── src/
└── package.json
```

```json
// .continue/config.json
{
  "mcpServers": {
    "project-api": {
      "command": "node",
      "args": ["scripts/mcp-proxy.js"],
      "cwd": "${workspaceFolder}"
    }
  }
}
```

This integration enables powerful API-aware development where Continue can intelligently assist with API integration tasks using your actual API documentation.