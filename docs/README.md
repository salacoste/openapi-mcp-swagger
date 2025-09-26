# Swagger MCP Server Documentation

> Transform any Swagger/OpenAPI specification into an intelligent MCP server for AI agents

## Table of Contents

### 🚀 Getting Started
- [Installation Guide](INSTALLATION.md) - Complete installation instructions and system requirements
- [Quick Start Tutorial](guides/QUICKSTART.md) - Get your first MCP server running in 5 minutes
- [Basic Configuration](guides/BASIC_CONFIG.md) - Essential configuration for new users

### 📖 CLI Reference
- [Command Reference](reference/CLI_REFERENCE.md) - Complete CLI commands, options, and examples
- [Configuration Management](reference/CONFIGURATION.md) - Configuration file syntax and options
- [Server Management](reference/SERVER_MANAGEMENT.md) - Starting, stopping, and monitoring servers

### 💡 Examples
- [Sample Swagger Files](examples/swagger-files/) - Real-world API examples for testing
- [Configuration Examples](examples/configurations/) - Ready-to-use configuration templates
- [Integration Examples](examples/integrations/) - AI assistant and tool integrations

### 📚 Guides
- [Deployment Guide](guides/DEPLOYMENT.md) - Production deployment and best practices
- [Performance Tuning](guides/PERFORMANCE.md) - Optimization and scaling strategies
- [Security Configuration](guides/SECURITY.md) - Hardening and production security

### 🔧 Troubleshooting
- [Common Issues](troubleshooting/COMMON_ISSUES.md) - Frequently encountered problems and solutions
- [Error Reference](troubleshooting/ERROR_REFERENCE.md) - Error messages and resolution steps
- [Diagnostic Tools](troubleshooting/DIAGNOSTICS.md) - Tools and techniques for problem diagnosis

### 🔌 API Reference
- [MCP Protocol Integration](api/MCP_PROTOCOL.md) - Using MCP protocol with AI agents
- [Extension Points](api/EXTENSIONS.md) - Customizing and extending functionality
- [Development Guide](api/DEVELOPMENT.md) - Contributing and development setup

---

## Overview

The Swagger MCP Server converts any OpenAPI/Swagger specification into a fully functional MCP (Model Context Protocol) server. This enables AI coding assistants to intelligently query, understand, and utilize API documentation without the limitations of context windows.

### Key Features

- **🔄 One-Command Conversion**: Transform Swagger files to MCP servers instantly
- **🔍 Intelligent Search**: Advanced search across endpoints, parameters, and schemas
- **⚡ High Performance**: Optimized indexing and caching for fast responses
- **🛡️ Production Ready**: SSL support, authentication, and monitoring
- **🔧 Highly Configurable**: Extensive configuration options for any deployment
- **📱 Cross-Platform**: Works on Windows, macOS, and Linux

### Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   AI Agent      │◄──►│   MCP Server     │◄──►│  Search Engine  │
│                 │    │                  │    │                 │
│ • Claude        │    │ • JSON-RPC API   │    │ • Endpoint Index│
│ • GPT-4         │    │ • Authentication │    │ • Schema Index  │
│ • Cursor        │    │ • Rate Limiting  │    │ • Full-Text     │
│ • Custom Tools  │    │ • Monitoring     │    │ • Relationships │
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

### Quick Example

```bash
# Install
pip install swagger-mcp-server

# Convert Swagger to MCP Server
swagger-mcp-server convert api.json --name my-api

# Start server
cd mcp-server-my-api
swagger-mcp-server serve

# Query from AI agent
curl -X POST http://localhost:8080 \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "searchEndpoints",
    "params": {"keywords": "user authentication"}
  }'
```

---

## Documentation Categories

### For New Users
- Start with [Installation Guide](INSTALLATION.md)
- Follow [Quick Start Tutorial](guides/QUICKSTART.md)
- Configure basics with [Basic Configuration](guides/BASIC_CONFIG.md)

### For Developers
- Review [CLI Reference](reference/CLI_REFERENCE.md)
- Explore [Configuration Reference](reference/CONFIGURATION.md)
- Check [Development Guide](api/DEVELOPMENT.md)

### For Operations
- Follow [Deployment Guide](guides/DEPLOYMENT.md)
- Implement [Security Configuration](guides/SECURITY.md)
- Monitor with [Performance Tuning](guides/PERFORMANCE.md)

### For Troubleshooting
- Check [Common Issues](troubleshooting/COMMON_ISSUES.md)
- Search [Error Reference](troubleshooting/ERROR_REFERENCE.md)
- Use [Diagnostic Tools](troubleshooting/DIAGNOSTICS.md)

---

## Support and Community

### Getting Help
- **Documentation**: Start here with comprehensive guides and references
- **GitHub Issues**: [Report bugs](https://github.com/swagger-mcp-server/swagger-mcp-server/issues)
- **Discussions**: [Community Q&A](https://github.com/swagger-mcp-server/swagger-mcp-server/discussions)
- **Examples**: [Real-world examples](examples/) in this repository

### Contributing
- **Documentation**: Help improve these docs
- **Examples**: Contribute integration examples
- **Bug Reports**: Submit detailed issue reports
- **Feature Requests**: Propose new functionality

### Resources
- **Source Code**: [GitHub Repository](https://github.com/swagger-mcp-server/swagger-mcp-server)
- **PyPI Package**: [swagger-mcp-server](https://pypi.org/project/swagger-mcp-server/)
- **Docker Images**: [Docker Hub](https://hub.docker.com/r/swagger-mcp-server/swagger-mcp-server)

---

## License and Credits

This project is open source and available under the [MIT License](../LICENSE).

Built with:
- **[Click](https://click.palletsprojects.com/)** - Command-line interface framework
- **[Whoosh](https://whoosh.readthedocs.io/)** - Full-text search library
- **[FastAPI](https://fastapi.tiangolo.com/)** - Modern web framework for APIs
- **[SQLite](https://sqlite.org/)** - Embedded database engine
- **[OpenAPI Spec Validator](https://github.com/p1c2u/openapi-spec-validator)** - OpenAPI validation

Special thanks to the [Model Context Protocol](https://github.com/modelcontextprotocol) specification creators and the broader AI development community.