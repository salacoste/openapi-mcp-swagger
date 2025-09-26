# Contributing to Universal Swagger → MCP Server Converter

Thank you for your interest in contributing! This guide will help you get started with contributing to the project.

## 🚀 Quick Start for Contributors

### 1. Development Environment Setup

```bash
# Fork and clone the repository
git clone https://github.com/YOUR_USERNAME/swagger-mcp-server.git
cd swagger-mcp-server

# Install Poetry (if not already installed)
curl -sSL https://install.python-poetry.org | python3 -

# Install dependencies
poetry install --with dev
poetry shell

# Install pre-commit hooks
pre-commit install
```

### 2. Verify Setup

```bash
# Run tests to ensure everything works
pytest

# Run linting
black src/ && isort src/ && flake8 src/ && mypy src/swagger_mcp_server/
```

## 📋 Development Guidelines

### Code Style and Standards

We follow strict coding standards to maintain high code quality:

#### Python Style
- **Formatter**: Black with 88-character line length
- **Import sorting**: isort with Black compatibility
- **Linting**: Flake8 with docstring and type-checking plugins
- **Type checking**: MyPy in strict mode

#### Code Quality Requirements
- **Test Coverage**: Minimum 80%, target 85%+
- **Type Hints**: Required for all public functions and methods
- **Documentation**: Comprehensive docstrings for public APIs
- **Performance**: Meet response time requirements (<200ms search, <500ms schema)

### Testing Standards

#### Test Structure
```
src/tests/
├── unit/              # Unit tests (80%+ coverage)
├── integration/       # Integration tests
├── fixtures/          # Test data and utilities
└── conftest.py        # Pytest configuration
```

#### Test Categories
- **Unit tests**: Test individual functions/classes in isolation
- **Integration tests**: Test component interactions
- **Performance tests**: Validate response time requirements
- **End-to-end tests**: Full MCP server workflow testing

#### Writing Tests
```python
# Good test naming
def test_parse_large_swagger_file_handles_10mb_within_memory_limits():
    """Test that parser handles 10MB files within 2GB RAM limit."""

# Use appropriate markers
@pytest.mark.unit
@pytest.mark.performance
def test_search_endpoints_response_time_under_200ms():
    """Test search response time meets NFR1 requirement."""
```

### Git Workflow

#### Branch Naming
- **Feature**: `feat/streaming-parser`
- **Bugfix**: `fix/search-performance`
- **Documentation**: `docs/contributing-guide`
- **Hotfix**: `hotfix/memory-leak`

#### Commit Messages
We follow [Conventional Commits](https://www.conventionalcommits.org/):

```bash
# Features
feat(parser): add streaming JSON parser for large swagger files

# Bug fixes
fix(search): resolve memory leak in BM25 ranking algorithm

# Documentation
docs(readme): update installation instructions

# Performance improvements
perf(search): optimize database queries for sub-200ms response

# Breaking changes
feat(api)!: change MCP method signatures for v2.0 compatibility
```

#### Pull Request Process

1. **Create feature branch**: `git checkout -b feat/my-feature`
2. **Make changes with tests**: Ensure new code has appropriate test coverage
3. **Run full test suite**: `pytest --cov=swagger_mcp_server`
4. **Run linting**: `black src/ && isort src/ && flake8 src/ && mypy src/swagger_mcp_server/`
5. **Update documentation**: Update README.md or docs/ if needed
6. **Commit changes**: Use conventional commit format
7. **Push and create PR**: Include description and reference any issues

### Pull Request Requirements

#### Checklist
- [ ] All tests pass (`pytest`)
- [ ] Code coverage maintains 80%+ (`pytest --cov`)
- [ ] Linting passes (Black, isort, Flake8, MyPy)
- [ ] Type hints added for public APIs
- [ ] Documentation updated if needed
- [ ] Performance requirements validated
- [ ] Security considerations addressed

#### PR Description Template
```markdown
## Description
Brief description of changes and motivation.

## Type of Change
- [ ] Bug fix (non-breaking change that fixes an issue)
- [ ] New feature (non-breaking change that adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Documentation update

## Testing
- [ ] Unit tests added/updated
- [ ] Integration tests added/updated
- [ ] Performance tests validate requirements
- [ ] All tests pass

## Performance Impact
Describe any performance implications and validation.

## Security Considerations
Describe any security implications.

Closes #[issue_number]
```

## 🏗️ Architecture Guidelines

### Component Design Principles

#### Parser Module
- **Stream-based processing**: Use ijson for memory-efficient parsing
- **Error resilience**: Handle malformed JSON gracefully
- **Progress reporting**: Support progress callbacks for large files
- **OpenAPI compliance**: Validate against OpenAPI 3.x specification

#### Storage Module
- **Repository pattern**: Separate data access logic
- **Query optimization**: Ensure sub-200ms response times
- **Migration support**: Version database schema properly
- **Connection management**: Handle concurrent access

#### Server Module
- **MCP compliance**: Follow MCP protocol specifications exactly
- **Async/await**: Use async patterns for all I/O operations
- **Error handling**: Provide descriptive error messages
- **Logging**: Structure logs for debugging and monitoring

### Performance Guidelines

#### Memory Management
- **Stream processing**: Never load entire files into memory
- **Connection pooling**: Reuse database connections
- **Resource cleanup**: Always close resources properly
- **Memory limits**: Stay within 2GB for 10MB file processing

#### Response Time Requirements
- **Search endpoints**: < 200ms target, < 500ms maximum
- **Schema retrieval**: < 500ms target, < 1s maximum
- **Code generation**: < 1s for all formats

## 🔒 Security Guidelines

### Input Validation
- **File size limits**: Enforce 10MB maximum for swagger files
- **Content validation**: Verify file types and sanitize paths
- **Parameter validation**: Use Pydantic models for all inputs
- **SQL injection prevention**: Use parameterized queries

### Logging Security
- **No sensitive data**: Never log API keys, tokens, or credentials
- **Structured logging**: Use consistent, machine-readable formats
- **Log levels**: Appropriate levels for different information types
- **Log rotation**: Implement proper log rotation policies

## 🤖 AI Agent Integration

### MCP Method Implementation
When implementing new MCP methods:

1. **Parameter validation**: Use Pydantic models
2. **Error handling**: Return proper MCP error responses
3. **Documentation**: Include method description and examples
4. **Testing**: Test with actual MCP clients
5. **Performance**: Validate response time requirements

### Search Implementation
- **Relevance ranking**: Use BM25 for semantic relevance
- **Filtering**: Support HTTP method and tag filtering
- **Pagination**: Handle large result sets appropriately
- **Caching**: Cache frequent searches

## 📚 Documentation Standards

### Code Documentation
- **Public APIs**: Comprehensive docstrings with examples
- **Type hints**: Full typing for better IDE support
- **Inline comments**: Explain complex logic, not obvious code
- **Architecture notes**: Document design decisions

### User Documentation
- **API examples**: cURL and code samples for all methods
- **Configuration**: Document all environment variables
- **Deployment**: Step-by-step deployment guides
- **Troubleshooting**: Common issues and solutions

## 🐛 Bug Reports and Feature Requests

### Bug Reports
Please include:
- **Description**: Clear description of the bug
- **Reproduction**: Steps to reproduce the issue
- **Expected behavior**: What should happen
- **Environment**: Python version, OS, relevant dependencies
- **Logs**: Any relevant error messages or logs

### Feature Requests
Please include:
- **Use case**: Why is this feature needed?
- **Proposed solution**: How should it work?
- **Alternatives**: Other approaches considered
- **Implementation**: Any implementation ideas

## 💬 Community and Communication

- **Discussions**: Use GitHub Discussions for questions and ideas
- **Issues**: Use GitHub Issues for bugs and feature requests
- **Pull Requests**: For code contributions
- **Code Review**: All PRs require at least one reviewer approval

Thank you for contributing to Universal Swagger → MCP Server Converter!