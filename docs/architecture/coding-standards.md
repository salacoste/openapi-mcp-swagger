# Coding Standards - Universal Swagger → MCP Server Converter

## Code Style & Formatting

### Language Standards
- **Python**: Follow PEP 8 with black formatter (line length: 88 characters)
- **TypeScript/Node.js**: Prettier + ESLint with Airbnb config
- **SQL**: Uppercase keywords, snake_case for tables/columns

### General Principles
- **Clear naming**: Use descriptive variable/function names (`parse_swagger_endpoints` vs `parse`)
- **Single responsibility**: Each function/class should have one clear purpose
- **Early returns**: Prefer early returns over deep nesting
- **Type safety**: Strict typing in all languages (TypeScript strict mode, Python type hints)

## Error Handling

### Exception Patterns
```python
# Good: Specific exceptions with context
class SwaggerParseError(Exception):
    def __init__(self, message: str, file_path: str, line_number: int = None):
        self.message = message
        self.file_path = file_path
        self.line_number = line_number
        super().__init__(f"Swagger parse error in {file_path}: {message}")
```

### Error Response Standards
- **Validation errors**: Return 400 with specific field errors
- **Resource not found**: Return 404 with resource identifier
- **Internal errors**: Return 500 with generic message, log detailed error
- **MCP errors**: Use proper MCP error codes and messages

## Testing Standards

### Test Structure
- **Unit tests**: 80%+ coverage minimum for core parsing logic
- **Integration tests**: Full MCP server workflow testing
- **Performance tests**: Response time validation (<200ms search, <500ms schema)

### Test Naming
```python
def test_parse_large_swagger_file_performance():
    """Test that 5MB+ swagger files parse within 2 seconds"""

def test_search_endpoints_returns_relevant_results():
    """Test BM25 search returns endpoints matching keywords"""
```

## Documentation Standards

### Code Comments
- **Function docstrings**: Required for all public functions
- **Complex logic**: Inline comments explaining "why", not "what"
- **API changes**: Include version notes in breaking changes

### README Requirements
- **Quick start**: 5-minute setup guide
- **API examples**: cURL and code samples for all MCP methods
- **Configuration**: All environment variables and config options

## Security Standards

### Input Validation
- **Sanitize all inputs**: Prevent injection attacks
- **File size limits**: 10MB max for swagger files
- **Rate limiting**: 100 requests/minute per client

### Data Handling
- **No sensitive data logging**: Redact API keys, tokens
- **Secure file handling**: Validate file types, sanitize paths
- **Memory management**: Streaming for large files, cleanup resources

## Performance Standards

### Response Times
- **Search endpoints**: <200ms target, <500ms maximum
- **Get schema**: <500ms target, <1s maximum
- **Parse swagger**: <2s for files up to 5MB

### Memory Usage
- **Streaming parsing**: No full file loading into memory
- **Database connections**: Connection pooling with max 10 connections
- **Cache strategy**: LRU cache for frequently accessed schemas

## Git Workflow

### Commit Messages
```
feat(parser): add streaming JSON parser for large swagger files

- Implement ijson-based streaming parser
- Add memory usage tests for 10MB+ files
- Reduces memory footprint by 80%

Closes #123
```

### Branch Naming
- **Feature**: `feat/streaming-parser`
- **Bugfix**: `fix/search-performance`
- **Hotfix**: `hotfix/memory-leak`

### PR Requirements
- **Tests passing**: All CI checks green
- **Code review**: At least 1 reviewer approval
- **Documentation**: Update docs for API changes