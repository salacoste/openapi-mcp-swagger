# Technology Stack - Universal Swagger → MCP Server Converter

## Core Technologies

### Runtime & Language
**Python 3.11+** - Primary implementation language
- **Rationale**:
  - Excellent JSON/streaming support (ijson)
  - Rich ecosystem for text search (Whoosh, rank_bm25)
  - Strong MCP Python SDK support
  - Mature async/await for concurrent requests
- **Key Libraries**:
  - `asyncio` - Async MCP server implementation
  - `ijson` - Streaming JSON parsing for large files
  - `pydantic` - Data validation and serialization
  - `click` - CLI interface

### Database & Storage
**SQLite 3.38+** - Primary data storage
- **Rationale**:
  - Zero-configuration deployment
  - Excellent full-text search (FTS5)
  - ACID transactions
  - Cross-platform compatibility
  - Handles concurrent reads efficiently
- **Schema Design**:
  - `endpoints` table with FTS5 index
  - `schemas` table for component definitions
  - `metadata` table for swagger file info

### Search Engine
**Hybrid Approach**: SQLite FTS5 + Python rank_bm25
- **SQLite FTS5**: Fast keyword matching and ranking
- **rank_bm25**: Advanced BM25 scoring for relevance
- **Combined Strategy**: FTS5 for initial filtering, BM25 for final ranking

### MCP Implementation
**MCP Python SDK 1.0+**
- **Server Implementation**: `mcp` package
- **Transport**: stdio-based communication
- **Methods**:
  - `searchEndpoints` - Endpoint discovery
  - `getSchema` - Schema retrieval
  - `getExample` - Code generation

## Development Tools

### Code Quality
- **Black**: Code formatting (line-length: 88)
- **isort**: Import sorting
- **flake8**: Linting with plugins:
  - `flake8-docstrings` - Docstring validation
  - `flake8-type-checking` - Type hint validation
- **mypy**: Static type checking (strict mode)

### Testing Framework
- **pytest**: Primary testing framework
- **pytest-asyncio**: Async test support
- **pytest-benchmark**: Performance testing
- **faker**: Test data generation
- **coverage.py**: Code coverage reporting (85%+ target)

### Build & Packaging
- **Poetry**: Dependency management and packaging
- **pyproject.toml**: Modern Python packaging
- **GitHub Actions**: CI/CD pipeline
- **Docker**: Optional containerized deployment

## Infrastructure & Deployment

### Local Development
- **Python venv**: Isolated development environment
- **pre-commit**: Git hooks for code quality
- **tox**: Multi-version testing

### Production Deployment
- **Standalone Python**: Direct installation
- **Docker**: Containerized deployment (optional)
- **systemd**: Service management on Linux
- **Homebrew**: macOS installation

### Configuration Management
- **TOML**: Configuration file format
- **Environment variables**: Runtime overrides
- **CLI flags**: Command-line configuration

## Performance Architecture

### Memory Management
- **Streaming parsing**: ijson for large file processing
- **Connection pooling**: SQLite connection management
- **LRU cache**: functools.lru_cache for frequently accessed data
- **Lazy loading**: Load schemas only when requested

### Concurrency Model
- **asyncio**: Single-threaded async I/O
- **Connection pool**: Shared SQLite connections
- **Request queuing**: Fair scheduling for concurrent requests
- **Backpressure**: Rate limiting to prevent resource exhaustion

### Database Optimization
- **Indexes**: Compound indexes for search queries
- **Prepared statements**: Query plan caching
- **WAL mode**: Write-Ahead Logging for better concurrency
- **PRAGMA optimizations**: Performance tuning

## Security Considerations

### Input Validation
- **File size limits**: 10MB maximum swagger files
- **Schema validation**: Pydantic models for all inputs
- **Path sanitization**: Prevent directory traversal
- **Content-Type validation**: Ensure JSON/YAML inputs

### Runtime Security
- **No shell execution**: Pure Python implementation
- **Sandboxed parsing**: Isolated JSON parsing
- **Resource limits**: Memory and CPU constraints
- **Logging security**: No sensitive data in logs

## Monitoring & Observability

### Logging
- **structlog**: Structured logging
- **Log levels**: DEBUG, INFO, WARNING, ERROR
- **Log rotation**: Daily rotation with 30-day retention
- **Performance logs**: Query timing and resource usage

### Metrics
- **Response times**: P50, P95, P99 percentiles
- **Error rates**: By endpoint and error type
- **Resource usage**: Memory and disk consumption
- **Search relevance**: Click-through rates (if applicable)

## Alternative Technologies Considered

### Language Alternatives
- **Node.js/TypeScript**: Rejected due to weaker text search libraries
- **Go**: Rejected due to less mature MCP ecosystem
- **Rust**: Rejected for development speed concerns

### Database Alternatives
- **PostgreSQL**: Overkill for single-user deployment
- **DuckDB**: Considered but SQLite FTS5 is more mature
- **Elasticsearch**: Too heavy for local deployment

### Search Alternatives
- **Whoosh**: Pure Python but slower than SQLite FTS5
- **Tantivy**: Rust-based, rejected for complexity
- **Vector search**: Overkill for keyword-based API search