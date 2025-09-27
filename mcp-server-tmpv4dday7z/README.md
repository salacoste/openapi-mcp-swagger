# MCP Server for Test

Generated MCP server providing intelligent access to Test API documentation.

## Overview

This MCP server was automatically generated from your Swagger/OpenAPI specification and provides three main capabilities:

- **🔍 Intelligent Endpoint Search**: Find API endpoints by functionality using natural language queries
- **📋 Schema Retrieval**: Get detailed schema definitions with full type information and relationships
- **💻 Code Generation**: Generate working code examples in multiple programming languages

## Quick Start

### Prerequisites
- Python 3.8 or higher
- pip (Python package installer)

### Option 1: Automatic Setup (Recommended)
```bash
# Unix/Linux/macOS
./start.sh

# Windows
start.bat
```

### Option 2: Manual Setup
```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Unix/Linux/macOS:
source venv/bin/activate
# On Windows:
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Start the server
python server.py
```

### Verify Installation
Once started, the server will display:
```
🚀 MCP Server is starting...
📊 API: Test v1.0
🌐 Server URL: http://localhost:8080
📚 Available MCP methods: searchEndpoints, getSchema, getExample
🤖 AI agents can now connect and query API documentation
```

## API Information

- **API Title**: Test
- **Version**: 1.0
- **Total Endpoints**: 0
- **Schema Components**: 0
- **Generated**: 2025-09-28 02:33:55

## MCP Methods

### searchEndpoints
Search for API endpoints using natural language queries.

**Parameters:**
- `keywords` (string): Search terms describing the functionality
- `httpMethods` (optional array): Filter by HTTP methods (GET, POST, etc.)
- `tags` (optional array): Filter by OpenAPI tags

**Example:**
```python
# Search for user-related endpoints
results = await client.searchEndpoints("user management")

# Search for authentication endpoints
results = await client.searchEndpoints("login authentication", ["POST"])
```

### getSchema
Retrieve detailed schema definitions with relationships.

**Parameters:**
- `componentName` (string): Name of the schema component
- `maxDepth` (optional number): Maximum relationship depth (1-10)

**Example:**
```python
# Get user schema with dependencies
schema = await client.getSchema("User")

# Get schema with limited depth
schema = await client.getSchema("UserProfile", maxDepth=2)
```

### getExample
Generate code examples for API endpoints.

**Parameters:**
- `endpoint` (string): API endpoint path
- `format` (string): Output format (curl, python, javascript, etc.)
- `method` (optional string): HTTP method

**Example:**
```python
# Get cURL example
curl_example = await client.getExample("/api/v1/users/{id}", "curl")

# Get Python example
python_example = await client.getExample("/api/v1/users", "python", "POST")
```

## Configuration

Edit `config/server.yaml` to customize server behavior:

```yaml
server:
  host: localhost      # Server host
  port: 8080            # Server port
  name: test

database:
  path: data/mcp_server.db     # SQLite database path
  backup_enabled: true

search:
  index_path: data/search_index  # Search index location
  cache_size: 1000     # Search result cache size
  enable_fuzzy: true   # Enable fuzzy matching

logging:
  level: INFO          # Log level (DEBUG, INFO, WARNING, ERROR)
  format: console      # Log format
```

## Environment Variables

Override configuration with environment variables:

- `MCP_HOST`: Server host (default: localhost)
- `MCP_PORT`: Server port (default: 8080)
- `MCP_DATABASE_PATH`: Database file path

Example:
```bash
export MCP_PORT=9000
python server.py
```

## Deployment

### Local Development
```bash
python server.py
```

### Docker (if Dockerfile is present)
```bash
docker build -t mcp-server-test .
docker run -p 8080:8080 mcp-server-test
```

### Production with systemd (Linux)
```bash
# Copy service file
sudo cp mcp-server.service /etc/systemd/system/

# Enable and start service
sudo systemctl enable mcp-server
sudo systemctl start mcp-server

# Check status
sudo systemctl status mcp-server
```

## Troubleshooting

### Common Issues

**Port already in use:**
```bash
# Check what's using the port
lsof -i :8080

# Use a different port
export MCP_PORT=9000
python server.py
```

**Module import errors:**
```bash
# Ensure dependencies are installed
pip install -r requirements.txt

# Check Python path
python -c "import sys; print(sys.path)"
```

**Database errors:**
```bash
# Remove database to regenerate
rm ./mcp-server-tmpv4dday7z/data/mcp_server.db
python server.py
```

**Search index issues:**
```bash
# Remove search index to regenerate
rm -rf ./mcp-server-tmpv4dday7z/data/search_index
python server.py
```

### Debug Mode
Run with verbose logging:
```bash
python server.py --verbose
```

### Performance Tuning
For high-traffic deployments:
1. Increase search cache size in `config/server.yaml`
2. Enable database connection pooling
3. Use a reverse proxy (nginx, Apache)
4. Monitor with the built-in health endpoints

## File Structure

```
test/
├── server.py              # Main MCP server
├── start.sh              # Unix startup script
├── start.bat             # Windows startup script
├── requirements.txt      # Python dependencies
├── README.md             # This file
├── config/
│   └── server.yaml      # Server configuration
├── data/
│   ├── mcp_server.db    # SQLite database
│   └── search_index/    # Search index files
└── docs/
    └── examples.md      # Usage examples
```

## Support

- **Original Swagger file**: `/var/folders/zn/q3v0th8s0918bl7_p1xmd2l00000gn/T/tmpv4dday7z.json`
- **Generated by**: swagger-mcp-server v<module 'swagger_mcp_server.__version__' from '/Users/r2d2/Documents/Code_Projects/spacechemical-nextjs/bmad-openapi-mcp-server/src/swagger_mcp_server/__version__.py'>
- **Documentation**: https://docs.swagger-mcp-server.com
- **Issues**: https://github.com/swagger-mcp-server/issues

## License

This generated MCP server inherits the license from the original Swagger specification.
