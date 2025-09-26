# Common Issues and Solutions

> Quick solutions to frequently encountered problems

This guide covers the most common issues users encounter with swagger-mcp-server and provides step-by-step solutions.

## 🔧 Installation Issues

### Python Version Error

**Problem:**
```
ERROR: Python 3.9 or higher is required, found Python 3.8.5
```

**Solution:**
```bash
# Check current Python version
python --version
python3 --version

# Option 1: Install Python 3.9+ from python.org
# Download from https://python.org/downloads/

# Option 2: Use pyenv (recommended)
curl https://pyenv.run | bash
pyenv install 3.9.16
pyenv global 3.9.16

# Option 3: Use conda
conda create -n swagger-mcp python=3.9
conda activate swagger-mcp

# Verify installation
python --version
pip install swagger-mcp-server
```

### Permission Denied During Installation

**Problem:**
```
PermissionError: [Errno 13] Permission denied: '/usr/local/lib/python3.9/site-packages/'
```

**Solutions:**

**Option 1: Install in user space (recommended)**
```bash
pip install --user swagger-mcp-server
```

**Option 2: Use virtual environment (best practice)**
```bash
python -m venv swagger-mcp-env
source swagger-mcp-env/bin/activate  # Linux/macOS
# or
swagger-mcp-env\Scripts\activate     # Windows
pip install swagger-mcp-server
```

**Option 3: Use sudo (not recommended)**
```bash
sudo pip install swagger-mcp-server
```

### Package Not Found Error

**Problem:**
```
ERROR: Could not find a version that satisfies the requirement swagger-mcp-server
```

**Solution:**
```bash
# Update pip first
pip install --upgrade pip

# Clear pip cache
pip cache purge

# Install with verbose output to see the issue
pip install -v swagger-mcp-server

# Alternative: Install from TestPyPI if in development
pip install -i https://test.pypi.org/simple/ swagger-mcp-server
```

---

## 📁 File Conversion Issues

### Invalid Swagger File

**Problem:**
```
ERROR: Invalid OpenAPI specification: 'openapi' is a required property
```

**Solutions:**

**Step 1: Validate your file**
```bash
# Check JSON syntax
python -m json.tool your-api.json

# Validate OpenAPI spec online
# Go to https://editor.swagger.io and paste your content

# Use validation command
swagger-mcp-server convert your-api.json --validate-only
```

**Step 2: Common fixes**
```yaml
# Ensure required fields are present
openapi: "3.0.0"  # Required
info:             # Required
  title: "Your API"
  version: "1.0.0"
paths: {}         # Required (can be empty)
```

**Step 3: Convert YAML to JSON if needed**
```bash
# Install PyYAML if not present
pip install PyYAML

# Convert YAML to JSON
python -c "
import yaml, json, sys
with open('api.yaml') as f:
    data = yaml.safe_load(f)
with open('api.json', 'w') as f:
    json.dump(data, f, indent=2)
"
```

### Large File Processing Timeout

**Problem:**
```
ERROR: Conversion timeout after 300 seconds
Processing file: large-api.json (25MB)
```

**Solutions:**

**Option 1: Use streaming mode**
```bash
swagger-mcp-server convert large-api.json --streaming
```

**Option 2: Increase system resources**
```bash
# Increase Python memory limit
export PYTHONHASHSEED=0
ulimit -v 2097152  # 2GB virtual memory limit

# Use more efficient conversion
swagger-mcp-server convert large-api.json --name large-api --port 8080
```

**Option 3: Split large APIs**
```bash
# Create separate files for different API sections
# Example: split by paths starting with /users, /orders, etc.
```

### Missing Schemas or Incomplete Conversion

**Problem:**
```
WARNING: 15 schema references could not be resolved
WARNING: 8 endpoints skipped due to missing schemas
```

**Solution:**
```bash
# Check for external references
grep -r '\$ref.*http' your-api.json

# Download external schemas
curl -o external-schema.json https://api.example.com/schema.json

# Use bundled specification (combine all references)
# Tools like swagger-codegen or openapi-generator can help bundle specs
```

---

## 🚀 Server Runtime Issues

### Port Already in Use

**Problem:**
```
ERROR: [Errno 48] Address already in use: ('localhost', 8080)
```

**Solutions:**

**Option 1: Use different port**
```bash
swagger-mcp-server serve --port 9000
```

**Option 2: Find and stop conflicting service**
```bash
# Find what's using the port
lsof -i :8080
# or
netstat -tulpn | grep :8080

# Kill the process (replace PID with actual process ID)
kill -9 <PID>
```

**Option 3: Configure default port**
```yaml
# In config.yaml
server:
  port: 9000
```

### Database Connection Errors

**Problem:**
```
DatabaseError: database is locked
# or
DatabaseError: unable to open database file
```

**Solutions:**

**Step 1: Check file permissions**
```bash
ls -la mcp_server.db
# Should show read/write permissions for your user

# Fix permissions if needed
chmod 644 mcp_server.db
chown $USER:$USER mcp_server.db
```

**Step 2: Check for other processes**
```bash
# Check if another server instance is running
swagger-mcp-server status --all

# Stop other instances
swagger-mcp-server stop --all
```

**Step 3: Reset database**
```bash
# Backup existing database
cp mcp_server.db mcp_server.db.backup

# Remove corrupted database (will be recreated)
rm mcp_server.db

# Restart server (will recreate database)
swagger-mcp-server serve
```

### Search Index Corruption

**Problem:**
```
ERROR: Search index corrupted or incompatible
SearchError: Cannot read index directory
```

**Solution:**
```bash
# Remove corrupted index
rm -rf search_index/

# Option 1: Restart server (will rebuild index)
swagger-mcp-server serve

# Option 2: Rebuild explicitly (if command exists)
swagger-mcp-server rebuild-index

# Option 3: Re-convert from original Swagger file
swagger-mcp-server convert original-api.json --name api --overwrite
```

---

## ⚡ Performance Issues

### Slow Response Times

**Problem:**
Server responds slowly to queries (>2 seconds per request).

**Diagnosis:**
```bash
# Check server status
swagger-mcp-server status --all

# Monitor system resources
top -p $(pgrep -f swagger-mcp-server)

# Test specific queries
time curl -X POST http://localhost:8080 -d '{"jsonrpc":"2.0","id":1,"method":"searchEndpoints","params":{"keywords":"test"}}'
```

**Solutions:**

**Option 1: Increase cache size**
```yaml
# In config.yaml
search:
  performance:
    cache_size_mb: 128  # Increase from default 32MB
```

**Option 2: Optimize database**
```yaml
# In config.yaml
database:
  pool_size: 10       # Increase connection pool
  journal_mode: wal   # Use write-ahead logging
```

**Option 3: System optimization**
```bash
# Increase system limits
ulimit -n 65536     # Increase file descriptor limit

# Use SSD storage for database and index
# Move to faster storage if on HDD
```

### High Memory Usage

**Problem:**
Server consumes excessive memory (>500MB for small APIs).

**Solutions:**

**Option 1: Reduce cache sizes**
```yaml
# In config.yaml
search:
  performance:
    cache_size_mb: 32  # Reduce cache size

database:
  pool_size: 2         # Reduce connection pool
```

**Option 2: Enable garbage collection tuning**
```bash
# Set Python garbage collection environment variables
export PYTHONHASHSEED=0
export PYTHONOPTIMIZE=2

# Restart server
swagger-mcp-server serve
```

**Option 3: Monitor and restart periodically**
```bash
# Create monitoring script
#!/bin/bash
while true; do
  MEMORY=$(ps -o pid,vsz,comm | grep swagger-mcp | awk '{print $2}')
  if [ "$MEMORY" -gt 524288 ]; then  # 512MB in KB
    echo "Memory limit exceeded, restarting server"
    swagger-mcp-server stop
    sleep 5
    swagger-mcp-server serve --daemon
  fi
  sleep 300  # Check every 5 minutes
done
```

---

## 🔌 Integration Issues

### AI Agent Connection Problems

**Problem:**
AI tools cannot connect to MCP server or receive empty responses.

**Diagnosis:**
```bash
# Test server health
curl http://localhost:8080/health

# Test basic connectivity
curl -X POST http://localhost:8080 \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"searchEndpoints","params":{"keywords":"test"}}'

# Check server logs
swagger-mcp-server logs --follow
```

**Solutions:**

**Option 1: Verify MCP protocol format**
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "searchEndpoints",
  "params": {
    "keywords": "user authentication"
  }
}
```

**Option 2: Check CORS settings for web clients**
```yaml
# In config.yaml
development:
  cors:
    enabled: true
    origins: ["http://localhost:3000", "https://cursor.sh"]
    methods: ["GET", "POST", "OPTIONS"]
    headers: ["Content-Type"]
```

**Option 3: Verify network connectivity**
```bash
# Test from AI tool's perspective
curl -v http://localhost:8080/health

# Check firewall settings
sudo ufw status  # Ubuntu
sudo firewall-cmd --list-all  # CentOS/RHEL
```

### SSL/TLS Certificate Issues

**Problem:**
```
SSL certificate verification failed
unable to get local issuer certificate
```

**Solutions:**

**Option 1: For development - disable SSL verification**
```bash
# In client configuration, disable SSL verification
# WARNING: Only for development!
```

**Option 2: Fix certificate issues**
```bash
# Check certificate validity
openssl x509 -in cert.pem -text -noout -dates

# Verify certificate chain
openssl verify -CAfile ca-bundle.crt cert.pem

# Check certificate matches key
openssl x509 -noout -modulus -in cert.pem | openssl md5
openssl rsa -noout -modulus -in key.pem | openssl md5
```

**Option 3: Use self-signed certificates for development**
```bash
# Generate self-signed certificate
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes

# Update configuration
swagger-mcp-server config edit
# Set ssl.cert_file and ssl.key_file paths
```

---

## 🔧 Configuration Issues

### Configuration File Not Found

**Problem:**
```
ConfigurationError: Configuration file not found: config.yaml
```

**Solution:**
```bash
# Create configuration from template
swagger-mcp-server config create development --output config.yaml

# Or specify explicit path
swagger-mcp-server serve --config /full/path/to/config.yaml

# Check default location
ls ~/.swagger-mcp-server/config.yaml
```

### Invalid Configuration Format

**Problem:**
```
ConfigurationError: Invalid YAML syntax at line 15, column 3
```

**Solution:**
```bash
# Validate YAML syntax
python -c "
import yaml
with open('config.yaml') as f:
    try:
        yaml.safe_load(f)
        print('✅ YAML syntax is valid')
    except yaml.YAMLError as e:
        print(f'❌ YAML error: {e}')
"

# Validate configuration
swagger-mcp-server config validate --config config.yaml

# Common YAML issues:
# - Incorrect indentation (use spaces, not tabs)
# - Missing quotes around strings with special characters
# - Inconsistent list formatting
```

---

## 🆘 Getting More Help

### Collecting Diagnostic Information

When reporting issues, please include:

```bash
# System information
swagger-mcp-server --version
python --version
uname -a  # Linux/macOS
systeminfo | findstr /B /C:"OS Name" /C:"OS Version"  # Windows

# Configuration
swagger-mcp-server config show

# Server status
swagger-mcp-server status --all --json

# Recent logs
swagger-mcp-server logs --lines 50

# Resource usage
ps aux | grep swagger-mcp
df -h  # Disk usage
free -h  # Memory usage (Linux)
```

### Enable Debug Logging

```bash
# Temporary debug mode
swagger-mcp-server --verbose serve

# Permanent debug mode
swagger-mcp-server config edit
# Set logging.level: DEBUG
```

### Test with Minimal Configuration

```yaml
# minimal-config.yaml
server:
  host: localhost
  port: 8080

database:
  path: ./test.db

search:
  index_directory: ./test_index

logging:
  level: DEBUG
  console: true
```

```bash
swagger-mcp-server serve --config minimal-config.yaml
```

### Community Resources

- **GitHub Issues**: [Report bugs](https://github.com/swagger-mcp-server/swagger-mcp-server/issues)
- **Discussions**: [Community Q&A](https://github.com/swagger-mcp-server/swagger-mcp-server/discussions)
- **Documentation**: [Complete docs](../README.md)
- **Examples**: [Working examples](../examples/)

### Before Reporting Issues

1. ✅ Check this troubleshooting guide
2. ✅ Search existing GitHub issues
3. ✅ Test with minimal configuration
4. ✅ Collect diagnostic information
5. ✅ Try the latest version
6. ✅ Check for conflicting software

**Issue Template:**
```markdown
## Problem Description
Brief description of the issue

## Environment
- OS: [Ubuntu 20.04 / macOS 12.1 / Windows 10]
- Python: [3.9.16]
- swagger-mcp-server: [1.0.0]

## Steps to Reproduce
1. Step one
2. Step two
3. Step three

## Expected Behavior
What should happen

## Actual Behavior
What actually happens

## Logs
```
[Paste relevant logs here]
```

## Configuration
```yaml
[Paste relevant config here]
```
```

This format helps maintainers quickly understand and resolve your issue!