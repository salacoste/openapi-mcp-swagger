# 🚀 Universal Swagger → MCP Server Converter

> **Stop wrestling with massive API docs in your AI assistant's context window. Start having intelligent conversations about any API.**

[![CI](https://github.com/salacoste/openapi-mcp-swagger/workflows/CI/badge.svg)](https://github.com/salacoste/openapi-mcp-swagger/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![GitHub stars](https://img.shields.io/github/stars/salacoste/openapi-mcp-swagger?style=social)](https://github.com/salacoste/openapi-mcp-swagger/stargazers)

[![MCP Compatible](https://img.shields.io/badge/MCP-Compatible-blue.svg)](https://modelcontextprotocol.io)
[![Cursor](https://img.shields.io/badge/Cursor-Ready-green.svg)](https://cursor.sh/)
[![Claude](https://img.shields.io/badge/Claude-Integration-orange.svg)](https://claude.ai/)
[![VS Code](https://img.shields.io/badge/VS%20Code-Extension-blue.svg)](https://code.visualstudio.com/)

---

<div align="center">

### ⭐ **Love this project? Give it a star!** ⭐

<a href="https://github.com/salacoste/openapi-mcp-swagger/stargazers">
  <img src="https://img.shields.io/github/stars/salacoste/openapi-mcp-swagger?style=for-the-badge&logo=github&logoColor=white&color=gold" alt="GitHub stars"/>
</a>

**🚀 Help us reach more developers who struggle with API integrations!**  
*Your star makes this project more discoverable and motivates continued development.*

[⭐ **Star this repo**](https://github.com/salacoste/openapi-mcp-swagger/stargazers) | [🍴 **Fork it**](https://github.com/salacoste/openapi-mcp-swagger/fork) | [📢 **Share it**](https://twitter.com/intent/tweet?text=Stop%20wrestling%20with%20massive%20API%20docs!%20Check%20out%20this%20Universal%20Swagger%20→%20MCP%20Server%20Converter%20for%20AI%20assistants&url=https://github.com/salacoste/openapi-mcp-swagger)

</div>

---

## 💡 **The Problem Every Developer Faces**

You're building an integration with a complex API. The Swagger documentation is **2MB+ of JSON**. Your AI assistant can only see tiny fragments at a time. You end up:

- ❌ **Copy-pasting documentation chunks** into chat windows
- ❌ **Missing crucial schema relationships** between endpoints  
- ❌ **Getting outdated or incomplete code examples**
- ❌ **Losing context** when working across multiple API endpoints
- ❌ **Wasting hours** on what should be simple integrations

## ✨ **The Solution: Intelligent API Knowledge for AI**

Transform any Swagger/OpenAPI specification into an intelligent MCP server that gives your AI assistant **superpowers**:

### 🎯 **What Your AI Can Now Do:**

```bash
# Instead of this painful workflow:
"Here's a 500KB Swagger file, please help me integrate..."
# Error: Context window exceeded

# You get this magical experience:
AI: "I need to create a user and get their profile data"
→ Instantly finds relevant endpoints: POST /users, GET /users/{id}
→ Generates complete TypeScript client with proper types
→ Includes error handling and authentication patterns
→ Shows example requests/responses for testing
```

### 🚀 **From 0 to AI-Powered API Integration in 30 Seconds:**

```bash
# 1. Convert any Swagger file to intelligent MCP server
swagger-mcp-server convert your-api.json

# 2. Connect to Cursor, Claude, or VS Code
# Your AI assistant now knows EVERYTHING about your API

# 3. Start building with superhuman API knowledge
"Create a React hook for user authentication with retry logic"
"Generate Python client for the payment endpoints"
"Show me all endpoints that return user data"
```

### 🌟 **Real-World Impact:**

- **⚡ 10x Faster Integration:** From hours to minutes for complex APIs
- **🎯 Perfect Code Generation:** AI understands full API context and relationships  
- **🔍 Instant API Discovery:** Natural language search across any documentation size
- **🛡️ Enterprise Ready:** Works offline, handles massive APIs (10MB+), production deployment
- **🔌 Universal Compatibility:** Cursor, Claude, VS Code, or any MCP-compatible tool

---

**Ready to supercharge your API development workflow?** Jump to [🚀 Quick Start](#-quick-start) and experience the future of AI-assisted API integration.

## 📋 Table of Contents

- [✨ What is swagger-mcp-server?](#-what-is-swagger-mcp-server)
- [🚀 Quick Start](#-quick-start) - Get running in 5 minutes
- [🏗️ Architecture](#️-architecture) - System overview
- [🔍 MCP Server Methods](#-mcp-server-methods) - API reference
- [🔧 CLI Commands](#-cli-commands) - Command reference
- [🤖 AI Tool Integrations](#-ai-tool-integrations) - VS Code, Cursor setup
- [📝 Configuration](#-configuration) - Basic setup
- [💡 Examples](#-examples) - Sample APIs and use cases
- [🔧 Troubleshooting](#-troubleshooting) - Common issues
- [📚 Complete Documentation](#-complete-documentation) - All guides
- [🆘 Getting Help](#-getting-help) - Support resources

## ✨ What is swagger-mcp-server?

swagger-mcp-server bridges the gap between API documentation and AI coding assistants. Instead of AI agents struggling with large API docs in their context window, they can now query specific information on-demand through the Model Context Protocol (MCP).

### Key Benefits
- **🔍 Intelligent Search**: Find relevant endpoints using natural language queries
- **📊 Schema Awareness**: Get complete type information and relationships
- **💻 Code Generation**: Generate working examples in multiple languages
- **⚡ Fast Responses**: Sub-200ms search, optimized for AI agent workflows
- **🔌 Easy Integration**: Works with VS Code, Cursor, and custom AI tools
- **🛡️ Production Ready**: SSL, authentication, monitoring, and deployment guides

### Use Cases
- **API Integration**: Help AI assistants understand and use your APIs correctly
- **Documentation Search**: Quickly find specific endpoints and schemas
- **Code Generation**: Generate accurate API client code and examples
- **API Exploration**: Discover API capabilities through intelligent search
- **Development Workflow**: Integrate API knowledge into your coding environment

## 🚀 Quick Start

### Step 1: Get Your Swagger JSON File

Before converting, you need to obtain the Swagger/OpenAPI JSON specification from any API documentation site:

#### 🔍 **Finding the Swagger JSON (Most Common Method)**

1. **Visit any API documentation website** (e.g., `docs.example.com/api`)
2. **Open Browser DevTools** (`F12` or `Cmd/Ctrl + Shift + I`)
3. **Go to Network tab** and refresh the page
4. **Look for `swagger.json` or similar files** in the network requests
5. **Click on the JSON file** and copy the response
6. **Save it to your project** in the `swagger-openapi-data/` directory:

```bash
# Save the JSON content to the existing swagger-openapi-data directory
# Either copy-paste or download directly:
curl -o swagger-openapi-data/your-api.json "https://api.example.com/swagger.json"

# Or save manually by copying the JSON content and pasting it into:
# swagger-openapi-data/your-api.json
```

#### 📋 **Alternative Methods to Get Swagger JSON**

**Method 2: Direct URL Access**
```bash
# Many APIs expose Swagger at common endpoints:
curl -o swagger-openapi-data/your-api.json "https://api.example.com/swagger.json"
curl -o swagger-openapi-data/your-api.json "https://api.example.com/v1/swagger.json"
curl -o swagger-openapi-data/your-api.json "https://api.example.com/docs/swagger.json"
```

**Method 3: API Documentation Download**
Most API documentation sites have a "Download OpenAPI" or "Export JSON" button.

**Method 4: Use Our Sample API (Already Included)**
```bash
# We already include a sample Ozon Performance API for testing:
ls swagger-openapi-data/swagger.json  # 262KB Ozon API ready to use
```

### Step 2: Installation

```bash
# Option 1: Install from source (recommended)
git clone https://github.com/salacoste/openapi-mcp-swagger.git
cd openapi-mcp-swagger

# Option 2: Install dependencies
pip install -r requirements.txt

# Option 3: Use standalone script (no installation required)
chmod +x scripts/standalone-mcp.py
```

### Step 3: Convert & Start

```bash
# Convert your Swagger file to MCP server
swagger-mcp-server convert swagger-openapi-data/your-api.json --name your-api

# Or use the included sample API
swagger-mcp-server convert swagger-openapi-data/swagger.json --name ozon-api

# Start the MCP server
cd mcp-server-your-api  # or mcp-server-ozon-api
swagger-mcp-server serve

# 4. Test with AI agents or curl
curl -X POST http://localhost:8080 \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"searchEndpoints","params":{"keywords":"user"}}'
```

### Step 4: What Happens Next

🎉 **Congratulations!** Your API is now AI-ready. Here's what you get:

#### 🧠 **Intelligent API Knowledge**
- **Complete endpoint mapping** with search capability
- **Schema relationships** preserved and queryable  
- **Code examples** generated on-demand in multiple languages
- **Context-aware responses** for any API size

#### 🤖 **AI Assistant Integration**
Connect to your favorite AI coding assistant:

**For Cursor IDE:**
```bash
# Add to .cursor-mcp/config.json
{
  "mcpServers": {
    "your-api": {
      "command": "swagger-mcp-server",
      "args": ["serve", "--port", "8080"]
    }
  }
}
```

**For Claude/VS Code:**
```bash
# Server will automatically integrate via MCP protocol
# Just point your AI assistant to: http://localhost:8080
```

#### ✨ **Start Building with AI Superpowers**
Now you can ask your AI assistant:

```
"Create a TypeScript client for the user authentication endpoints"
"Show me all endpoints that handle payment processing"  
"Generate a React hook for real-time order status updates"
"What are the required fields for creating a new product?"
```

> **📖 Complete Quick Start**: Follow our step-by-step [Quick Start Tutorial](docs/guides/QUICKSTART.md) to get your first MCP server running in 5 minutes with sample data.

## 🏗️ Architecture

The system consists of four main components:

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   AI Agent      │◄──►│   MCP Server     │◄──►│  Search Engine  │
│                 │    │                  │    │                 │
│ • Claude        │    │ • JSON-RPC API   │    │ • Endpoint Index│
│ • GPT-4         │    │ • Authentication │    │ • Schema Index  │
│ • Cursor        │    │ • Rate Limiting  │    │ • Full-Text     │
│ • VS Code       │    │ • Monitoring     │    │ • Relationships │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │
                                ▼
                       ┌──────────────────┐
                       │  Swagger Parser  │
                       │                  │
                       │ • Validation     │
                       │ • Schema Extract │
                       │ • Relationship   │
                       │ • Indexing       │
                       └──────────────────┘
```

### Core Components
- **🔍 Parser**: Stream-based JSON parsing for large OpenAPI files (up to 10MB)
- **💾 Storage**: SQLite database with optimized search indexes and relationships
- **🌐 Server**: MCP protocol implementation with JSON-RPC over HTTP
- **🔗 Search**: Intelligent endpoint and schema search with relevance ranking
- **💻 Examples**: Multi-language code generation (cURL, JavaScript, Python, Go)

> **📖 Detailed Architecture**: See [docs/architecture/](docs/architecture/) for complete technical documentation and design decisions.

## 🔧 Development Setup

### Prerequisites

- **Python 3.11 or higher** (tested with Python 3.13.3)
- **Poetry** (recommended for dependency management) or pip
- **pipx** (for Poetry installation)
- **Git**

### System Dependencies

Install system dependencies first:

```bash
# macOS (using Homebrew)
brew install python@3.13 pipx

# Ubuntu/Debian
sudo apt update
sudo apt install python3.11-dev python3.11-venv python3-pip pipx

# Install Poetry
pipx install poetry
```

### Local Development

1. **Clone and setup:**
   ```bash
   git clone https://github.com/salacoste/openapi-mcp-swagger.git
   cd openapi-mcp-swagger
   ```

2. **Setup virtual environment and install dependencies:**

   **Option A: Using Poetry (Recommended):**
   ```bash
   # Install all dependencies including dev dependencies
   poetry install --with dev

   # Activate virtual environment
   poetry shell
   ```

   **Option B: Using pip with virtual environment:**
   ```bash
   # Create virtual environment
   python3 -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate

   # Upgrade pip
   pip install --upgrade pip

   # Install essential dependencies for development
   pip install pytest pytest-asyncio aiosqlite sqlalchemy structlog greenlet

   # Install optional dev dependencies
   pip install black isort flake8 mypy pytest-cov
   ```

3. **Verify installation:**
   ```bash
   # Test import of main modules
   python -c "
   import sys; sys.path.append('src')
   from swagger_mcp_server.storage.migrations import Migration
   print('✅ Installation successful!')
   "
   ```

4. **Run tests:**
   ```bash
   # With Poetry
   poetry run pytest src/tests/unit/test_storage/ -v

   # With pip/venv (make sure .venv is activated)
   PYTHONPATH=src python -m pytest src/tests/unit/test_storage/ -v

   # Run performance tests
   PYTHONPATH=src python -m pytest src/tests/performance/ -v

   # Run with coverage
   pytest --cov=src/swagger_mcp_server --cov-report=html
   ```

5. **Run linting:**
   ```bash
   # Format code
   black src/
   isort src/

   # Check linting
   flake8 src/
   mypy src/swagger_mcp_server/
   ```

## 🧪 Testing

The project uses a comprehensive testing strategy:

- **Unit Tests**: 80%+ coverage requirement, focused on individual components
- **Integration Tests**: Full MCP server workflow testing
- **Performance Tests**: Validation of response time requirements (<200ms search, <500ms schema)
- **Fixtures**: Sample OpenAPI specifications for consistent testing

### Running Tests

```bash
# All tests with coverage
poetry run pytest --cov=swagger_mcp_server --cov-report=html

# Unit tests only
poetry run pytest -m unit

# Integration tests only
poetry run pytest -m integration

# Performance/benchmark tests
poetry run pytest -m performance --benchmark-only
```

## 📁 Project Structure

```
swagger-mcp-server/
├── src/
│   ├── swagger_mcp_server/        # Main package
│   │   ├── parser/                # OpenAPI parsing
│   │   ├── storage/               # Database layer
│   │   ├── server/                # MCP implementation
│   │   ├── config/                # Configuration
│   │   └── examples/              # Code generation
│   └── tests/                     # Test suite
├── scripts/                       # Utility scripts
├── data/                          # Sample data
├── docs/                          # Documentation
├── .github/                       # CI/CD workflows
└── pyproject.toml                 # Project configuration
```

## 🔍 MCP Server Methods

The server implements three core MCP methods:

### `searchEndpoints(keywords, httpMethods)`
Search for API endpoints using keywords and HTTP method filters.

```javascript
// Example usage
const results = await mcpClient.call('searchEndpoints', {
  keywords: ['user', 'authentication'],
  httpMethods: ['GET', 'POST']
});
```

### `getSchema(componentName)`
Retrieve complete schema definitions with dependencies.

```javascript
const schema = await mcpClient.call('getSchema', {
  componentName: 'User'
});
```

### `getExample(endpoint, format)`
Generate working code examples in multiple formats.

```javascript
const example = await mcpClient.call('getExample', {
  endpoint: '/api/users',
  format: 'curl'  // 'curl', 'javascript', 'python'
});
```

> **📖 Complete API Reference**: See [docs/api/MCP_PROTOCOL.md](docs/api/MCP_PROTOCOL.md) for detailed protocol documentation, client libraries, and integration examples.

## 🔧 CLI Commands

Essential commands for everyday use:

```bash
# Convert Swagger to MCP server
swagger-mcp-server convert api.json --name my-api --port 8080

# Start server
swagger-mcp-server serve --config config.yaml

# Check server status
swagger-mcp-server status --all

# Configuration management
swagger-mcp-server config create production --output prod-config.yaml

# Setup and installation
swagger-mcp-server setup --verify
```

> **📖 Complete CLI Reference**: See [docs/reference/CLI_REFERENCE.md](docs/reference/CLI_REFERENCE.md) for all commands, options, and usage examples.

## ⚡ Performance Requirements

- **Search Response**: < 200ms target, < 500ms maximum
- **Schema Retrieval**: < 500ms target, < 1s maximum
- **File Processing**: < 2s for files up to 5MB
- **Memory Usage**: Process 10MB files within 2GB RAM
- **Concurrency**: Support 100+ concurrent AI agent connections

> **📖 Performance Tuning**: See [docs/guides/PERFORMANCE.md](docs/guides/PERFORMANCE.md) for optimization strategies and scaling guidelines.

## 🤖 AI Tool Integrations

swagger-mcp-server works seamlessly with popular AI coding assistants:

### VS Code + Continue
```json
{
  "mcpServers": {
    "my-api": {
      "command": "swagger-mcp-server",
      "args": ["serve", "--config", "config.yaml"]
    }
  }
}
```

### Cursor AI
```json
{
  "mcp": {
    "servers": {
      "api-docs": "http://localhost:8080"
    }
  }
}
```

> **📖 Integration Guides**: See [docs/examples/integrations/](docs/examples/integrations/) for complete setup instructions for VS Code, Cursor, and custom AI agents.

## 📝 Configuration

### Basic Configuration
```yaml
# config.yaml
server:
  host: localhost
  port: 8080

database:
  path: ./mcp_server.db

search:
  index_directory: ./search_index

logging:
  level: INFO
  console: true
```

### Environment-Specific Configs
- **Development**: [docs/examples/configurations/development.yaml](docs/examples/configurations/development.yaml)
- **Production**: [docs/examples/configurations/production.yaml](docs/examples/configurations/production.yaml)

> **📖 Configuration Guide**: See [docs/guides/BASIC_CONFIG.md](docs/guides/BASIC_CONFIG.md) for configuration basics and [docs/reference/CONFIGURATION.md](docs/reference/CONFIGURATION.md) for complete reference.

## 💡 Examples

### Sample APIs
We provide realistic sample APIs for testing:

- **E-commerce Platform** (45 endpoints): [docs/examples/swagger-files/ecommerce-api.json](docs/examples/swagger-files/ecommerce-api.json)
- **Banking API** (67 endpoints): [docs/examples/swagger-files/banking-api.json](docs/examples/swagger-files/banking-api.json)
- **Healthcare API** (52 endpoints): [docs/examples/swagger-files/healthcare-api.json](docs/examples/swagger-files/healthcare-api.json)

### Quick Test
```bash
# Use our sample e-commerce API
swagger-mcp-server examples create-sample --type ecommerce --output sample-api.json
swagger-mcp-server convert sample-api.json --name demo
cd mcp-server-demo && swagger-mcp-server serve
```

> **📖 Examples Catalog**: See [docs/examples/swagger-files/README.md](docs/examples/swagger-files/README.md) for all available sample APIs and use cases.

## 🤝 Contributing

We welcome contributions! Please see our [contribution guidelines](CONTRIBUTING.md) for details.

### Development Workflow

1. Fork the repository
2. Create a feature branch: `git checkout -b feat/my-feature`
3. Make your changes with tests
4. Run the test suite: `pytest`
5. Run linting: `black src/ && flake8 src/`
6. Commit with conventional commits: `git commit -m "feat: add new feature"`
7. Push and create a pull request

### Code Quality Standards

- **Code Coverage**: Minimum 80% (target 85%+)
- **Type Hints**: Required for all public functions
- **Documentation**: Comprehensive docstrings for public APIs
- **Performance**: All changes must meet response time requirements
- **Security**: No credentials in logs, input validation required

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🏷️ Version History

- **v0.1.0**: Initial release with core parsing and MCP server functionality

## 🔧 Troubleshooting

### Common Issues

**Installation Problems**:
```bash
# Python version issues
python --version  # Should be 3.9+

# Permission errors
pip install --user swagger-mcp-server

# Package conflicts
python -m venv venv && source venv/bin/activate
```

**Runtime Issues**:
```bash
# Port already in use
swagger-mcp-server serve --port 9000

# Database locked
swagger-mcp-server stop --all

# Search index corruption
rm -rf search_index/ && swagger-mcp-server serve
```

> **📖 Comprehensive Troubleshooting**: See [docs/troubleshooting/COMMON_ISSUES.md](docs/troubleshooting/COMMON_ISSUES.md) for detailed solutions to installation, configuration, and runtime problems.

## 📚 Complete Documentation

### 🚀 Getting Started
- **[Installation Guide](docs/INSTALLATION.md)** - System requirements, installation methods, verification
- **[Quick Start Tutorial](docs/guides/QUICKSTART.md)** - 5-minute setup with sample API
- **[Basic Configuration](docs/guides/BASIC_CONFIG.md)** - Essential configuration for new users

### 📖 Reference Documentation
- **[CLI Reference](docs/reference/CLI_REFERENCE.md)** - Complete command reference with examples
- **[Configuration Reference](docs/reference/CONFIGURATION.md)** - All configuration options and settings
- **[MCP Protocol API](docs/api/MCP_PROTOCOL.md)** - Protocol documentation and client libraries

### 💡 Examples and Integrations
- **[Sample APIs](docs/examples/swagger-files/README.md)** - Realistic APIs for testing and learning
- **[Configuration Templates](docs/examples/configurations/)** - Environment-specific configurations
- **[AI Tool Integrations](docs/examples/integrations/)** - VS Code, Cursor, and custom integrations

### 🔧 Advanced Topics
- **[Deployment Guide](docs/guides/DEPLOYMENT.md)** - Production deployment and scaling
- **[Performance Tuning](docs/guides/PERFORMANCE.md)** - Optimization and monitoring
- **[Security Configuration](docs/guides/SECURITY.md)** - Hardening and best practices

### 🆘 Support and Troubleshooting
- **[Common Issues](docs/troubleshooting/COMMON_ISSUES.md)** - Frequently encountered problems
- **[Error Reference](docs/troubleshooting/ERROR_REFERENCE.md)** - Error messages and solutions
- **[Diagnostic Tools](docs/troubleshooting/DIAGNOSTICS.md)** - Debugging and analysis tools

### 🛠️ Development
- **[Development Setup](DEVELOPMENT.md)** - Complete development environment setup
- **[Contributing Guide](CONTRIBUTING.md)** - How to contribute to the project
- **[Architecture Documentation](docs/architecture/)** - Technical design and decisions

> **📖 Main Documentation Hub**: See [docs/README.md](docs/README.md) for the complete documentation index with detailed navigation.

## 🆘 Getting Help

### Quick Help
- **🚀 New Users**: Start with [Quick Start Tutorial](docs/guides/QUICKSTART.md)
- **🔧 Problems**: Check [Common Issues](docs/troubleshooting/COMMON_ISSUES.md)
- **⚙️ Configuration**: See [Basic Configuration](docs/guides/BASIC_CONFIG.md)
- **🤖 AI Integration**: Follow [Integration Guides](docs/examples/integrations/)

### Community Support
- **🐛 Issues**: [GitHub Issues](https://github.com/salacoste/openapi-mcp-swagger/issues) for bugs and feature requests
- **💬 Discussions**: [GitHub Discussions](https://github.com/salacoste/openapi-mcp-swagger/discussions) for questions and community support
- **📖 Documentation**: [Complete docs](docs/README.md) with searchable content
- **💡 Examples**: [Working examples](docs/examples/) for common use cases

### Before Reporting Issues
1. ✅ Check [Common Issues](docs/troubleshooting/COMMON_ISSUES.md)
2. ✅ Search [existing issues](https://github.com/salacoste/openapi-mcp-swagger/issues)
3. ✅ Try with [minimal configuration](docs/guides/BASIC_CONFIG.md)
4. ✅ Include system info and logs in your report

---

<div align="center">

## 🌟 **Show Your Support** 🌟

If this project helped solve your API integration challenges, **please consider starring it!**

<a href="https://github.com/salacoste/openapi-mcp-swagger/stargazers">
  <img src="https://img.shields.io/github/stars/salacoste/openapi-mcp-swagger?style=for-the-badge&logo=star&logoColor=white&color=ffd700" alt="Star this repository"/>
</a>

**🎯 Why your star matters:**
- 📈 **Increases visibility** for developers facing similar challenges
- 💪 **Motivates continued development** and new features
- 🚀 **Helps us prioritize** community-requested improvements
- 🤝 **Shows appreciation** for open-source work

### **Quick Actions:**
[⭐ Star](https://github.com/salacoste/openapi-mcp-swagger/stargazers) • [🍴 Fork](https://github.com/salacoste/openapi-mcp-swagger/fork) • [📋 Issues](https://github.com/salacoste/openapi-mcp-swagger/issues) • [💬 Discuss](https://github.com/salacoste/openapi-mcp-swagger/discussions)

**Thank you for being part of our community! 🙏**

</div>