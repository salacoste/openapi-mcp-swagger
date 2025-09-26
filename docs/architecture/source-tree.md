# Source Tree Structure - Universal Swagger → MCP Server Converter

## Project Root Structure

```
bmad-openapi-mcp-server/
├── src/                          # Main source code
│   ├── swagger_mcp_server/       # Main package
│   │   ├── __init__.py
│   │   ├── main.py              # Entry point & CLI
│   │   ├── server.py            # MCP server implementation
│   │   ├── parser/              # Swagger parsing module
│   │   ├── storage/             # Database operations
│   │   ├── search/              # Search implementation
│   │   ├── examples/            # Code example generation
│   │   └── config/              # Configuration handling
│   └── tests/                   # Test suite (mirrors src structure)
├── docs/                        # Documentation
├── scripts/                     # Build and utility scripts
├── data/                        # Sample swagger files & fixtures
├── .bmad-core/                  # BMAD-METHOD framework
├── pyproject.toml               # Poetry configuration
├── README.md                    # Project documentation
└── CHANGELOG.md                 # Version history
```

## Source Code Organization

### Core Package: `src/swagger_mcp_server/`

#### `main.py` - CLI Entry Point
```python
# Command-line interface and application bootstrap
- CLI command definitions (click)
- Configuration loading
- Server lifecycle management
- Error handling and logging setup
```

#### `server.py` - MCP Server Implementation
```python
# Core MCP protocol server
- MCP server class implementation
- Request routing and validation
- Method implementations:
  - searchEndpoints()
  - getSchema()
  - getExample()
- Error handling and responses
```

### Parser Module: `src/swagger_mcp_server/parser/`

```
parser/
├── __init__.py
├── base.py                      # Base parser interface
├── swagger_parser.py            # Main swagger/OpenAPI parser
├── stream_parser.py             # Streaming JSON parser
├── normalization.py             # Data normalization
└── validation.py                # Schema validation
```

**Responsibilities**:
- Stream-based parsing of large JSON files
- OpenAPI/Swagger spec validation
- Data structure normalization
- Error recovery and reporting

### Storage Module: `src/swagger_mcp_server/storage/`

```
storage/
├── __init__.py
├── database.py                  # Database connection management
├── models.py                    # SQLite schema definitions
├── migrations.py                # Database migrations
├── repositories/                # Data access layer
│   ├── __init__.py
│   ├── endpoint_repository.py
│   ├── schema_repository.py
│   └── metadata_repository.py
└── queries/                     # SQL queries
    ├── __init__.py
    ├── search_queries.sql
    └── schema_queries.sql
```

**Responsibilities**:
- SQLite database management
- CRUD operations for all entities
- Query optimization
- Connection pooling

### Search Module: `src/swagger_mcp_server/search/`

```
search/
├── __init__.py
├── search_engine.py             # Main search interface
├── bm25_ranker.py              # BM25 ranking implementation
├── fts_search.py               # SQLite FTS5 search
├── query_parser.py             # Search query parsing
└── relevance.py                # Relevance scoring
```

**Responsibilities**:
- Hybrid search implementation
- Query parsing and optimization
- Relevance ranking
- Search result formatting

### Examples Module: `src/swagger_mcp_server/examples/`

```
examples/
├── __init__.py
├── code_generator.py           # Main code generation interface
├── generators/                 # Language-specific generators
│   ├── __init__.py
│   ├── curl_generator.py
│   ├── javascript_generator.py
│   ├── python_generator.py
│   └── typescript_generator.py
└── templates/                  # Code templates
    ├── curl.j2
    ├── javascript.j2
    ├── python.j2
    └── typescript.j2
```

**Responsibilities**:
- Multi-language code example generation
- Template-based code generation
- Parameter substitution
- Output formatting

### Configuration Module: `src/swagger_mcp_server/config/`

```
config/
├── __init__.py
├── settings.py                 # Configuration classes
├── defaults.py                 # Default configuration
└── validation.py               # Config validation
```

**Responsibilities**:
- Configuration loading and validation
- Environment variable handling
- Default value management
- Configuration schema definition

## Test Structure: `src/tests/`

```
tests/
├── __init__.py
├── conftest.py                 # Pytest configuration & fixtures
├── unit/                       # Unit tests (mirror src structure)
│   ├── test_parser/
│   ├── test_storage/
│   ├── test_search/
│   ├── test_examples/
│   └── test_config/
├── integration/                # Integration tests
│   ├── test_mcp_server.py
│   ├── test_full_workflow.py
│   └── test_performance.py
├── fixtures/                   # Test data
│   ├── swagger_files/
│   ├── expected_outputs/
│   └── mock_responses/
└── utils/                      # Test utilities
    ├── __init__.py
    ├── test_helpers.py
    └── mock_factories.py
```

## Documentation Structure: `docs/`

```
docs/
├── architecture/               # Architecture documentation
│   ├── coding-standards.md
│   ├── tech-stack.md
│   ├── source-tree.md          # This file
│   └── deployment.md
├── api/                       # API documentation
│   ├── mcp-methods.md
│   └── examples.md
├── development/               # Development guides
│   ├── setup.md
│   ├── testing.md
│   └── contributing.md
├── prd/                      # Product requirements (BMAD sharded)
└── brief/                    # Project briefs
```

## Configuration Files

### `pyproject.toml` - Project Configuration
```toml
# Poetry dependency management
# Build system configuration
# Tool configurations (black, isort, mypy, pytest)
# Entry points and scripts
```

### `.gitignore` - Version Control
```
# Python artifacts
__pycache__/
*.pyc
*.pyo
.coverage
htmlcov/

# Virtual environments
venv/
.env

# IDE files
.vscode/
.idea/

# Build artifacts
dist/
build/
*.egg-info/

# Local data
data/local/
*.db
logs/
```

## Build and Scripts: `scripts/`

```
scripts/
├── build.sh                   # Build and packaging
├── test.sh                    # Test runner
├── lint.sh                    # Code quality checks
├── setup-dev.sh              # Development environment setup
└── benchmark.sh              # Performance benchmarking
```

## Data and Fixtures: `data/`

```
data/
├── samples/                   # Sample swagger files
│   ├── petstore.json         # Small example
│   ├── stripe.json           # Medium complexity
│   └── kubernetes.json       # Large, complex API
├── benchmarks/               # Performance test data
└── fixtures/                 # Test fixtures
```

## Key Design Principles

### Module Separation
- **Clear boundaries**: Each module has specific responsibilities
- **Dependency injection**: Modules depend on interfaces, not implementations
- **Testability**: Each module can be tested in isolation

### Scalability Considerations
- **Horizontal scaling**: Stateless design allows multiple instances
- **Resource efficiency**: Streaming parsing prevents memory bloat
- **Cache-friendly**: Clear caching boundaries at repository level

### Maintainability Features
- **Type hints**: Full typing for better IDE support
- **Documentation**: Comprehensive docstrings
- **Error handling**: Consistent error handling patterns
- **Logging**: Structured logging throughout