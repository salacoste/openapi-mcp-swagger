# MVP Scope

## Core Features (Must Have)

- **Universal Swagger Parser:** Stream-based JSON processor that handles OpenAPI/Swagger files from 1KB to 10MB+ without memory constraints. Normalizes API structure while preserving endpoint-to-schema relationships essential for AI understanding.

- **Semantic Storage Engine:** SQLite-based storage with intelligent indexing that maintains OpenAPI semantic relationships. Stores endpoints, schemas, components, and security definitions in queryable format optimized for MCP protocol serving.

- **MCP Protocol Server:** Standards-compliant MCP server implementation with three core methods:
  - `searchEndpoints(keywords, httpMethods)` - Returns filtered endpoint list with descriptions
  - `getSchema(componentName)` - Retrieves complete schema definitions with dependencies
  - `getExample(endpoint, format)` - Generates working code examples in cURL, JavaScript fetch, Python requests

- **Basic Search & Indexing:** BM25-based text search across endpoint paths, descriptions, and parameter names. Enables intelligent endpoint discovery beyond simple keyword matching.

- **CLI Installation & Setup:** Simple command-line interface for installing, configuring, and running MCP servers from Swagger files. One-command deployment for developer adoption.

## Out of Scope for MVP

- Advanced vector search or semantic similarity matching
- Web-based UI for API exploration (focus on AI agent consumption)
- Support for GraphQL, gRPC, or non-OpenAPI specifications
- Real-time API monitoring or health checking
- Authentication/authorization for MCP server access
- Multi-tenant or enterprise deployment features
- Custom code generation templates beyond the three standard formats

## MVP Success Criteria

The MVP succeeds when a developer can: (1) Install the tool via single CLI command, (2) Convert any Swagger file (tested up to 2MB) into a functioning MCP server in <60 seconds, (3) Use AI coding assistants to successfully query endpoints, retrieve schemas, and generate working API integration code, (4) Complete a typical API integration task 50%+ faster than manual documentation approach.
