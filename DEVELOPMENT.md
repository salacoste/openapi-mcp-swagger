# Development Setup Guide

## Prerequisites

- **Python 3.11+** (tested with Python 3.13.3)
- **Poetry** (recommended) or pip
- **pipx** (for Poetry installation)

## Quick Setup

### 1. Install System Dependencies

```bash
# macOS (using Homebrew)
brew install python@3.13 pipx

# Ubuntu/Debian
sudo apt update
sudo apt install python3.11-dev python3.11-venv python3-pip pipx

# Install Poetry
pipx install poetry
```

### 2. Setup Project

```bash
# Clone repository
git clone https://github.com/bmad-dev/swagger-mcp-server.git
cd swagger-mcp-server

# Option A: Using Poetry (Recommended)
poetry install --with dev
poetry shell

# Option B: Using pip with virtual environment
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install --upgrade pip
pip install -e ".[dev]"
```

### 3. Verify Installation

```bash
# Test basic functionality
python -c "
import sys; sys.path.append('src')
from swagger_mcp_server.storage.migrations import Migration
print('✅ Installation successful!')
"
```

## Virtual Environment

This project uses a Python virtual environment located at `.venv/`.

### Essential Dependencies

**Core Runtime Dependencies:**
- `sqlalchemy>=2.0.0` - Database ORM with async support
- `aiosqlite>=0.19.0` - Async SQLite driver
- `greenlet>=3.0.0` - Required for SQLAlchemy async operations
- `structlog>=23.2.0` - Structured logging
- `mcp>=1.0.0` - MCP protocol implementation
- `ijson>=3.2.3` - Streaming JSON parsing
- `pydantic>=2.5.0` - Data validation

**Development Dependencies:**
- `pytest>=7.4.3` + `pytest-asyncio>=0.21.1` - Testing framework
- `pytest-cov>=4.1.0` - Code coverage
- `black`, `isort`, `flake8`, `mypy` - Code quality tools

### Environment Management

```bash
# Activate virtual environment
source .venv/bin/activate  # Linux/macOS
# OR
.venv\Scripts\activate     # Windows

# Deactivate
deactivate

# Check which environment is active
which python
```

## Running Tests

### Unit Tests (Storage Layer)
```bash
# Basic storage tests
PYTHONPATH=src python -m pytest src/tests/unit/test_storage/ -v

# Migration tests
PYTHONPATH=src python -m pytest src/tests/unit/test_storage/test_migrations.py -v

# Repository tests
PYTHONPATH=src python -m pytest src/tests/unit/test_storage/test_repositories.py -v
```

### Performance Tests (NFR Validation)
```bash
# Performance validation (validates <200ms search requirements)
PYTHONPATH=src python -m pytest src/tests/performance/ -v

# Specific performance tests
PYTHONPATH=src python -m pytest src/tests/performance/test_storage_performance.py::TestSearchPerformance -v
```

### Coverage Reports
```bash
# Generate HTML coverage report
pytest --cov=src/swagger_mcp_server --cov-report=html src/tests/unit/

# View coverage
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
```

## Project Structure
```
swagger-mcp-server/
├── src/
│   ├── swagger_mcp_server/        # Main package
│   │   ├── storage/               # Database layer (Story 1.4)
│   │   │   ├── models.py          # SQLAlchemy models
│   │   │   ├── database.py        # Database manager
│   │   │   ├── migrations.py      # Migration system
│   │   │   └── repositories/      # Data access layer
│   │   ├── parser/                # OpenAPI parsing (Stories 1.2-1.3)
│   │   ├── server/                # MCP implementation (Epic 2)
│   │   ├── config/                # Configuration
│   │   └── examples/              # Code generation
│   └── tests/                     # Test suite
│       ├── unit/                  # Unit tests
│       ├── integration/           # Integration tests
│       └── performance/           # Performance tests (NEW)
├── .venv/                         # Virtual environment (excluded from git)
├── docs/                          # Documentation
│   └── stories/                   # BMAD-METHOD stories
└── pyproject.toml                 # Project configuration
```

## Development Workflow

### 1. Before Starting Work
```bash
# Activate environment
source .venv/bin/activate

# Verify all tests pass
PYTHONPATH=src python -m pytest src/tests/unit/test_storage/ -v
```

### 2. During Development
```bash
# Run specific tests for your changes
PYTHONPATH=src python -m pytest src/tests/unit/test_storage/test_migrations.py::TestMigration -v

# Check code quality
black src/
flake8 src/swagger_mcp_server/
```

### 3. Before Committing
```bash
# Run full test suite
PYTHONPATH=src python -m pytest src/tests/unit/ -v

# Performance validation
PYTHONPATH=src python -m pytest src/tests/performance/ -v
```

## Troubleshooting

### Common Issues

**1. Import Errors:**
```bash
# Make sure PYTHONPATH includes src/
export PYTHONPATH="$PWD/src:$PYTHONPATH"
```

**2. SQLAlchemy Async Errors:**
```bash
# Ensure greenlet is installed
pip install greenlet>=3.0.0
```

**3. Test Discovery Issues:**
```bash
# Use explicit paths for pytest
python -m pytest src/tests/unit/test_storage/ -v
```

**4. Poetry Issues:**
```bash
# Reinstall Poetry
pipx uninstall poetry
pipx install poetry
```

### Performance Debugging
```bash
# Run single performance test with verbose output
PYTHONPATH=src python -m pytest src/tests/performance/test_storage_performance.py::TestSearchPerformance::test_endpoint_search_performance -v -s
```