"""Search module for the Swagger MCP Server.

This module provides comprehensive search functionality including:
- BM25-based search index management
- Full-text search across API endpoints and documentation
- Relevance ranking and result optimization
- Index creation, updates, and maintenance

Main components:
- SearchIndexManager: Core index management and operations
- SearchEngine: High-level search interface
- IndexSchema: Search index structure definition
- SearchConfig: Search system configuration
"""

from .search_engine import SearchEngine
from .index_manager import SearchIndexManager
from .index_schema import IndexSchema, create_search_schema
from .relevance import RelevanceRanker

__all__ = [
    "SearchEngine",
    "SearchIndexManager",
    "IndexSchema",
    "create_search_schema",
    "RelevanceRanker",
]