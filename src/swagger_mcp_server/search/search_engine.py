"""High-level search engine interface for the Swagger MCP Server.

This module provides the SearchEngine class which serves as the main
interface for search operations, combining Whoosh indexing with
BM25 ranking for optimal search results.
"""

from typing import Dict, Any, List, Optional, Union
import asyncio
from dataclasses import dataclass

from whoosh.qparser import QueryParser, MultifieldParser, OrGroup
from whoosh.query import Query, Term, And, Or
from whoosh import scoring

from .index_manager import SearchIndexManager
from .relevance import RelevanceRanker
from .query_processor import QueryProcessor, ProcessedQuery, QuerySuggestion
from .result_processor import ResultProcessor, EnhancedSearchResult
from ..config.settings import SearchConfig


@dataclass
class SearchResult:
    """Represents a single search result."""
    endpoint_id: str
    endpoint_path: str
    http_method: str
    summary: str
    description: str
    score: float
    highlights: Dict[str, str]
    metadata: Dict[str, Any]


@dataclass
class SearchResponse:
    """Complete search response with results and metadata."""
    results: List[SearchResult]
    total_results: int
    query_time: float
    query: str
    page: int
    per_page: int
    has_more: bool
    metadata: Optional[Dict[str, Any]] = None


class SearchEngine:
    """High-level search engine providing comprehensive search capabilities."""

    def __init__(
        self,
        index_manager: SearchIndexManager,
        config: SearchConfig,
    ):
        """Initialize the search engine.

        Args:
            index_manager: Search index manager instance
            config: Search configuration settings
        """
        self.index_manager = index_manager
        self.config = config
        self.relevance_ranker = RelevanceRanker(config)
        self.query_processor = QueryProcessor(config)
        self.result_processor = ResultProcessor(config)

        # Create query parsers
        self._setup_query_parsers()

    def _setup_query_parsers(self) -> None:
        """Set up query parsers for different search scenarios."""
        schema = self.index_manager.index.schema

        # Main multifield parser for general search
        self.multifield_parser = MultifieldParser(
            ["endpoint_path", "summary", "description", "parameters", "tags"],
            schema,
            group=OrGroup.factory(0.9)  # Slight preference for OR matching
        )

        # Specific field parsers
        self.path_parser = QueryParser("endpoint_path", schema)
        self.description_parser = QueryParser("description", schema)
        self.parameter_parser = QueryParser("parameters", schema)

    async def search(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        page: int = 1,
        per_page: int = 20,
        sort_by: Optional[str] = None,
        include_highlights: bool = True,
    ) -> SearchResponse:
        """Perform a comprehensive search across the API documentation.

        Args:
            query: Search query string
            filters: Optional filters to apply (e.g., {"http_method": "GET"})
            page: Page number (1-based)
            per_page: Results per page
            sort_by: Sort field (default: relevance)
            include_highlights: Whether to include result highlights

        Returns:
            SearchResponse: Complete search response with results and metadata

        Raises:
            ValueError: If query is empty or invalid parameters
            RuntimeError: If search operation fails
        """
        if not query.strip():
            raise ValueError("Search query cannot be empty")

        if page < 1:
            raise ValueError("Page number must be >= 1")

        if per_page < 1 or per_page > self.config.performance.max_search_results:
            raise ValueError(
                f"per_page must be between 1 and {self.config.performance.max_search_results}"
            )

        start_time = asyncio.get_event_loop().time()

        try:
            # Process query with advanced query processor
            processed_query = await self.query_processor.process_query(query)

            # Get schema fields for query generation
            schema_fields = list(self.index_manager.index.schema.names())

            # Generate Whoosh query from processed components
            parsed_query = self.query_processor.generate_whoosh_query(
                processed_query, schema_fields
            )

            # Apply additional filters if provided
            if filters:
                parsed_query = self._apply_filters(parsed_query, filters)

            # Execute search
            results = await self._execute_search(
                parsed_query,
                page,
                per_page,
                sort_by,
                include_highlights
            )

            query_time = asyncio.get_event_loop().time() - start_time

            # Generate query suggestions if needed
            suggestions = []
            if results["total"] < 10:  # Low result count
                available_terms = self._get_available_terms()
                suggestions = await self.query_processor.generate_query_suggestions(
                    query, results["total"], available_terms
                )

            search_response = SearchResponse(
                results=results["hits"],
                total_results=results["total"],
                query_time=query_time,
                query=query,
                page=page,
                per_page=per_page,
                has_more=results["total"] > (page * per_page)
            )

            # Add suggestions to metadata if available
            if suggestions:
                search_response.metadata = {
                    "suggestions": [
                        {
                            "query": s.query,
                            "description": s.description,
                            "category": s.category
                        }
                        for s in suggestions
                    ]
                }

            return search_response

        except Exception as e:
            raise RuntimeError(f"Search operation failed: {e}") from e

    async def search_advanced(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        page: int = 1,
        per_page: int = 20,
        sort_by: Optional[str] = None,
        include_organization: bool = True,
        include_metadata: bool = True,
    ) -> Dict[str, Any]:
        """Perform advanced search with result optimization and filtering.

        Args:
            query: Search query string
            filters: Advanced filtering criteria
            page: Page number (1-based)
            per_page: Results per page
            sort_by: Sort field (default: relevance)
            include_organization: Whether to include result organization
            include_metadata: Whether to include enhanced metadata

        Returns:
            Dict: Complete search response with enhanced results and metadata

        Raises:
            ValueError: If query is empty or invalid parameters
            RuntimeError: If search operation fails
        """
        if not query.strip():
            raise ValueError("Search query cannot be empty")

        if page < 1:
            raise ValueError("Page number must be >= 1")

        if per_page < 1 or per_page > self.config.performance.max_search_results:
            raise ValueError(
                f"per_page must be between 1 and {self.config.performance.max_search_results}"
            )

        start_time = asyncio.get_event_loop().time()

        try:
            # Process query with advanced query processor
            processed_query = await self.query_processor.process_query(query)

            # Get schema fields for query generation
            schema_fields = list(self.index_manager.index.schema.names())

            # Generate Whoosh query from processed components
            parsed_query = self.query_processor.generate_whoosh_query(
                processed_query, schema_fields
            )

            # Apply additional filters if provided
            if filters and "basic_filters" in filters:
                parsed_query = self._apply_filters(parsed_query, filters["basic_filters"])

            # Execute search to get raw results
            raw_results = await self._execute_search_raw(
                parsed_query,
                page=1,  # Get all results for processing
                per_page=1000,  # Large limit for initial fetch
                sort_by=sort_by
            )

            # Convert Whoosh results to dict format for processing
            raw_results_list = []
            for hit in raw_results["hits"]:
                raw_result = {
                    "endpoint_id": hit.endpoint_id,
                    "endpoint_path": hit.endpoint_path,
                    "http_method": hit.http_method,
                    "summary": hit.summary,
                    "description": hit.description,
                    "score": hit.score,
                    "tags": ",".join(hit.metadata.get("tags", "").split()),
                    "deprecated": hit.metadata.get("deprecated", False),
                    "parameters": hit.metadata.get("parameters", ""),
                    "security": hit.metadata.get("security", {}),
                    "responses": hit.metadata.get("responses", {}),
                }
                raw_results_list.append(raw_result)

            # Process results with advanced result processor
            processed_results = await self.result_processor.process_search_results(
                raw_results_list,
                query,
                filters=filters,
                pagination={"page": page, "per_page": per_page}
            )

            # Add query processing metadata
            query_time = asyncio.get_event_loop().time() - start_time
            processed_results["query_time"] = query_time
            processed_results["query"] = query
            processed_results["processed_query_info"] = {
                "query_type": processed_query.query_type,
                "field_filters": processed_query.field_filters,
                "boolean_operators": processed_query.boolean_operators,
                "enhanced_terms": len(processed_query.enhanced_terms)
            }

            # Add query suggestions if needed
            if processed_results.get("summary", {}).get("filtered_results", 0) < 10:
                available_terms = self._get_available_terms()
                suggestions = await self.query_processor.generate_query_suggestions(
                    query, processed_results["summary"]["filtered_results"], available_terms
                )
                processed_results["suggestions"] = [
                    {
                        "query": s.query,
                        "description": s.description,
                        "category": s.category
                    }
                    for s in suggestions
                ]

            return processed_results

        except Exception as e:
            raise RuntimeError(f"Advanced search operation failed: {e}") from e

    async def search_by_path(
        self,
        path_pattern: str,
        http_methods: Optional[List[str]] = None,
        exact_match: bool = False,
    ) -> List[SearchResult]:
        """Search for endpoints by path pattern.

        Args:
            path_pattern: Path pattern to search for
            http_methods: Optional list of HTTP methods to filter by
            exact_match: Whether to use exact path matching

        Returns:
            List[SearchResult]: Matching endpoints ordered by relevance
        """
        try:
            if exact_match:
                query = Term("endpoint_path", path_pattern)
            else:
                query = self.path_parser.parse(path_pattern)

            # Add HTTP method filter if specified
            if http_methods:
                method_queries = [
                    Term("http_method", method.upper()) for method in http_methods
                ]
                method_filter = Or(method_queries)
                query = And([query, method_filter])

            results = await self._execute_search(query, 1, 100, include_highlights=False)
            return results["hits"]

        except Exception as e:
            raise RuntimeError(f"Path search failed: {e}") from e

    async def search_by_tag(
        self,
        tags: Union[str, List[str]],
        additional_query: Optional[str] = None,
    ) -> List[SearchResult]:
        """Search for endpoints by tags.

        Args:
            tags: Tag or list of tags to search for
            additional_query: Optional additional search query

        Returns:
            List[SearchResult]: Matching endpoints ordered by relevance
        """
        try:
            if isinstance(tags, str):
                tags = [tags]

            # Create tag queries
            tag_queries = [Term("tags", tag) for tag in tags]
            tag_query = Or(tag_queries) if len(tag_queries) > 1 else tag_queries[0]

            # Combine with additional query if provided
            if additional_query:
                text_query = self.multifield_parser.parse(additional_query)
                final_query = And([tag_query, text_query])
            else:
                final_query = tag_query

            results = await self._execute_search(final_query, 1, 100, include_highlights=True)
            return results["hits"]

        except Exception as e:
            raise RuntimeError(f"Tag search failed: {e}") from e

    async def suggest_queries(self, partial_query: str, limit: int = 10) -> List[str]:
        """Get query suggestions based on partial input.

        Args:
            partial_query: Partial query string
            limit: Maximum number of suggestions

        Returns:
            List[str]: List of suggested queries
        """
        # This is a placeholder implementation
        # In a full implementation, this would use term frequency analysis
        # or a dedicated suggestion index
        suggestions = []

        try:
            # Simple implementation: find terms that start with the partial query
            reader = self.index_manager.index.reader()

            for field_name in ["endpoint_path", "summary", "description", "tags"]:
                terms = reader.field_terms(field_name)
                for term in terms:
                    if term.startswith(partial_query.lower()) and term not in suggestions:
                        suggestions.append(term)
                        if len(suggestions) >= limit:
                            break
                if len(suggestions) >= limit:
                    break

            return sorted(suggestions[:limit])

        except Exception:
            return []

    # Private methods

    def _parse_search_query(self, query: str) -> Query:
        """Parse the search query string into a Whoosh Query object.

        Args:
            query: Raw search query string

        Returns:
            Query: Parsed Whoosh query
        """
        try:
            # Use multifield parser for general queries
            return self.multifield_parser.parse(query)
        except Exception:
            # Fallback to simple term search if parsing fails
            return Term("description", query.lower())

    def _apply_filters(self, base_query: Query, filters: Dict[str, Any]) -> Query:
        """Apply filters to the base search query.

        Args:
            base_query: Base search query
            filters: Filter criteria

        Returns:
            Query: Query with filters applied
        """
        filter_queries = []

        for field, value in filters.items():
            if isinstance(value, list):
                # Multiple values for the same field (OR condition)
                field_queries = [Term(field, str(v)) for v in value]
                filter_queries.append(Or(field_queries))
            else:
                # Single value
                filter_queries.append(Term(field, str(value)))

        if filter_queries:
            return And([base_query] + filter_queries)

        return base_query

    async def _execute_search(
        self,
        query: Query,
        page: int = 1,
        per_page: int = 20,
        sort_by: Optional[str] = None,
        include_highlights: bool = True,
    ) -> Dict[str, Any]:
        """Execute the search query and return results.

        Args:
            query: Parsed search query
            page: Page number
            per_page: Results per page
            sort_by: Sort field
            include_highlights: Whether to include highlights

        Returns:
            Dict containing hits, total count, and metadata
        """
        with self.index_manager.index.searcher(weighting=scoring.BM25F()) as searcher:
            # Calculate offset for pagination
            offset = (page - 1) * per_page

            # Execute search
            results = searcher.search_page(
                query,
                pagenum=page,
                pagelen=per_page,
                sortedby=sort_by
            )

            # Convert results to SearchResult objects
            hits = []
            for hit in results:
                search_result = SearchResult(
                    endpoint_id=hit["endpoint_id"],
                    endpoint_path=hit.get("endpoint_path", ""),
                    http_method=hit.get("http_method", ""),
                    summary=hit.get("summary", ""),
                    description=hit.get("description", ""),
                    score=hit.score if hasattr(hit, 'score') else 0.0,
                    highlights={},
                    metadata={
                        "operation_id": hit.get("operation_id", ""),
                        "tags": hit.get("tags", ""),
                        "deprecated": hit.get("deprecated", False),
                    }
                )

                # Add highlights if requested
                if include_highlights:
                    search_result.highlights = self._extract_highlights(hit, query)

                hits.append(search_result)

            return {
                "hits": hits,
                "total": len(results),
                "page": page,
                "per_page": per_page,
            }

    def _extract_highlights(self, hit: Any, query: Query) -> Dict[str, str]:
        """Extract highlighted text snippets from search hit.

        Args:
            hit: Search result hit
            query: Search query for highlighting

        Returns:
            Dict[str, str]: Field highlights
        """
        highlights = {}

        try:
            # Extract highlights for key fields
            highlight_fields = ["summary", "description", "parameters"]

            for field in highlight_fields:
                if hasattr(hit, 'highlights') and field in hit:
                    highlighted = hit.highlights(field)
                    if highlighted:
                        highlights[field] = highlighted
                elif field in hit and hit[field]:
                    # Fallback: truncate field content if no highlights available
                    content = str(hit[field])
                    if len(content) > 200:
                        highlights[field] = content[:197] + "..."
                    else:
                        highlights[field] = content

        except Exception:
            # If highlighting fails, continue without highlights
            pass

        return highlights

    def _get_available_terms(self) -> Optional[set]:
        """Get available terms from the search index for suggestions."""
        try:
            available_terms = set()
            reader = self.index_manager.index.reader()

            # Collect terms from main content fields
            content_fields = ["endpoint_path", "summary", "description", "tags"]
            for field_name in content_fields:
                if field_name in reader.schema:
                    terms = reader.field_terms(field_name)
                    available_terms.update(terms)

            return available_terms
        except Exception:
            return None

    async def _execute_search_raw(
        self,
        query: Query,
        page: int = 1,
        per_page: int = 20,
        sort_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute raw search query and return results without processing.

        Args:
            query: Parsed search query
            page: Page number
            per_page: Results per page
            sort_by: Sort field

        Returns:
            Dict containing raw search hits and metadata
        """
        return await self._execute_search(query, page, per_page, sort_by, include_highlights=True)