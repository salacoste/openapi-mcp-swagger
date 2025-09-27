# Basic Configuration Guide

> Essential configuration setup for new users

This guide covers the fundamental configuration options you need to get started with openapi-mcp-swagger. For advanced configuration, see the [Configuration Reference](../reference/CONFIGURATION.md).

## Configuration File Location

The main configuration file is located at:
```
~/.swagger-mcp-server/config.yaml
```

When running a server from a specific directory, you can also use:
```
./config.yaml  # In the server directory
```

## Creating Your First Configuration

### Option 1: Use Built-in Templates

```bash
# Create development configuration
swagger-mcp-server config create development --output config.yaml

# Create production configuration
swagger-mcp-server config create production --output config.yaml

# Create testing configuration
swagger-mcp-server config create testing --output config.yaml
```

### Option 2: Start with Minimal Configuration

Create a `config.yaml` file with basic settings:

```yaml
# Minimal configuration for getting started
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

## Essential Configuration Sections

### 1. Server Configuration

Controls how your MCP server listens for connections:

```yaml
server:
  # Network settings
  host: localhost          # localhost for local use, 0.0.0.0 for external access
  port: 8080              # Port number (1024-65535)

  # Connection limits
  max_connections: 50     # Maximum concurrent connections
  connection_timeout: 30  # Connection timeout in seconds

  # SSL settings (for HTTPS)
  ssl:
    enabled: false        # Set to true for HTTPS
    cert_file: ""         # Path to SSL certificate
    key_file: ""          # Path to SSL private key
```

**Common Settings:**
- **Development**: `host: localhost, port: 8080, ssl: false`
- **Production**: `host: 0.0.0.0, port: 8080, ssl: true`
- **Testing**: `host: localhost, port: 8081, ssl: false`

### 2. Database Configuration

Controls where and how data is stored:

```yaml
database:
  # Database file location
  path: ./mcp_server.db   # Relative to server directory
  # path: /var/lib/mcp-server/database.db  # Absolute path for production

  # Connection settings
  pool_size: 5            # Number of database connections
  connection_timeout: 10  # Database connection timeout

  # Backup settings
  backup:
    enabled: false        # Enable automatic backups
    interval: 86400       # Backup interval in seconds (24 hours)
    retention_days: 7     # How long to keep backups
```

**Storage Requirements:**
- **Small API** (<100 endpoints): ~5-10MB
- **Medium API** (100-500 endpoints): ~10-50MB
- **Large API** (500+ endpoints): ~50-200MB

### 3. Search Configuration

Controls search performance and behavior:

```yaml
search:
  # Search engine settings
  engine: whoosh                    # Search engine (currently only whoosh)
  index_directory: ./search_index   # Where search index is stored

  # Search relevance weights
  field_weights:
    endpoint_path: 1.5    # Higher weight = more important for relevance
    summary: 1.3          # Endpoint summaries
    description: 1.0      # Detailed descriptions
    parameters: 0.8       # Parameter names and descriptions
    tags: 0.6             # OpenAPI tags

  # Performance settings
  performance:
    cache_size_mb: 64     # Memory cache size
    max_results: 100      # Maximum search results
    fuzzy_matching: true  # Enable fuzzy/approximate matching
    min_score: 0.2        # Minimum relevance score
```

**Performance Tuning:**
- **Low memory**: `cache_size_mb: 32, max_results: 50`
- **High performance**: `cache_size_mb: 128, max_results: 200`
- **Exact matching**: `fuzzy_matching: false, min_score: 0.5`

### 4. Logging Configuration

Controls log output and debugging:

```yaml
logging:
  # Log level
  level: INFO             # DEBUG, INFO, WARNING, ERROR

  # Log output
  console: true           # Log to console/terminal
  file: ./server.log      # Log to file (optional)

  # Log formatting
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

  # Log rotation (for file logging)
  rotation:
    enabled: false        # Enable log rotation
    max_size_mb: 10       # Rotate when log exceeds size
    backup_count: 5       # Number of backup files to keep
```

**Common Log Levels:**
- **DEBUG**: Detailed information for troubleshooting
- **INFO**: General information about server operation
- **WARNING**: Important events that might need attention
- **ERROR**: Error conditions that need immediate attention

## Environment-Specific Examples

### Development Configuration

Perfect for local development and testing:

```yaml
# config/development.yaml
server:
  host: localhost
  port: 8080
  debug_mode: true        # Enable debug features

database:
  path: ./dev_server.db   # Separate dev database

search:
  index_directory: ./dev_search_index
  performance:
    cache_size_mb: 32     # Lower memory usage

logging:
  level: DEBUG            # Verbose logging
  console: true           # Log to terminal
  file: ./dev_server.log  # Also log to file

# Development-specific features
development:
  auto_reload: true       # Restart on code changes
  cors:
    enabled: true         # Enable CORS for web development
    origins: ["http://localhost:3000"]
```

### Production Configuration

Optimized for production deployment:

```yaml
# config/production.yaml
server:
  host: 0.0.0.0          # Accept external connections
  port: 8080
  max_connections: 100    # Higher connection limit

  ssl:
    enabled: true         # Enable HTTPS
    cert_file: /etc/ssl/certs/server.crt
    key_file: /etc/ssl/private/server.key

database:
  path: /var/lib/mcp-server/server.db  # System directory
  pool_size: 10          # Larger connection pool

  backup:
    enabled: true        # Enable backups
    interval: 86400      # Daily backups
    backup_directory: /var/backups/mcp-server

search:
  index_directory: /var/lib/mcp-server/search_index
  performance:
    cache_size_mb: 128   # More memory for performance
    max_results: 200     # Higher result limit

logging:
  level: INFO            # Standard logging
  console: false         # Don't log to console
  file: /var/log/mcp-server/server.log

  rotation:
    enabled: true        # Rotate logs
    max_size_mb: 10
    backup_count: 10

# Security settings
security:
  authentication:
    enabled: true        # Require authentication
    type: api_key

  rate_limiting:
    enabled: true        # Prevent abuse
    requests_per_minute: 100
```

## Quick Configuration Recipes

### Recipe 1: High Performance Setup

```yaml
server:
  max_connections: 200
  connection_timeout: 15

database:
  pool_size: 20
  journal_mode: wal       # Faster database mode

search:
  performance:
    cache_size_mb: 256
    max_results: 500

logging:
  level: WARNING          # Minimal logging for speed
```

### Recipe 2: Debug Everything

```yaml
logging:
  level: DEBUG
  console: true
  component_levels:
    swagger_parser: DEBUG
    search_engine: DEBUG
    mcp_server: DEBUG
    database: DEBUG

development:
  debug_endpoints: true   # Enable debug API endpoints
  enable_profiling: true  # Performance profiling
```

### Recipe 3: Security Hardened

```yaml
server:
  ssl:
    enabled: true
    protocols: ["TLSv1.2", "TLSv1.3"]

security:
  authentication:
    enabled: true
    type: api_key
    require_https: true

  rate_limiting:
    enabled: true
    requests_per_minute: 60

  validation:
    strict_mode: true
    max_request_size_mb: 1
```

## Configuration Validation

Always validate your configuration before starting the server:

```bash
# Validate configuration file
swagger-mcp-server config validate --config config.yaml

# Show current configuration
swagger-mcp-server config show --format yaml

# Test configuration with dry run
swagger-mcp-server serve --config config.yaml --dry-run
```

## Common Configuration Mistakes

### 1. Wrong File Permissions

```bash
# Configuration file should be readable
chmod 644 config.yaml

# Database directory should be writable
chmod 755 ./database/

# Log directory should be writable
chmod 755 ./logs/
```

### 2. Invalid YAML Syntax

```yaml
# ❌ Wrong - inconsistent indentation
server:
  host: localhost
   port: 8080

# ✅ Correct - consistent 2-space indentation
server:
  host: localhost
  port: 8080
```

### 3. Resource Conflicts

```yaml
# ❌ Wrong - same port as another service
server:
  port: 3000  # Might conflict with React dev server

# ✅ Better - use a dedicated port
server:
  port: 8080  # Standard for API servers
```

## Environment Variables

Override configuration with environment variables:

```bash
# Server settings
export SWAGGER_MCP_SERVER_HOST=0.0.0.0
export SWAGGER_MCP_SERVER_PORT=9000

# Database settings
export SWAGGER_MCP_DB_PATH=/custom/path/database.db

# Logging settings
export SWAGGER_MCP_LOG_LEVEL=DEBUG

# Start server with environment overrides
swagger-mcp-server serve
```

## Configuration Management

### Version Control

```bash
# Include in version control
git add config/development.yaml
git add config/production.yaml

# Exclude environment-specific configs
echo "config/local.yaml" >> .gitignore
echo "*.local.yaml" >> .gitignore
```

### Multiple Environments

```bash
# Different configs for different environments
config/
├── base.yaml           # Common settings
├── development.yaml    # Development overrides
├── staging.yaml       # Staging overrides
├── production.yaml     # Production overrides
└── local.yaml         # Personal local settings (gitignored)
```

### Configuration Templates

```bash
# Generate from template
swagger-mcp-server config create production > config/production.yaml

# Customize for your environment
vim config/production.yaml

# Validate before deployment
swagger-mcp-server config validate --config config/production.yaml
```

## Next Steps

Once you have basic configuration working:

1. **[CLI Reference](../reference/CLI_REFERENCE.md)** - Learn all available commands
2. **[Performance Tuning](PERFORMANCE.md)** - Optimize for your use case
3. **[Security Guide](SECURITY.md)** - Secure your server for production
4. **[Deployment Guide](DEPLOYMENT.md)** - Deploy to production environments

## Getting Help

If you encounter configuration issues:

1. **Validate syntax**: `swagger-mcp-server config validate`
2. **Check logs**: Look for configuration errors in server logs
3. **Use templates**: Start with built-in templates and modify
4. **Check permissions**: Ensure files and directories are accessible
5. **Ask for help**: Use GitHub discussions for configuration questions