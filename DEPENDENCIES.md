# Project Dependencies Guide

## Overview

This document explains all dependencies used in the Swagger MCP Server project and why they are needed.

## Core Runtime Dependencies

### Database & Storage
- **`sqlalchemy>=2.0.0`** - Modern Python ORM with full async support
  - Used for: Database models, query building, schema management
  - Why needed: Provides robust ORM layer for SQLite with async operations
  - Story: 1.4 (Storage Layer)

- **`aiosqlite>=0.19.0`** - Async SQLite database driver
  - Used for: Async database connections and operations
  - Why needed: Required for non-blocking database I/O
  - Story: 1.4 (Storage Layer)

- **`greenlet>=3.0.0`** - Lightweight coroutines for SQLAlchemy async
  - Used for: SQLAlchemy async operations under the hood
  - Why needed: Critical dependency for SQLAlchemy 2.0+ async mode
  - Note: Will cause runtime errors if missing
  - Story: 1.4 (Storage Layer)

### MCP Protocol & API Processing
- **`mcp>=1.0.0`** - Model Context Protocol implementation
  - Used for: MCP server implementation, protocol handling
  - Why needed: Core framework for AI agent communication
  - Story: Epic 2 (MCP Server Implementation)

- **`ijson>=3.2.3`** - Streaming JSON parser
  - Used for: Processing large OpenAPI/Swagger files without loading into memory
  - Why needed: Handle 10MB+ API specification files efficiently
  - Story: 1.2 (Stream Parser)

- **`pydantic>=2.5.0`** - Data validation and parsing
  - Used for: Configuration management, request/response validation
  - Why needed: Type-safe data handling and validation
  - Story: Multiple stories for data validation

### Search & Indexing
- **`whoosh>=2.7.4`** - Pure Python full-text search engine
  - Used for: Advanced search capabilities beyond SQLite FTS5
  - Why needed: Provides sophisticated search ranking and filtering
  - Story: Epic 3 (Search & Discovery Engine)

- **`rank-bm25>=0.2.2`** - BM25 ranking algorithm implementation
  - Used for: Search result ranking and relevance scoring
  - Why needed: Industry-standard search ranking algorithm
  - Story: Epic 3 (Search & Discovery Engine)

### OpenAPI Processing
- **`openapi-spec-validator>=0.7.1`** - OpenAPI specification validator
  - Used for: Validating OpenAPI/Swagger files before processing
  - Why needed: Ensure input files are valid before parsing
  - Story: 1.2 (Stream Parser), 1.3 (Schema Normalization)

- **`jsonref>=1.1.0`** - JSON reference resolution
  - Used for: Resolving $ref references in OpenAPI specifications
  - Why needed: Handle complex API specs with shared components
  - Story: 1.3 (Schema Normalization)

### CLI & User Interface
- **`click>=8.1.7`** - Command line interface framework
  - Used for: CLI commands and user interaction
  - Why needed: Professional CLI for API conversion and server management
  - Story: Epic 4 (CLI Tool & Developer Experience)

### Logging
- **`structlog>=23.2.0`** - Structured logging
  - Used for: Structured, machine-readable logging
  - Why needed: Better debugging, monitoring, and observability
  - Story: All stories (cross-cutting concern)

### Code Generation
- **`jinja2>=3.1.2`** - Template engine
  - Used for: Generating code examples (cURL, JavaScript, Python)
  - Why needed: Template-based code generation for API clients
  - Story: Epic 4 (CLI Tool & Developer Experience)

## Development Dependencies

### Testing Framework
- **`pytest>=7.4.3`** - Testing framework
  - Used for: Unit, integration, and performance testing
  - Why needed: Comprehensive test suite with fixtures and plugins

- **`pytest-asyncio>=0.21.1`** - Async testing support for pytest
  - Used for: Testing async database operations and MCP server
  - Why needed: Required for testing async code properly

- **`pytest-cov>=4.1.0`** - Code coverage measurement
  - Used for: Measuring test coverage, generating reports
  - Why needed: Ensure 85%+ test coverage requirement

- **`pytest-benchmark>=4.0.0`** - Performance benchmarking
  - Used for: Performance testing and NFR validation
  - Why needed: Validate <200ms search, <500ms schema requirements

- **`faker>=20.1.0`** - Generate fake test data
  - Used for: Creating realistic test datasets
  - Why needed: Performance testing with large, realistic datasets

### Code Quality
- **`black>=23.11.0`** - Code formatter
  - Used for: Consistent code formatting
  - Why needed: Maintain code style consistency

- **`isort>=5.12.0`** - Import statement sorter
  - Used for: Organizing import statements
  - Why needed: Clean, organized imports

- **`flake8>=6.1.0`** - Style guide enforcement
  - Used for: PEP8 compliance, basic linting
  - Why needed: Code quality standards

- **`flake8-docstrings>=1.7.0`** - Docstring linting
  - Used for: Ensuring proper documentation
  - Why needed: Documentation quality standards

- **`flake8-type-checking>=2.7.0`** - Type checking linting
  - Used for: Type annotation quality
  - Why needed: Type safety standards

- **`mypy>=1.7.0`** - Static type checker
  - Used for: Type checking and type safety
  - Why needed: Catch type-related bugs early

### Development Tools
- **`pre-commit>=3.5.0`** - Git pre-commit hooks
  - Used for: Automated code quality checks before commits
  - Why needed: Prevent bad code from being committed

- **`tox>=4.11.0`** - Testing automation
  - Used for: Testing across multiple Python versions
  - Why needed: Ensure compatibility with Python 3.11-3.13

## Dependency Categories by Story

### Story 1.2 (Stream Parser)
- `ijson` - Streaming JSON processing
- `openapi-spec-validator` - Input validation
- `structlog` - Logging

### Story 1.3 (Schema Normalization)
- `jsonref` - Reference resolution
- `pydantic` - Data validation
- `openapi-spec-validator` - Schema validation

### Story 1.4 (Storage Layer)
- `sqlalchemy` - Database ORM
- `aiosqlite` - Async SQLite driver
- `greenlet` - SQLAlchemy async support
- `structlog` - Logging

### Epic 2 (MCP Server)
- `mcp` - Protocol implementation
- `pydantic` - Request/response validation

### Epic 3 (Search & Discovery)
- `whoosh` - Full-text search
- `rank-bm25` - Search ranking

### Epic 4 (CLI & Developer Experience)
- `click` - CLI framework
- `jinja2` - Code generation templates

## Installation Methods

### Method 1: Poetry (Recommended)
```bash
poetry install --with dev
```
Installs all dependencies from pyproject.toml

### Method 2: pip with requirements
```bash
pip install -e ".[dev]"
```
Uses dependencies defined in pyproject.toml

### Method 3: Manual (Development Only)
```bash
# Core dependencies for storage layer development
pip install sqlalchemy aiosqlite greenlet structlog pytest pytest-asyncio

# Additional development tools
pip install black isort flake8 mypy pytest-cov
```

## Troubleshooting Dependencies

### Common Issues

1. **SQLAlchemy async errors**
   - Symptom: `ValueError: the greenlet library is required`
   - Solution: `pip install greenlet>=3.0.0`

2. **Import errors in tests**
   - Symptom: `ModuleNotFoundError` for swagger_mcp_server
   - Solution: Set `PYTHONPATH=src` before running tests

3. **Poetry installation issues**
   - Symptom: Poetry command not found or errors
   - Solution: `pipx uninstall poetry && pipx install poetry`

4. **Version conflicts**
   - Symptom: Dependency resolver errors
   - Solution: Create fresh virtual environment

### Minimum Requirements for Core Functionality

If you need to run with minimal dependencies:

```bash
# Absolute minimum for storage layer
pip install sqlalchemy>=2.0.0 aiosqlite>=0.19.0 greenlet>=3.0.0 structlog>=23.2.0

# Add for testing
pip install pytest>=7.4.3 pytest-asyncio>=0.21.1
```

## Version Constraints Explained

- **`>=` constraints**: Allow newer versions for security updates and bug fixes
- **Minimum versions chosen**: Based on required features:
  - SQLAlchemy 2.0+: Required for modern async support
  - Python 3.11+: Required for latest async features and type hints
  - Greenlet 3.0+: Compatible with SQLAlchemy 2.0+ async mode

## Security Considerations

All dependencies are:
- ✅ Actively maintained with recent releases
- ✅ Popular packages with large user bases
- ✅ No known security vulnerabilities in specified versions
- ✅ Regular security updates through dependency updates

Update dependencies regularly:
```bash
poetry update  # With Poetry
pip install --upgrade -e ".[dev]"  # With pip
```