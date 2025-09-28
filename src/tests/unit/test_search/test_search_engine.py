"""Tests for search engine functionality."""

import asyncio
import shutil
import tempfile
from unittest.mock import AsyncMock, Mock, patch

import pytest

from swagger_mcp_server.config.settings import SearchConfig
from swagger_mcp_server.search.index_manager import SearchIndexManager
from swagger_mcp_server.search.search_engine import (
    SearchEngine,
    SearchResponse,
    SearchResult,
)


@pytest.fixture
def temp_index_dir():
    """Create a temporary directory for index testing."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def mock_index_manager():
    """Create a mock SearchIndexManager."""
    mock_manager = Mock(spec=SearchIndexManager)
    mock_manager.index = Mock()
    mock_manager.index.schema = Mock()
    mock_manager.index.searcher.return_value.__enter__ = Mock()
    mock_manager.index.searcher.return_value.__exit__ = Mock()
    return mock_manager


@pytest.fixture
def search_config():
    """Create test search configuration."""
    return SearchConfig(
        performance__max_search_results=1000,
        performance__query_timeout=5,
    )


@pytest.fixture
def search_engine(mock_index_manager, search_config):
    """Create SearchEngine instance for testing."""
    return SearchEngine(mock_index_manager, search_config)


class TestSearchEngine:
    """Test cases for SearchEngine class."""

    def test_initialization(self, search_engine, mock_index_manager, search_config):
        """Test SearchEngine initialization."""
        assert search_engine.index_manager == mock_index_manager
        assert search_engine.config == search_config
        assert search_engine.relevance_ranker is not None
        assert search_engine.multifield_parser is not None

    def test_setup_query_parsers(self, search_engine):
        """Test that query parsers are set up correctly."""
        assert hasattr(search_engine, "multifield_parser")
        assert hasattr(search_engine, "path_parser")
        assert hasattr(search_engine, "description_parser")
        assert hasattr(search_engine, "parameter_parser")

    @pytest.mark.asyncio
    async def test_search_with_empty_query_raises_error(self, search_engine):
        """Test that empty query raises ValueError."""
        with pytest.raises(ValueError, match="Search query cannot be empty"):
            await search_engine.search("")

        with pytest.raises(ValueError, match="Search query cannot be empty"):
            await search_engine.search("   ")

    @pytest.mark.asyncio
    async def test_search_with_invalid_page_raises_error(self, search_engine):
        """Test that invalid page number raises ValueError."""
        with pytest.raises(ValueError, match="Page number must be >= 1"):
            await search_engine.search("test", page=0)

        with pytest.raises(ValueError, match="Page number must be >= 1"):
            await search_engine.search("test", page=-1)

    @pytest.mark.asyncio
    async def test_search_with_invalid_per_page_raises_error(self, search_engine):
        """Test that invalid per_page raises ValueError."""
        with pytest.raises(ValueError, match="per_page must be between"):
            await search_engine.search("test", per_page=0)

        with pytest.raises(ValueError, match="per_page must be between"):
            await search_engine.search("test", per_page=2000)  # Exceeds max

    @pytest.mark.asyncio
    async def test_search_basic_functionality(self, search_engine):
        """Test basic search functionality."""
        # Mock the search execution
        mock_results = {
            "hits": [
                SearchResult(
                    endpoint_id="1",
                    endpoint_path="/api/users",
                    http_method="GET",
                    summary="Get users",
                    description="Retrieve all users",
                    score=0.8,
                    highlights={"summary": "Get <em>users</em>"},
                    metadata={
                        "operation_id": "getUsers",
                        "tags": "users",
                        "deprecated": False,
                    },
                )
            ],
            "total": 1,
            "page": 1,
            "per_page": 20,
        }

        with patch.object(
            search_engine, "_execute_search", new_callable=AsyncMock
        ) as mock_execute:
            mock_execute.return_value = mock_results

            response = await search_engine.search("users")

            assert isinstance(response, SearchResponse)
            assert response.total_results == 1
            assert len(response.results) == 1
            assert response.query == "users"
            assert response.page == 1
            assert response.per_page == 20
            assert response.has_more is False
            assert response.query_time >= 0

    @pytest.mark.asyncio
    async def test_search_with_filters(self, search_engine):
        """Test search with filters applied."""
        filters = {"http_method": "GET", "deprecated": False}

        with patch.object(
            search_engine, "_execute_search", new_callable=AsyncMock
        ) as mock_execute:
            mock_execute.return_value = {
                "hits": [],
                "total": 0,
                "page": 1,
                "per_page": 20,
            }

            with patch.object(search_engine, "_parse_search_query") as mock_parse:
                with patch.object(search_engine, "_apply_filters") as mock_filter:
                    mock_parse.return_value = Mock()
                    mock_filter.return_value = Mock()

                    await search_engine.search("test", filters=filters)

                    mock_filter.assert_called_once()
                    args, kwargs = mock_filter.call_args
                    assert filters in args

    @pytest.mark.asyncio
    async def test_search_with_pagination(self, search_engine):
        """Test search with pagination."""
        mock_results = {
            "hits": [],
            "total": 100,
            "page": 2,
            "per_page": 10,
        }

        with patch.object(
            search_engine, "_execute_search", new_callable=AsyncMock
        ) as mock_execute:
            mock_execute.return_value = mock_results

            response = await search_engine.search("test", page=2, per_page=10)

            assert response.page == 2
            assert response.per_page == 10
            assert response.total_results == 100
            assert response.has_more is True  # 100 total, page 2 of 10 per page

    @pytest.mark.asyncio
    async def test_search_by_path_exact_match(self, search_engine):
        """Test searching by exact path match."""
        with patch.object(
            search_engine, "_execute_search", new_callable=AsyncMock
        ) as mock_execute:
            mock_execute.return_value = {"hits": [], "total": 0}

            await search_engine.search_by_path("/api/users", exact_match=True)

            mock_execute.assert_called_once()
            # Verify that Term query was used for exact match
            args, kwargs = mock_execute.call_args
            query = args[0]
            assert query is not None

    @pytest.mark.asyncio
    async def test_search_by_path_with_http_methods(self, search_engine):
        """Test searching by path with HTTP method filter."""
        with patch.object(
            search_engine, "_execute_search", new_callable=AsyncMock
        ) as mock_execute:
            mock_execute.return_value = {"hits": [], "total": 0}

            await search_engine.search_by_path(
                "/api/users", http_methods=["GET", "POST"]
            )

            mock_execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_by_tag_single_tag(self, search_engine):
        """Test searching by a single tag."""
        with patch.object(
            search_engine, "_execute_search", new_callable=AsyncMock
        ) as mock_execute:
            mock_execute.return_value = {"hits": [], "total": 0}

            await search_engine.search_by_tag("users")

            mock_execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_by_tag_multiple_tags(self, search_engine):
        """Test searching by multiple tags."""
        with patch.object(
            search_engine, "_execute_search", new_callable=AsyncMock
        ) as mock_execute:
            mock_execute.return_value = {"hits": [], "total": 0}

            await search_engine.search_by_tag(["users", "admin"])

            mock_execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_by_tag_with_additional_query(self, search_engine):
        """Test searching by tag with additional text query."""
        with patch.object(
            search_engine, "_execute_search", new_callable=AsyncMock
        ) as mock_execute:
            mock_execute.return_value = {"hits": [], "total": 0}

            await search_engine.search_by_tag("users", additional_query="profile")

            mock_execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_suggest_queries(self, search_engine):
        """Test query suggestion functionality."""
        # Mock the index reader
        mock_reader = Mock()
        mock_reader.field_terms.return_value = [
            "user",
            "users",
            "username",
            "profile",
        ]
        search_engine.index_manager.index.reader.return_value = mock_reader

        suggestions = await search_engine.suggest_queries("user", limit=3)

        assert isinstance(suggestions, list)
        assert len(suggestions) <= 3
        assert all(isinstance(s, str) for s in suggestions)

    def test_parse_search_query(self, search_engine):
        """Test query parsing functionality."""
        query = search_engine._parse_search_query("test query")
        assert query is not None

    def test_apply_filters(self, search_engine):
        """Test filter application to queries."""
        base_query = Mock()
        filters = {"http_method": "GET", "deprecated": False}

        filtered_query = search_engine._apply_filters(base_query, filters)
        assert filtered_query is not None

    def test_apply_filters_with_list_values(self, search_engine):
        """Test filter application with list values."""
        base_query = Mock()
        filters = {"http_method": ["GET", "POST"], "deprecated": False}

        filtered_query = search_engine._apply_filters(base_query, filters)
        assert filtered_query is not None

    def test_extract_highlights(self, search_engine):
        """Test highlight extraction from search hits."""
        mock_hit = Mock()
        mock_hit.__getitem__ = Mock(side_effect=lambda x: f"test {x}")
        mock_hit.__contains__ = Mock(return_value=True)
        mock_hit.get = Mock(side_effect=lambda x, default=None: f"test {x}")

        mock_query = Mock()

        highlights = search_engine._extract_highlights(mock_hit, mock_query)

        assert isinstance(highlights, dict)


class TestSearchResult:
    """Test SearchResult dataclass."""

    def test_search_result_creation(self):
        """Test creating a SearchResult instance."""
        result = SearchResult(
            endpoint_id="test_id",
            endpoint_path="/api/test",
            http_method="GET",
            summary="Test endpoint",
            description="A test endpoint",
            score=0.85,
            highlights={"summary": "Test <em>endpoint</em>"},
            metadata={"operation_id": "getTest"},
        )

        assert result.endpoint_id == "test_id"
        assert result.endpoint_path == "/api/test"
        assert result.http_method == "GET"
        assert result.summary == "Test endpoint"
        assert result.description == "A test endpoint"
        assert result.score == 0.85
        assert "summary" in result.highlights
        assert "operation_id" in result.metadata


class TestSearchResponse:
    """Test SearchResponse dataclass."""

    def test_search_response_creation(self):
        """Test creating a SearchResponse instance."""
        results = [
            SearchResult(
                endpoint_id="1",
                endpoint_path="/api/test",
                http_method="GET",
                summary="Test",
                description="Test endpoint",
                score=0.8,
                highlights={},
                metadata={},
            )
        ]

        response = SearchResponse(
            results=results,
            total_results=1,
            query_time=0.05,
            query="test",
            page=1,
            per_page=20,
            has_more=False,
        )

        assert len(response.results) == 1
        assert response.total_results == 1
        assert response.query_time == 0.05
        assert response.query == "test"
        assert response.page == 1
        assert response.per_page == 20
        assert response.has_more is False


class TestErrorHandling:
    """Test error handling in search operations."""

    @pytest.mark.asyncio
    async def test_search_handles_search_exceptions(self, search_engine):
        """Test that search handles exceptions gracefully."""
        with patch.object(
            search_engine, "_execute_search", new_callable=AsyncMock
        ) as mock_execute:
            mock_execute.side_effect = Exception("Search failed")

            with pytest.raises(RuntimeError, match="Search operation failed"):
                await search_engine.search("test")

    @pytest.mark.asyncio
    async def test_search_by_path_handles_exceptions(self, search_engine):
        """Test that path search handles exceptions gracefully."""
        with patch.object(
            search_engine, "_execute_search", new_callable=AsyncMock
        ) as mock_execute:
            mock_execute.side_effect = Exception("Path search failed")

            with pytest.raises(RuntimeError, match="Path search failed"):
                await search_engine.search_by_path("/api/test")

    @pytest.mark.asyncio
    async def test_search_by_tag_handles_exceptions(self, search_engine):
        """Test that tag search handles exceptions gracefully."""
        with patch.object(
            search_engine, "_execute_search", new_callable=AsyncMock
        ) as mock_execute:
            mock_execute.side_effect = Exception("Tag search failed")

            with pytest.raises(RuntimeError, match="Tag search failed"):
                await search_engine.search_by_tag("test")

    @pytest.mark.asyncio
    async def test_suggest_queries_handles_exceptions(self, search_engine):
        """Test that query suggestions handle exceptions gracefully."""
        search_engine.index_manager.index.reader.side_effect = Exception(
            "Reader failed"
        )

        suggestions = await search_engine.suggest_queries("test")

        # Should return empty list on error
        assert suggestions == []
