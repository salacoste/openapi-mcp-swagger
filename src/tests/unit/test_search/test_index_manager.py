"""Tests for search index manager functionality."""

import asyncio
import shutil
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from swagger_mcp_server.config.settings import SearchConfig
from swagger_mcp_server.search.index_manager import SearchIndexManager
from swagger_mcp_server.storage.repositories.endpoint_repository import (
    EndpointRepository,
)
from swagger_mcp_server.storage.repositories.metadata_repository import (
    MetadataRepository,
)
from swagger_mcp_server.storage.repositories.schema_repository import (
    SchemaRepository,
)


@pytest.fixture
def temp_index_dir():
    """Create a temporary directory for index testing."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def mock_repositories():
    """Create mock repository instances."""
    endpoint_repo = Mock(spec=EndpointRepository)
    schema_repo = Mock(spec=SchemaRepository)
    metadata_repo = Mock(spec=MetadataRepository)

    return endpoint_repo, schema_repo, metadata_repo


@pytest.fixture
def search_config():
    """Create a test search configuration."""
    from swagger_mcp_server.config.settings import (
        SearchIndexingConfig,
        SearchPerformanceConfig,
    )

    indexing_config = SearchIndexingConfig(batch_size=100)
    performance_config = SearchPerformanceConfig(max_search_results=500)

    return SearchConfig(
        index_directory="./test_index",
        indexing=indexing_config,
        performance=performance_config,
    )


@pytest.fixture
def index_manager(temp_index_dir, mock_repositories, search_config):
    """Create a SearchIndexManager instance for testing."""
    endpoint_repo, schema_repo, metadata_repo = mock_repositories

    manager = SearchIndexManager(
        index_dir=temp_index_dir,
        endpoint_repo=endpoint_repo,
        schema_repo=schema_repo,
        metadata_repo=metadata_repo,
        config=search_config,
    )

    return manager


class TestSearchIndexManager:
    """Test cases for SearchIndexManager class."""

    def test_initialization(self, index_manager, temp_index_dir):
        """Test that SearchIndexManager initializes correctly."""
        assert index_manager.index_dir == Path(temp_index_dir)
        assert index_manager.config is not None
        assert index_manager._index is None

    def test_index_directory_creation(
        self, temp_index_dir, mock_repositories, search_config
    ):
        """Test that index directory is created if it doesn't exist."""
        # Use a subdirectory that doesn't exist
        non_existent_dir = Path(temp_index_dir) / "new_index_dir"
        assert not non_existent_dir.exists()

        endpoint_repo, schema_repo, metadata_repo = mock_repositories
        manager = SearchIndexManager(
            index_dir=str(non_existent_dir),
            endpoint_repo=endpoint_repo,
            schema_repo=schema_repo,
            metadata_repo=metadata_repo,
            config=search_config,
        )

        assert non_existent_dir.exists()

    def test_index_property_creates_index(self, index_manager):
        """Test that accessing index property creates the index."""
        # Index should be None initially
        assert index_manager._index is None

        # Accessing the property should create the index
        index = index_manager.index
        assert index is not None
        assert index_manager._index is not None

    @pytest.mark.asyncio
    async def test_create_index_from_database_empty(self, index_manager):
        """Test index creation with empty database."""
        # Mock empty database
        index_manager.endpoint_repo.count_all = AsyncMock(return_value=0)
        index_manager.endpoint_repo.get_all = AsyncMock(return_value=[])

        # Create index
        (
            total_indexed,
            elapsed_time,
        ) = await index_manager.create_index_from_database()

        assert total_indexed == 0
        assert elapsed_time >= 0
        assert index_manager.endpoint_repo.count_all.called

    @pytest.mark.asyncio
    async def test_create_index_from_database_with_data(self, index_manager):
        """Test index creation with sample endpoint data."""
        # Mock database with sample data
        sample_endpoints = [
            {
                "id": "1",
                "path": "/api/users",
                "method": "GET",
                "summary": "Get users",
                "description": "Retrieve all users",
                "parameters": [],
                "tags": ["users"],
                "security": [],
                "responses": {"200": {"description": "Success"}},
            },
            {
                "id": "2",
                "path": "/api/users/{id}",
                "method": "GET",
                "summary": "Get user",
                "description": "Retrieve a specific user",
                "parameters": [{"name": "id", "type": "string"}],
                "tags": ["users"],
                "security": [],
                "responses": {"200": {"description": "Success"}},
            },
        ]

        index_manager.endpoint_repo.count_all = AsyncMock(return_value=2)

        # Mock get_all to handle pagination properly
        async def mock_get_all(limit=None, offset=0):
            if offset == 0:
                return sample_endpoints
            else:
                return []  # No more data after first batch

        index_manager.endpoint_repo.get_all = AsyncMock(side_effect=mock_get_all)

        # Mock the document creation
        async def mock_create_search_document(endpoint):
            return {
                "endpoint_id": endpoint["id"],
                "endpoint_path": endpoint["path"],
                "http_method": endpoint["method"],
                "operation_summary": endpoint["summary"],
                "searchable_text": f"{endpoint['path']} {endpoint['method']} {endpoint['summary']}",
            }

        index_manager._create_search_document = AsyncMock(
            side_effect=mock_create_search_document
        )

        # Create index
        (
            total_indexed,
            elapsed_time,
        ) = await index_manager.create_index_from_database()

        assert total_indexed == 2
        assert elapsed_time >= 0
        assert index_manager.endpoint_repo.count_all.called

    @pytest.mark.asyncio
    async def test_create_index_with_progress_callback(self, index_manager):
        """Test index creation with progress callback."""
        progress_calls = []

        async def progress_callback(current, total, message):
            progress_calls.append((current, total, message))

        # Mock database
        index_manager.endpoint_repo.count_all = AsyncMock(return_value=1)
        index_manager.endpoint_repo.get_all = AsyncMock(
            return_value=[
                {
                    "id": "1",
                    "path": "/api/test",
                    "method": "GET",
                    "summary": "Test",
                    "description": "Test endpoint",
                    "parameters": [],
                    "tags": [],
                    "security": [],
                    "responses": {},
                }
            ]
        )

        # Create index with callback
        await index_manager.create_index_from_database(
            progress_callback=progress_callback
        )

        # Verify callback was called
        assert len(progress_calls) >= 2  # At least start and end calls
        assert progress_calls[0][0] == 0  # First call should be 0
        assert "Starting" in progress_calls[0][2]

    @pytest.mark.asyncio
    async def test_update_endpoint_document(self, index_manager):
        """Test updating a single endpoint document."""
        # First create an index
        index_manager.endpoint_repo.count_all = AsyncMock(return_value=0)
        index_manager.endpoint_repo.get_all = AsyncMock(return_value=[])
        await index_manager.create_index_from_database()

        # Mock endpoint data for update
        updated_endpoint = {
            "id": "1",
            "path": "/api/updated",
            "method": "POST",
            "summary": "Updated endpoint",
            "description": "An updated test endpoint",
            "parameters": [],
            "tags": ["updated"],
            "security": [],
            "responses": {},
        }

        index_manager.endpoint_repo.get_by_id = AsyncMock(return_value=updated_endpoint)

        # Update document
        result = await index_manager.update_endpoint_document("1")

        assert result is True
        assert index_manager.endpoint_repo.get_by_id.called

    @pytest.mark.asyncio
    async def test_update_nonexistent_endpoint_document(self, index_manager):
        """Test updating a document that doesn't exist in database."""
        # Create empty index
        index_manager.endpoint_repo.count_all = AsyncMock(return_value=0)
        index_manager.endpoint_repo.get_all = AsyncMock(return_value=[])
        await index_manager.create_index_from_database()

        # Mock missing endpoint
        index_manager.endpoint_repo.get_by_id = AsyncMock(return_value=None)

        # Update should remove document
        result = await index_manager.update_endpoint_document("nonexistent")

        assert result is True  # Successfully handled missing document
        assert index_manager.endpoint_repo.get_by_id.called

    @pytest.mark.asyncio
    async def test_remove_endpoint_document(self, index_manager):
        """Test removing an endpoint document from index."""
        # Create empty index first
        index_manager.endpoint_repo.count_all = AsyncMock(return_value=0)
        index_manager.endpoint_repo.get_all = AsyncMock(return_value=[])
        await index_manager.create_index_from_database()

        # Remove document (should succeed even if document doesn't exist)
        result = await index_manager.remove_endpoint_document("test_id")

        assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_get_index_stats(self, index_manager):
        """Test getting index statistics."""
        # Create empty index
        index_manager.endpoint_repo.count_all = AsyncMock(return_value=0)
        index_manager.endpoint_repo.get_all = AsyncMock(return_value=[])
        await index_manager.create_index_from_database()

        # Get stats
        stats = await index_manager.get_index_stats()

        assert isinstance(stats, dict)
        assert "document_count" in stats
        assert "field_count" in stats
        assert "index_size_bytes" in stats
        assert "index_size_mb" in stats

        # For empty index
        assert stats["document_count"] == 0
        assert stats["field_count"] > 0  # Should have field schema

    @pytest.mark.asyncio
    async def test_validate_index_integrity(self, index_manager):
        """Test index integrity validation."""
        # Create empty index
        index_manager.endpoint_repo.count_all = AsyncMock(return_value=0)
        index_manager.endpoint_repo.get_all = AsyncMock(return_value=[])
        await index_manager.create_index_from_database()

        # Validate integrity
        validation_result = await index_manager.validate_index_integrity()

        assert isinstance(validation_result, dict)
        assert "issues" in validation_result
        assert "validation_passed" in validation_result
        assert "database_document_count" in validation_result
        assert "index_document_count" in validation_result

        # For consistent empty state, validation should pass
        assert validation_result["validation_passed"] is True
        assert len(validation_result["issues"]) == 0

    @pytest.mark.asyncio
    async def test_validate_index_integrity_mismatch(self, index_manager):
        """Test index integrity validation with database mismatch."""
        # Create empty index
        index_manager.endpoint_repo.count_all = AsyncMock(return_value=0)
        index_manager.endpoint_repo.get_all = AsyncMock(return_value=[])
        await index_manager.create_index_from_database()

        # Change mock to return different count for validation
        index_manager.endpoint_repo.count_all = AsyncMock(return_value=5)

        # Validate integrity (should detect mismatch)
        validation_result = await index_manager.validate_index_integrity()

        assert validation_result["validation_passed"] is False
        assert len(validation_result["issues"]) > 0
        assert "mismatch" in validation_result["issues"][0].lower()

    def test_close_index(self, index_manager):
        """Test closing the index properly."""
        # Access index to create it
        _ = index_manager.index
        assert index_manager._index is not None

        # Close index
        index_manager.close()
        assert index_manager._index is None


class TestDocumentProcessing:
    """Test document processing functionality."""

    @pytest.mark.asyncio
    async def test_create_search_document_basic(self, index_manager):
        """Test creating a search document from endpoint data."""
        endpoint_data = {
            "id": "test_id",
            "path": "/api/test",
            "method": "GET",
            "summary": "Test endpoint",
            "description": "A test endpoint",
            "operation_id": "getTest",
            "parameters": [],
            "tags": ["test"],
            "security": [],
            "responses": {},
            "deprecated": False,
        }

        # Access private method for testing
        document = await index_manager._create_search_document(endpoint_data)

        assert document["endpoint_id"] == "test_id"
        assert document["endpoint_path"] == "/api/test"
        assert document["http_method"] == "GET"
        assert document["summary"] == "Test endpoint"
        assert document["description"] == "A test endpoint"
        assert document["operation_id"] == "getTest"
        assert document["deprecated"] is False

    @pytest.mark.asyncio
    async def test_create_search_document_with_parameters(self, index_manager):
        """Test creating a search document with parameters."""
        endpoint_data = {
            "id": "test_id",
            "path": "/api/users/{id}",
            "method": "GET",
            "summary": "Get user",
            "description": "Retrieve a user by ID",
            "parameters": [
                {
                    "name": "id",
                    "type": "string",
                    "description": "User identifier",
                },
                {
                    "name": "include",
                    "type": "array",
                    "description": "Include related data",
                },
            ],
            "tags": ["users"],
            "security": [],
            "responses": {},
            "deprecated": False,
        }

        document = await index_manager._create_search_document(endpoint_data)

        assert "id (string): User identifier" in document["parameters"]
        assert "include (array): Include related data" in document["parameters"]
        assert "id include" == document["parameter_names"]

    @pytest.mark.asyncio
    async def test_create_search_document_with_security(self, index_manager):
        """Test creating a search document with security requirements."""
        endpoint_data = {
            "id": "test_id",
            "path": "/api/secure",
            "method": "POST",
            "summary": "Secure endpoint",
            "description": "An endpoint requiring authentication",
            "parameters": [],
            "tags": [],
            "security": [{"bearer_auth": []}, {"api_key": []}],
            "responses": {},
            "deprecated": False,
        }

        document = await index_manager._create_search_document(endpoint_data)

        assert "bearer_auth api_key" == document["authentication"]
        assert "bearer_auth api_key" == document["security_schemes"]

    @pytest.mark.asyncio
    async def test_create_search_document_with_responses(self, index_manager):
        """Test creating a search document with response information."""
        endpoint_data = {
            "id": "test_id",
            "path": "/api/data",
            "method": "GET",
            "summary": "Get data",
            "description": "Retrieve data",
            "parameters": [],
            "tags": [],
            "security": [],
            "responses": {
                "200": {
                    "description": "Success",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/Data"}
                        },
                        "text/csv": {"schema": {"type": "string"}},
                    },
                },
                "404": {"description": "Not found"},
            },
            "deprecated": False,
        }

        document = await index_manager._create_search_document(endpoint_data)

        assert "200 404" == document["response_codes"]
        assert "application/json text/csv" == document["content_types"]


class TestBatchProcessing:
    """Test batch processing functionality."""

    @pytest.mark.asyncio
    async def test_process_endpoints_in_batches(self, index_manager):
        """Test processing endpoints in batches."""
        # Mock large dataset
        all_endpoints = []
        for i in range(250):  # More than one batch
            all_endpoints.append(
                {
                    "id": f"endpoint_{i}",
                    "path": f"/api/endpoint_{i}",
                    "method": "GET",
                    "summary": f"Endpoint {i}",
                    "description": f"Test endpoint number {i}",
                    "parameters": [],
                    "tags": [],
                    "security": [],
                    "responses": {},
                    "deprecated": False,
                }
            )

        # Mock repository to return batches
        def mock_get_all(limit=None, offset=0):
            if offset >= len(all_endpoints):
                return []
            end = offset + limit if limit else len(all_endpoints)
            return all_endpoints[offset:end]

        index_manager.endpoint_repo.get_all = AsyncMock(side_effect=mock_get_all)

        # Process in batches
        batch_count = 0
        total_documents = 0

        async for batch_num, documents in index_manager._process_endpoints_in_batches(
            100
        ):
            batch_count += 1
            total_documents += len(documents)

        # Should have 3 batches (100, 100, 50)
        assert batch_count == 3
        assert total_documents == 250

    @pytest.mark.asyncio
    async def test_index_document_batch(self, index_manager):
        """Test indexing a batch of documents."""
        # Create index first
        index_manager.endpoint_repo.count_all = AsyncMock(return_value=0)
        index_manager.endpoint_repo.get_all = AsyncMock(return_value=[])
        await index_manager.create_index_from_database()

        # Create test documents
        documents = [
            {
                "endpoint_id": "1",
                "endpoint_path": "/api/test1",
                "http_method": "GET",
                "summary": "Test 1",
                "description": "First test endpoint",
                "last_updated": 1234567890,
            },
            {
                "endpoint_id": "2",
                "endpoint_path": "/api/test2",
                "http_method": "POST",
                "summary": "Test 2",
                "description": "Second test endpoint",
                "last_updated": 1234567891,
            },
        ]

        # Index the batch
        indexed_count = await index_manager._index_document_batch(documents)

        assert indexed_count == 2
