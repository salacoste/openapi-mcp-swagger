# Quick Start Guide

> Get your first MCP server running in under 5 minutes

This guide will walk you through converting your first Swagger file to a working MCP server that AI agents can query intelligently.

## Prerequisites

Before you begin, ensure you have:
- **Python 3.9 or higher** ([Download Python](https://python.org/downloads/))
- **pip** (usually included with Python)
- **5 minutes** of your time

You can check your Python version:
```bash
python --version
# or
python3 --version
```

## Step 1: Installation

Install the swagger-mcp-server package using pip:

```bash
pip install swagger-mcp-server
```

> **Note**: If you encounter permission errors, try using `pip install --user swagger-mcp-server` or create a virtual environment first.

Verify the installation:
```bash
swagger-mcp-server --version
```

Expected output:
```
swagger-mcp-server version 1.0.0
```

## Step 2: Get a Sample API

For this tutorial, we'll use a sample e-commerce API. You can either:

### Option A: Download Sample API
```bash
# Download our sample e-commerce API
curl -o sample-ecommerce-api.json https://raw.githubusercontent.com/swagger-api/swagger-petstore/master/src/main/resources/openapi.yaml

# Convert YAML to JSON if needed
python -c "import yaml, json; json.dump(yaml.safe_load(open('sample-ecommerce-api.json')), open('sample-api.json', 'w'), indent=2)"
```

### Option B: Use the Built-in Example
```bash
# Generate a sample API for testing
swagger-mcp-server examples create-sample --type ecommerce --output sample-api.json
```

### Option C: Use Your Own API
If you have your own Swagger/OpenAPI JSON file, you can use that instead. Just replace `sample-api.json` with your file path in the following steps.

## Step 3: Convert to MCP Server

Convert the Swagger file to a working MCP server:

```bash
swagger-mcp-server convert sample-api.json --name ecommerce-server
```

You should see progress output similar to:
```
📋 Validating input file...
✅ Validating input file completed (0.2s)

📋 Parsing Swagger specification...
✅ Parsing Swagger specification completed (1.1s)
  • API Title: Swagger Petstore - OpenAPI 3.0
  • Version: 1.0.11
  • Endpoints found: 19
  • Schemas found: 11

📋 Building search index...
✅ Building search index completed (2.3s)
  • Endpoint entries: 19
  • Schema entries: 11
  • Parameter entries: 47
  • Full-text entries: 156

📋 Generating MCP server...
✅ Generating MCP server completed (0.8s)
  • Server configuration created
  • Database initialized
  • Search index ready

✅ Conversion completed successfully!
   📁 Output directory: ./mcp-server-ecommerce-server
   📊 Endpoints processed: 19
   📊 Schemas indexed: 11
   🚀 Server ready to start

Next steps:
  cd mcp-server-ecommerce-server
  swagger-mcp-server serve
```

## Step 4: Start the MCP Server

Navigate to the generated directory and start the server:

```bash
cd mcp-server-ecommerce-server
swagger-mcp-server serve
```

The server will start and display:
```
🚀 Starting MCP server...
   📍 Host: localhost
   🔌 Port: 8080
   📁 Config: ./config.yaml
   📊 Database: ./mcp_server.db

✅ MCP server ready for connections
   🔗 Endpoint: http://localhost:8080
   📋 Available methods: searchEndpoints, getSchema, getExample
   🤖 AI agents can now query API documentation

   Press Ctrl+C to stop server
```

> **Success!** Your MCP server is now running and ready to serve AI agents.

## Step 5: Test the Server

Let's test the server with some sample queries. Open a new terminal (keep the server running) and try these examples:

### Test 1: Search for Endpoints
```bash
curl -X POST http://localhost:8080 \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "searchEndpoints",
    "params": {
      "keywords": "pet",
      "httpMethods": ["GET", "POST"]
    }
  }'
```

Expected response:
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "endpoints": [
      {
        "endpoint_id": "findPetsByStatus",
        "path": "/pet/findByStatus",
        "method": "GET",
        "summary": "Finds Pets by status",
        "description": "Multiple status values can be provided",
        "score": 0.95
      },
      {
        "endpoint_id": "addPet",
        "path": "/pet",
        "method": "POST",
        "summary": "Add a new pet to the store",
        "score": 0.87
      }
    ],
    "total": 2,
    "search_time_ms": 23
  }
}
```

### Test 2: Get Schema Information
```bash
curl -X POST http://localhost:8080 \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 2,
    "method": "getSchema",
    "params": {
      "componentName": "Pet"
    }
  }'
```

### Test 3: Generate Code Example
```bash
curl -X POST http://localhost:8080 \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 3,
    "method": "getExample",
    "params": {
      "endpointId": "addPet",
      "language": "curl"
    }
  }'
```

## Step 6: Integration with AI Tools

Your MCP server is now ready to work with AI coding assistants! Here are some integration examples:

### VS Code with Continue
Add this to your Continue configuration:
```json
{
  "models": [...],
  "mcpServers": {
    "ecommerce-api": {
      "command": "swagger-mcp-server",
      "args": ["serve"],
      "cwd": "./mcp-server-ecommerce-server"
    }
  }
}
```

### Cursor AI
Configure MCP server in Cursor settings:
```json
{
  "mcp": {
    "servers": {
      "ecommerce": "http://localhost:8080"
    }
  }
}
```

### Custom AI Agent
```python
import requests

def query_api_docs(question):
    response = requests.post('http://localhost:8080', json={
        "jsonrpc": "2.0",
        "id": 1,
        "method": "searchEndpoints",
        "params": {"keywords": question}
    })
    return response.json()

# Example usage
result = query_api_docs("how to create a new user")
print(f"Found {len(result['result']['endpoints'])} relevant endpoints")
```

## Next Steps

Congratulations! You now have a working MCP server. Here's what you can do next:

### 🔧 Customize Configuration
- **Edit settings**: Modify `config.yaml` in your server directory
- **Change port**: Use `swagger-mcp-server serve --port 9000`
- **Add authentication**: Configure API keys and authentication
- **Enable SSL**: Set up HTTPS for production use

### 📚 Learn More
- **[Configuration Guide](BASIC_CONFIG.md)**: Learn about configuration options
- **[CLI Reference](../reference/CLI_REFERENCE.md)**: Explore all available commands
- **[Performance Tuning](PERFORMANCE.md)**: Optimize for your use case
- **[Security Guide](SECURITY.md)**: Secure your server for production

### 🚀 Advanced Usage
- **Multiple APIs**: Convert and manage multiple Swagger files
- **Server Management**: Monitor and control multiple MCP servers
- **Custom Extensions**: Extend functionality with plugins
- **Production Deployment**: Deploy to cloud platforms

### 🆘 Need Help?
- **[Troubleshooting Guide](../troubleshooting/COMMON_ISSUES.md)**: Solutions to common problems
- **[Error Reference](../troubleshooting/ERROR_REFERENCE.md)**: Understanding error messages
- **[Community Support](https://github.com/swagger-mcp-server/swagger-mcp-server/discussions)**: Ask questions and get help

---

## Summary

In this quick start, you:
1. ✅ Installed swagger-mcp-server
2. ✅ Converted a Swagger file to an MCP server
3. ✅ Started the server
4. ✅ Tested the API with sample queries
5. ✅ Learned about AI tool integration

Your MCP server is now ready to help AI agents understand and use your API documentation intelligently!

**What's the magic?** Instead of AI agents struggling with large API docs in their context window, they can now query specific information on-demand, getting exactly what they need when they need it.

Ready to convert your own APIs? Just replace `sample-api.json` with your Swagger file and follow the same steps!