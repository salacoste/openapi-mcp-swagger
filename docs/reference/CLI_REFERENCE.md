# CLI Reference

> Complete reference for all swagger-mcp-server commands

The swagger-mcp-server CLI provides a comprehensive set of commands for converting Swagger files, managing MCP servers, and configuring your environment.

## Command Structure

```
swagger-mcp-server [GLOBAL-OPTIONS] COMMAND [COMMAND-OPTIONS] [ARGUMENTS]
```

## Global Options

These options are available for all commands:

| Option | Short | Type | Description | Default |
|--------|-------|------|-------------|---------|
| `--verbose` | `-v` | FLAG | Enable verbose output with detailed logging | False |
| `--quiet` | `-q` | FLAG | Enable quiet mode (minimal output) | False |
| `--config` | `-c` | PATH | Path to configuration file | `~/.swagger-mcp-server/config.yaml` |
| `--help` | `-h` | FLAG | Show help message and exit | - |
| `--version` | - | FLAG | Show version and exit | - |

### Global Examples

```bash
# Show version
swagger-mcp-server --version

# Use custom config file
swagger-mcp-server --config ./my-config.yaml serve

# Enable verbose output for all commands
swagger-mcp-server --verbose convert api.json
```

---

## Commands

### `convert`

Convert Swagger/OpenAPI file to MCP server.

```bash
swagger-mcp-server convert <swagger-file> [OPTIONS]
```

#### Arguments

- **`swagger-file`** (required): Path to Swagger/OpenAPI JSON or YAML file

#### Options

| Option | Short | Type | Description | Default |
|--------|-------|------|-------------|---------|
| `--output` | `-o` | PATH | Output directory for generated server | `./mcp-server-{name}` |
| `--port` | `-p` | INTEGER | Default server port (1024-65535) | 8080 |
| `--name` | `-n` | TEXT | Server name identifier | From Swagger title |
| `--dry-run` | - | FLAG | Preview conversion without generating files | False |
| `--validate-only` | - | FLAG | Validate Swagger file only | False |
| `--overwrite` | - | FLAG | Overwrite existing output directory | False |
| `--streaming` | - | FLAG | Use streaming parser for large files (>10MB) | Auto-detect |

#### Examples

**Basic conversion:**
```bash
swagger-mcp-server convert api.json
```

**Custom output directory and port:**
```bash
swagger-mcp-server convert api.json --output ./my-api-server --port 9000
```

**Preview conversion (no files created):**
```bash
swagger-mcp-server convert api.json --dry-run
```

**Validate Swagger file only:**
```bash
swagger-mcp-server convert api.json --validate-only
```

**Convert with custom name:**
```bash
swagger-mcp-server convert api.json --name production-api --output ./prod-server
```

**Overwrite existing directory:**
```bash
swagger-mcp-server convert api.json --output ./existing-server --overwrite
```

#### Output Structure

Successful conversion creates:
```
mcp-server-{name}/
├── config.yaml              # Server configuration
├── mcp_server.db            # SQLite database
├── search_index/            # Whoosh search index
│   ├── _MAIN_1.toc
│   └── ...
├── logs/                    # Log directory
└── README.md               # Generated server documentation
```

---

### `serve`

Start MCP server instance.

```bash
swagger-mcp-server serve [OPTIONS]
```

#### Options

| Option | Short | Type | Description | Default |
|--------|-------|------|-------------|---------|
| `--config` | `-c` | PATH | Server configuration file | Auto-detect config.yaml |
| `--port` | `-p` | INTEGER | Server port | From config (8080) |
| `--host` | `-h` | TEXT | Server host | From config (localhost) |
| `--daemon` | `-d` | FLAG | Run server in background | False |
| `--name` | `-n` | TEXT | Server instance name | Auto-generate |
| `--ssl-cert` | - | PATH | SSL certificate file | None |
| `--ssl-key` | - | PATH | SSL private key file | None |
| `--workers` | `-w` | INTEGER | Number of worker processes | 1 |

#### Examples

**Start with default configuration:**
```bash
swagger-mcp-server serve
```

**Custom host and port:**
```bash
swagger-mcp-server serve --host 0.0.0.0 --port 9000
```

**Run as background daemon:**
```bash
swagger-mcp-server serve --daemon --name production-server
```

**Use specific configuration file:**
```bash
swagger-mcp-server serve --config ./production-config.yaml
```

**Enable SSL:**
```bash
swagger-mcp-server serve --ssl-cert ./cert.pem --ssl-key ./key.pem
```

**Multi-worker production setup:**
```bash
swagger-mcp-server serve --workers 4 --host 0.0.0.0 --daemon
```

#### Server Status Output

When server starts successfully:
```
🚀 Starting MCP server...
   📍 Host: localhost
   🔌 Port: 8080
   👤 Workers: 1
   📁 Config: ./config.yaml
   📊 Database: ./mcp_server.db
   🔍 Search Index: ./search_index

✅ MCP server ready for connections
   🔗 Endpoint: http://localhost:8080
   📋 Methods: searchEndpoints, getSchema, getExample
   🤖 Ready for AI agent connections

   Press Ctrl+C to stop server
```

---

### `status`

Show MCP server status and metrics.

```bash
swagger-mcp-server status [OPTIONS]
```

#### Options

| Option | Short | Type | Description | Default |
|--------|-------|------|-------------|---------|
| `--all` | `-a` | FLAG | Show all running servers | False |
| `--server-id` | `-s` | TEXT | Specific server ID | Current directory |
| `--json` | - | FLAG | Output in JSON format | False |
| `--watch` | `-w` | FLAG | Continuous monitoring mode | False |
| `--refresh` | `-r` | INTEGER | Refresh interval for watch mode (seconds) | 5 |

#### Examples

**Show current server status:**
```bash
swagger-mcp-server status
```

**Show all running servers:**
```bash
swagger-mcp-server status --all
```

**Monitor specific server:**
```bash
swagger-mcp-server status --server-id production-api
```

**Continuous monitoring:**
```bash
swagger-mcp-server status --all --watch
```

**JSON output for scripts:**
```bash
swagger-mcp-server status --all --json
```

#### Status Output Format

**Human-readable format:**
```
📊 MCP Server Status

🔹 Server: ecommerce-api
   📍 Status: Running
   🔌 Port: 8080
   📊 Database: ./mcp_server.db (2.4 MB)
   🔍 Search Index: 1,247 entries
   📈 Uptime: 2h 34m
   📊 Requests: 156 total, 2.3/min average
   💾 Memory: 45.2 MB
   ⚡ Response Time: 23ms average

🔹 Server: user-management-api
   📍 Status: Stopped
   🔌 Port: 8081
   📊 Last seen: 1h 15m ago
```

**JSON format:**
```json
{
  "servers": [
    {
      "id": "ecommerce-api",
      "status": "running",
      "port": 8080,
      "host": "localhost",
      "uptime_seconds": 9240,
      "requests_total": 156,
      "requests_per_minute": 2.3,
      "memory_mb": 45.2,
      "response_time_ms": 23,
      "database_size_mb": 2.4,
      "search_index_entries": 1247
    }
  ],
  "total_servers": 2,
  "running_servers": 1
}
```

---

### `stop`

Stop running MCP server instances.

```bash
swagger-mcp-server stop [OPTIONS]
```

#### Options

| Option | Short | Type | Description | Default |
|--------|-------|------|-------------|---------|
| `--all` | `-a` | FLAG | Stop all running servers | False |
| `--server-id` | `-s` | TEXT | Specific server ID to stop | Current directory |
| `--force` | `-f` | FLAG | Force stop (kill process) | False |
| `--timeout` | `-t` | INTEGER | Graceful shutdown timeout (seconds) | 30 |

#### Examples

**Stop current server:**
```bash
swagger-mcp-server stop
```

**Stop specific server:**
```bash
swagger-mcp-server stop --server-id production-api
```

**Stop all servers:**
```bash
swagger-mcp-server stop --all
```

**Force stop with timeout:**
```bash
swagger-mcp-server stop --force --timeout 10
```

---

### `config`

Manage configuration files and settings.

```bash
swagger-mcp-server config SUBCOMMAND [OPTIONS]
```

#### Subcommands

##### `config show`
Display current configuration.

```bash
swagger-mcp-server config show [--format json|yaml]
```

##### `config validate`
Validate configuration file.

```bash
swagger-mcp-server config validate [--config CONFIG_FILE]
```

##### `config create`
Create configuration template.

```bash
swagger-mcp-server config create TEMPLATE [--output OUTPUT_FILE]
```

Available templates: `development`, `production`, `testing`, `container`

##### `config edit`
Open configuration in default editor.

```bash
swagger-mcp-server config edit
```

#### Examples

**Show current configuration:**
```bash
swagger-mcp-server config show
```

**Validate configuration:**
```bash
swagger-mcp-server config validate --config ./prod-config.yaml
```

**Create production template:**
```bash
swagger-mcp-server config create production --output ./prod-config.yaml
```

**Edit configuration:**
```bash
swagger-mcp-server config edit
```

---

### `setup`

Installation and system setup.

```bash
swagger-mcp-server setup [OPTIONS]
```

#### Options

| Option | Description | Default |
|--------|-------------|---------|
| `--force` | Force reinstallation | False |
| `--verify` | Verify installation | False |
| `--uninstall` | Uninstall system | False |
| `--preserve-config` | Keep configuration during uninstall | False |
| `--preserve-data` | Keep data during uninstall | False |

#### Examples

**Initial setup:**
```bash
swagger-mcp-server setup
```

**Verify installation:**
```bash
swagger-mcp-server setup --verify
```

**Force reinstall:**
```bash
swagger-mcp-server setup --force
```

**Uninstall (keep config):**
```bash
swagger-mcp-server setup --uninstall --preserve-config
```

---

### `examples`

Generate sample files and examples.

```bash
swagger-mcp-server examples SUBCOMMAND [OPTIONS]
```

#### Subcommands

##### `examples create-sample`
Create sample Swagger file.

```bash
swagger-mcp-server examples create-sample --type TYPE --output FILE
```

Types: `ecommerce`, `social-media`, `banking`, `iot`, `healthcare`

##### `examples list`
List available examples.

```bash
swagger-mcp-server examples list [--category CATEGORY]
```

#### Examples

**Create sample e-commerce API:**
```bash
swagger-mcp-server examples create-sample --type ecommerce --output ./sample-api.json
```

**List all examples:**
```bash
swagger-mcp-server examples list
```

---

### `logs`

View and manage server logs.

```bash
swagger-mcp-server logs [OPTIONS]
```

#### Options

| Option | Short | Type | Description | Default |
|--------|-------|------|-------------|---------|
| `--follow` | `-f` | FLAG | Follow log output | False |
| `--lines` | `-n` | INTEGER | Number of lines to show | 50 |
| `--level` | `-l` | TEXT | Filter by log level | All |
| `--server-id` | `-s` | TEXT | Specific server logs | Current |

#### Examples

**View recent logs:**
```bash
swagger-mcp-server logs
```

**Follow logs in real-time:**
```bash
swagger-mcp-server logs --follow
```

**Show last 100 lines:**
```bash
swagger-mcp-server logs --lines 100
```

**Filter error logs:**
```bash
swagger-mcp-server logs --level ERROR
```

---

## Environment Variables

Configure behavior with environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `SWAGGER_MCP_CONFIG_DIR` | Configuration directory | `~/.swagger-mcp-server` |
| `SWAGGER_MCP_LOG_LEVEL` | Default log level | `INFO` |
| `SWAGGER_MCP_HOST` | Default server host | `localhost` |
| `SWAGGER_MCP_PORT` | Default server port | `8080` |
| `SWAGGER_MCP_WORKERS` | Default worker count | `1` |

Example usage:
```bash
export SWAGGER_MCP_LOG_LEVEL=DEBUG
export SWAGGER_MCP_PORT=9000
swagger-mcp-server serve
```

---

## Exit Codes

The CLI uses standard exit codes:

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | General error |
| 2 | Invalid usage/arguments |
| 3 | Configuration error |
| 4 | File not found |
| 5 | Permission denied |
| 6 | Network error |
| 7 | Validation error |

---

## Shell Completion

Enable shell completion for better CLI experience:

### Bash
```bash
_SWAGGER_MCP_SERVER_COMPLETE=bash_source swagger-mcp-server > ~/.swagger-mcp-completion.bash
echo 'source ~/.swagger-mcp-completion.bash' >> ~/.bashrc
```

### Zsh
```bash
_SWAGGER_MCP_SERVER_COMPLETE=zsh_source swagger-mcp-server > ~/.swagger-mcp-completion.zsh
echo 'source ~/.swagger-mcp-completion.zsh' >> ~/.zshrc
```

### Fish
```bash
_SWAGGER_MCP_SERVER_COMPLETE=fish_source swagger-mcp-server > ~/.config/fish/completions/swagger-mcp-server.fish
```

---

## Integration Examples

### With Make
```makefile
.PHONY: start stop status

start:
	swagger-mcp-server serve --daemon --name $(API_NAME)

stop:
	swagger-mcp-server stop --server-id $(API_NAME)

status:
	swagger-mcp-server status --server-id $(API_NAME)

convert:
	swagger-mcp-server convert $(SWAGGER_FILE) --name $(API_NAME)
```

### With Docker
```dockerfile
FROM python:3.9-slim
RUN pip install swagger-mcp-server
COPY api.json /app/
WORKDIR /app
EXPOSE 8080
CMD ["swagger-mcp-server", "convert", "api.json", "--name", "api", "&&", \
     "cd", "mcp-server-api", "&&", \
     "swagger-mcp-server", "serve", "--host", "0.0.0.0"]
```

### With systemd
```ini
[Unit]
Description=Swagger MCP Server
After=network.target

[Service]
Type=simple
User=mcp
WorkingDirectory=/opt/mcp-server
ExecStart=/usr/local/bin/swagger-mcp-server serve --config production.yaml
Restart=always

[Install]
WantedBy=multi-user.target
```

---

**Next Steps:**
- [Configuration Reference](CONFIGURATION.md) - Detailed configuration options
- [Server Management](SERVER_MANAGEMENT.md) - Advanced server management
- [Troubleshooting](../troubleshooting/COMMON_ISSUES.md) - Common issues and solutions