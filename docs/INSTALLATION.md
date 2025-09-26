# Installation Guide

## Overview

The Swagger MCP Server provides automated installation and setup capabilities for cross-platform deployment. This guide covers installation methods, system requirements, and troubleshooting.

## System Requirements

### Minimum Requirements
- **Python**: 3.9 or higher
- **Operating System**: Windows 10+, macOS 10.15+, or Linux (Ubuntu 18.04+)
- **Memory**: 512MB available RAM
- **Disk Space**: 100MB free space
- **Network**: Internet connection (for package downloads)

### Supported Platforms
- **Windows**: Windows 10, Windows 11
- **macOS**: macOS 10.15 (Catalina) and later
- **Linux**: Ubuntu 18.04+, CentOS 7+, Debian 10+, Fedora 30+

## Installation Methods

### Method 1: pip Installation (Recommended)

```bash
# Install from PyPI
pip install swagger-mcp-server

# Run setup
swagger-mcp-server setup
```

### Method 2: Poetry Installation (Development)

```bash
# Clone repository
git clone <repository-url>
cd swagger-mcp-server

# Install with Poetry
poetry install

# Run setup
poetry run swagger-mcp-server setup
```

### Method 3: Development Installation

```bash
# Clone and install in development mode
git clone <repository-url>
cd swagger-mcp-server
pip install -e .

# Run setup
swagger-mcp-server setup
```

## Setup Process

### Interactive Setup

The setup command provides an interactive installation experience:

```bash
swagger-mcp-server setup
```

### Setup Options

```bash
# Force reinstallation (overwrites existing installation)
swagger-mcp-server setup --force

# Setup with verification
swagger-mcp-server setup --verify

# Preview what will be installed
swagger-mcp-server setup --verify --force
```

### What Gets Installed

The setup process creates the following structure:

```
~/.swagger-mcp-server/
├── config/
│   ├── config.yaml          # Main configuration
│   └── servers.json          # Server registry
├── data/
│   ├── database/            # SQLite databases
│   ├── search_index/        # Search indices
│   └── temp/                # Temporary files
├── logs/
│   ├── server.log           # Server logs
│   ├── conversion.log       # Conversion logs
│   └── setup.log            # Setup logs
├── backups/                 # Configuration backups
└── installation_metadata.json
```

## Configuration

### Initial Configuration

After installation, the system creates a default configuration in development mode. You can customize it:

```bash
# Edit configuration
swagger-mcp-server config edit

# Validate configuration
swagger-mcp-server config validate

# View current configuration
swagger-mcp-server config show
```

### Environment-Specific Setup

```bash
# Production setup
swagger-mcp-server config create production

# Development setup (default)
swagger-mcp-server config create development

# Testing setup
swagger-mcp-server config create testing
```

## Verification

### System Health Check

```bash
# Run comprehensive health check
swagger-mcp-server setup --verify
```

### Manual Verification

```bash
# Check installation status
swagger-mcp-server status

# Test basic functionality
swagger-mcp-server test-connection

# Validate configuration
swagger-mcp-server config validate
```

## Uninstallation

### Complete Removal

```bash
# Remove everything (configurations, data, logs)
swagger-mcp-server setup --uninstall
```

### Selective Removal

```bash
# Preserve user configurations
swagger-mcp-server setup --uninstall --preserve-config

# Preserve user data and configurations
swagger-mcp-server setup --uninstall --preserve-config --preserve-data
```

### Manual Cleanup

If the automated uninstaller fails:

```bash
# Remove installation directory
rm -rf ~/.swagger-mcp-server

# Remove package
pip uninstall swagger-mcp-server
```

## Troubleshooting

### Common Issues

#### Permission Errors

**Problem**: Cannot create directories or files
```
PermissionError: [Errno 13] Permission denied
```

**Solution**:
```bash
# Check permissions
ls -la ~/
# Fix permissions
chmod 755 ~/
# Try setup again
swagger-mcp-server setup
```

#### Python Version Issues

**Problem**: Incompatible Python version
```
Python 3.9+ required, found 3.8
```

**Solution**:
```bash
# Update Python
# macOS with Homebrew
brew install python@3.9

# Ubuntu/Debian
sudo apt update && sudo apt install python3.9

# Or use pyenv
pyenv install 3.9.16
pyenv global 3.9.16
```

#### Disk Space Issues

**Problem**: Insufficient disk space
```
Insufficient disk space: 50MB available, 100MB required
```

**Solution**:
```bash
# Check disk usage
df -h
# Clean up temporary files
swagger-mcp-server cleanup
# Or free up space manually
```

#### Network Connectivity Issues

**Problem**: Cannot download packages
```
Network connectivity timeout
```

**Solution**:
```bash
# Test network
ping pypi.org
# Use offline installation
pip install swagger-mcp-server --no-deps
# Or configure proxy if needed
pip install --proxy http://proxy:8080 swagger-mcp-server
```

#### Dependency Conflicts

**Problem**: Package conflicts
```
ERROR: Cannot install swagger-mcp-server and other-package
```

**Solution**:
```bash
# Use virtual environment
python -m venv venv
source venv/bin/activate  # Linux/macOS
# or
venv\Scripts\activate  # Windows
pip install swagger-mcp-server
```

### Advanced Troubleshooting

#### Debug Mode

```bash
# Enable debug logging
export LOG_LEVEL=DEBUG
swagger-mcp-server setup --verify
```

#### System Information

```bash
# Get detailed system info
swagger-mcp-server system-info

# Check compatibility
swagger-mcp-server check-compatibility
```

#### Log Analysis

```bash
# View setup logs
cat ~/.swagger-mcp-server/logs/setup.log

# View server logs
tail -f ~/.swagger-mcp-server/logs/server.log
```

### Getting Help

If you continue to experience issues:

1. **Check Logs**: Review logs in `~/.swagger-mcp-server/logs/`
2. **System Info**: Run `swagger-mcp-server system-info`
3. **Compatibility**: Run `swagger-mcp-server check-compatibility`
4. **Documentation**: Review this guide and the main README
5. **Support**: Create an issue with system info and logs

## Advanced Configuration

### Custom Installation Directory

Currently not supported. Installation always uses `~/.swagger-mcp-server/`

### Environment Variables

```bash
# Custom configuration directory
export SWAGGER_MCP_CONFIG_DIR=/custom/path

# Custom log level
export LOG_LEVEL=DEBUG

# Disable network checks
export SWAGGER_MCP_OFFLINE=true
```

### Integration with System Services

#### systemd Service (Linux)

```ini
# /etc/systemd/system/swagger-mcp-server.service
[Unit]
Description=Swagger MCP Server
After=network.target

[Service]
Type=simple
User=mcp-user
ExecStart=/usr/local/bin/swagger-mcp-server serve
Restart=always

[Install]
WantedBy=multi-user.target
```

#### launchd Service (macOS)

```xml
<!-- ~/Library/LaunchAgents/com.swagger-mcp-server.plist -->
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.swagger-mcp-server</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/bin/swagger-mcp-server</string>
        <string>serve</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
</dict>
</plist>
```

## Security Considerations

### File Permissions

The installer sets appropriate permissions:
- **Directories**: 755 (rwxr-xr-x)
- **Configuration files**: 644 (rw-r--r--)
- **Log files**: 644 (rw-r--r--)
- **Database files**: 600 (rw-------)

### Network Security

- No incoming network connections by default
- Outbound connections only for package downloads
- All data stored locally

### Data Privacy

- No data sent to external services
- All processing happens locally
- Configuration and data remain on your system

## Performance Optimization

### Memory Usage

- Minimum: 512MB RAM
- Recommended: 1GB+ RAM for large API specifications
- Large files (>50MB) may require additional memory

### Disk Usage

- Base installation: ~50MB
- Search indices: ~10-20% of source API specification size
- Logs: Rotated automatically, ~100MB maximum

### CPU Usage

- Setup: CPU-intensive during initial indexing
- Runtime: Low CPU usage during normal operation
- Search: CPU usage scales with query complexity

## Migration and Upgrades

### Upgrading

```bash
# Upgrade package
pip install --upgrade swagger-mcp-server

# Verify installation
swagger-mcp-server setup --verify
```

### Data Migration

Configuration and data are automatically preserved during upgrades. If manual migration is needed:

```bash
# Backup current installation
swagger-mcp-server backup create

# Restore from backup if needed
swagger-mcp-server backup restore <backup-name>
```

### Version Compatibility

- **Backward Compatibility**: Configuration files are backward compatible
- **Database Migrations**: Automatic schema migrations during startup
- **API Changes**: Major version changes may require configuration updates