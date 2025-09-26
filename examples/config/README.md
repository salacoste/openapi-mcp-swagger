# Configuration Examples

This directory contains example configuration files for different deployment scenarios of the Swagger MCP Server.

## Available Templates

### Development (`development.yaml`)
**Use case**: Local development and testing
- **Host**: `localhost` (local access only)
- **Logging**: `DEBUG` level with file output
- **SSL**: Disabled for simplicity
- **Resources**: Minimal (10 connections, 32MB cache)
- **Features**: Rate limiting disabled, metrics enabled

**Best for**:
- Local development
- Debugging and testing
- Learning the system
- Quick prototyping

### Production (`production.yaml`)
**Use case**: Production deployment
- **Host**: `0.0.0.0` (accepts external connections)
- **Logging**: `INFO` level with rotation
- **SSL**: Enabled with certificate files
- **Resources**: High performance (100 connections, 128MB cache)
- **Features**: All features enabled including rate limiting

**Best for**:
- Live production environments
- High-traffic deployments
- Security-sensitive applications
- Performance-critical systems

### Staging (`staging.yaml`)
**Use case**: Pre-production testing
- **Host**: `0.0.0.0` (accepts external connections)
- **Logging**: `INFO` level with moderate rotation
- **SSL**: Disabled for easier testing
- **Resources**: Moderate (50 connections, 64MB cache)
- **Features**: Most features enabled

**Best for**:
- Integration testing
- QA environments
- Pre-production validation
- Load testing

### Container (`container.yaml`)
**Use case**: Docker/Kubernetes deployment
- **Host**: `0.0.0.0` (container networking)
- **Logging**: Stdout only (container logs)
- **SSL**: Disabled (handled by ingress)
- **Resources**: Container-optimized
- **Features**: Minimal features (handled externally)

**Best for**:
- Docker containers
- Kubernetes deployments
- Microservice architectures
- Cloud-native applications

## Using Templates

### Initialize Configuration
```bash
# Initialize with development template
swagger-mcp-server config init --template development

# Initialize with production template
swagger-mcp-server config init --template production --force

# Initialize with custom file
swagger-mcp-server config init --template staging --file ./my-config.yaml
```

### View Template Contents
```bash
# Show current configuration
swagger-mcp-server config show

# Show in different formats
swagger-mcp-server config show --format yaml
swagger-mcp-server config show --format json
```

### Customize Configuration
```bash
# Set specific values
swagger-mcp-server config set server.port 9000
swagger-mcp-server config set logging.level DEBUG
swagger-mcp-server config set features.rate_limiting.enabled true

# Validate configuration
swagger-mcp-server config validate
```

## Environment Variable Overrides

All configuration values can be overridden using environment variables with the `SWAGGER_MCP_` prefix:

### Server Configuration
```bash
export SWAGGER_MCP_SERVER_HOST=0.0.0.0
export SWAGGER_MCP_SERVER_PORT=9000
export SWAGGER_MCP_SERVER_MAX_CONNECTIONS=200
export SWAGGER_MCP_SERVER_TIMEOUT=45
export SWAGGER_MCP_SERVER_SSL_ENABLED=true
export SWAGGER_MCP_SERVER_SSL_CERT_FILE=/etc/ssl/cert.pem
export SWAGGER_MCP_SERVER_SSL_KEY_FILE=/etc/ssl/key.pem
```

### Database Configuration
```bash
export SWAGGER_MCP_DATABASE_PATH=/var/lib/mcp/server.db
export SWAGGER_MCP_DATABASE_POOL_SIZE=15
export SWAGGER_MCP_DATABASE_TIMEOUT=20
export SWAGGER_MCP_DATABASE_BACKUP_ENABLED=true
export SWAGGER_MCP_DATABASE_BACKUP_INTERVAL=43200
export SWAGGER_MCP_DATABASE_BACKUP_RETENTION=5
```

### Search Configuration
```bash
export SWAGGER_MCP_SEARCH_ENGINE=whoosh
export SWAGGER_MCP_SEARCH_INDEX_DIRECTORY=/var/lib/mcp/search
export SWAGGER_MCP_SEARCH_FIELD_WEIGHTS_ENDPOINT_PATH=2.0
export SWAGGER_MCP_SEARCH_FIELD_WEIGHTS_SUMMARY=1.5
export SWAGGER_MCP_SEARCH_PERFORMANCE_CACHE_SIZE_MB=256
export SWAGGER_MCP_SEARCH_PERFORMANCE_MAX_RESULTS=2000
export SWAGGER_MCP_SEARCH_PERFORMANCE_SEARCH_TIMEOUT=5
```

### Logging Configuration
```bash
export SWAGGER_MCP_LOGGING_LEVEL=WARNING
export SWAGGER_MCP_LOGGING_FORMAT='%(asctime)s [%(levelname)s] %(message)s'
export SWAGGER_MCP_LOGGING_FILE=/var/log/mcp-server.log
export SWAGGER_MCP_LOGGING_ROTATION_ENABLED=true
export SWAGGER_MCP_LOGGING_ROTATION_MAX_SIZE_MB=20
export SWAGGER_MCP_LOGGING_ROTATION_BACKUP_COUNT=10
```

### Features Configuration
```bash
export SWAGGER_MCP_FEATURES_METRICS_ENABLED=true
export SWAGGER_MCP_FEATURES_METRICS_ENDPOINT=/custom-metrics
export SWAGGER_MCP_FEATURES_HEALTH_CHECK_ENABLED=true
export SWAGGER_MCP_FEATURES_HEALTH_CHECK_ENDPOINT=/custom-health
export SWAGGER_MCP_FEATURES_RATE_LIMITING_ENABLED=true
export SWAGGER_MCP_FEATURES_RATE_LIMITING_REQUESTS_PER_MINUTE=500
```

## Configuration Hierarchy

The configuration system follows this precedence order (highest to lowest):

1. **Command-line options** (highest priority)
2. **Environment variables** (`SWAGGER_MCP_*`)
3. **Local project configuration file**
4. **Global user configuration file**
5. **Built-in defaults** (lowest priority)

## Configuration Validation

The system includes comprehensive validation:

### Automatic Validation
- Type checking (string, integer, float, boolean)
- Range validation (ports: 1024-65535, etc.)
- Allowed values (log levels: DEBUG, INFO, WARNING, ERROR)
- Cross-field validation (SSL requires cert and key files)
- Path validation (creates directories if needed)

### Manual Validation
```bash
# Validate current configuration
swagger-mcp-server config validate

# Example output for valid configuration:
✅ Configuration is valid

# Example output for invalid configuration:
❌ Configuration validation failed

Errors:
   • server.port must be at least 1024
   • SSL certificate file is required when SSL is enabled

Warnings:
   • Search cache size is quite small, consider increasing for better performance
   • Debug logging may impact performance and expose sensitive information
```

## Security Considerations

### Development Template
- ⚠️ **Not secure** - designed for local development only
- No SSL encryption
- Debug logging enabled
- Minimal access controls

### Production Template
- ✅ **Secure by default**
- SSL encryption enabled
- Appropriate log levels
- Rate limiting enabled
- Follows security best practices

### Environment Variables
- Never commit sensitive values to configuration files
- Use environment variables for:
  - SSL certificate paths
  - Database credentials
  - API keys
  - Sensitive file paths

## Troubleshooting

### Common Issues

**Port already in use**:
```bash
swagger-mcp-server config set server.port 8081
```

**SSL certificate not found**:
```bash
# Check certificate path
ls -la /etc/ssl/certs/mcp-server.crt

# Disable SSL for testing
swagger-mcp-server config set server.ssl.enabled false
```

**Permission denied for log file**:
```bash
# Create log directory
sudo mkdir -p /var/log/mcp-server
sudo chown $USER:$USER /var/log/mcp-server

# Or use different log location
swagger-mcp-server config set logging.file ./server.log
```

**Database directory not found**:
```bash
# Create database directory
mkdir -p /var/lib/mcp-server

# Or use different database path
swagger-mcp-server config set database.path ./mcp_server.db
```

### Getting Help

```bash
# Show all configuration keys
swagger-mcp-server config show

# Get help for specific configuration key
swagger-mcp-server config help server.port

# Show environment variable mappings
swagger-mcp-server config env-help
```

## Docker Example

```dockerfile
FROM python:3.11-slim

# Install MCP server
COPY . /app
WORKDIR /app
RUN pip install -e .

# Use container template
COPY examples/config/container.yaml /app/config.yaml

# Override with environment variables
ENV SWAGGER_MCP_SERVER_HOST=0.0.0.0
ENV SWAGGER_MCP_SERVER_PORT=8080
ENV SWAGGER_MCP_DATABASE_PATH=/data/mcp_server.db
ENV SWAGGER_MCP_SEARCH_INDEX_DIRECTORY=/data/search_index
ENV SWAGGER_MCP_LOGGING_LEVEL=INFO

# Create data volume
VOLUME ["/data"]

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8080/health || exit 1

# Start server
CMD ["swagger-mcp-server", "serve", "--config-file", "/app/config.yaml"]
```

## Kubernetes Example

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: mcp-server-config
data:
  config.yaml: |
    server:
      host: 0.0.0.0
      port: 8080
    database:
      path: /data/mcp_server.db
    logging:
      level: INFO
      file: null  # stdout
    features:
      health_check:
        enabled: true
        endpoint: /health
      metrics:
        enabled: true
        endpoint: /metrics

---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: mcp-server
spec:
  replicas: 3
  selector:
    matchLabels:
      app: mcp-server
  template:
    metadata:
      labels:
        app: mcp-server
    spec:
      containers:
      - name: mcp-server
        image: mcp-server:latest
        ports:
        - containerPort: 8080
        env:
        - name: SWAGGER_MCP_FEATURES_RATE_LIMITING_ENABLED
          value: "false"  # Handled by ingress
        volumeMounts:
        - name: config
          mountPath: /app/config.yaml
          subPath: config.yaml
        - name: data
          mountPath: /data
        livenessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 10
          periodSeconds: 30
        readinessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 5
          periodSeconds: 10
      volumes:
      - name: config
        configMap:
          name: mcp-server-config
      - name: data
        persistentVolumeClaim:
          claimName: mcp-server-data
```