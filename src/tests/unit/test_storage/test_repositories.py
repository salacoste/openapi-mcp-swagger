"""Comprehensive tests for repository classes."""

import os
import pytest
import tempfile
import asyncio
from datetime import datetime, timezone
from unittest.mock import Mock, patch
from typing import List, Dict, Any

from swagger_mcp_server.storage.database import DatabaseManager, DatabaseConfig
from swagger_mcp_server.storage.models import (
    APIMetadata, Endpoint, Schema, SecurityScheme, EndpointDependency
)
from swagger_mcp_server.storage.repositories import (
    EndpointRepository, SchemaRepository, SecurityRepository,
    MetadataRepository
)
from swagger_mcp_server.storage.repositories.base import (
    BaseRepository, RepositoryError, NotFoundError, ConflictError
)


@pytest.fixture
async def temp_db():
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as temp_file:
        temp_path = temp_file.name

    config = DatabaseConfig(
        database_path=temp_path,
        enable_wal=False,
        enable_fts=True,
        vacuum_on_startup=False
    )

    db_manager = DatabaseManager(config)
    await db_manager.initialize()

    yield db_manager

    await db_manager.close()
    if os.path.exists(temp_path):
        os.unlink(temp_path)


@pytest.fixture
async def db_session(temp_db):
    """Create a database session for testing."""
    async with temp_db.get_session() as session:
        yield session


@pytest.fixture
async def sample_api(db_session):
    """Create sample API metadata for testing."""
    api = APIMetadata(
        title="Test API",
        version="1.0.0",
        openapi_version="3.0.0",
        description="Test API for unit tests",
        base_url="https://api.test.com",
        contact_info={"name": "Test Team", "email": "test@test.com"},
        license_info={"name": "MIT"},
        servers=[{"url": "https://api.test.com"}],
        specification_hash="abc123",
        file_path="/test/swagger.json",
        file_size=1024
    )

    db_session.add(api)
    await db_session.flush()
    await db_session.refresh(api)
    return api


@pytest.fixture
async def sample_schema(db_session, sample_api):
    """Create sample schema for testing."""
    schema = Schema(
        api_id=sample_api.id,
        name="TestModel",
        title="Test Model",
        type="object",
        description="A test schema model",
        properties={
            "id": {"type": "integer", "description": "Unique identifier"},
            "name": {"type": "string", "description": "Name field"},
            "email": {"type": "string", "format": "email"}
        },
        required=["id", "name"],
        searchable_text="TestModel object id name email identifier",
        property_names=["id", "name", "email"]
    )

    db_session.add(schema)
    await db_session.flush()
    await db_session.refresh(schema)
    return schema


@pytest.fixture
async def sample_endpoint(db_session, sample_api):
    """Create sample endpoint for testing."""
    endpoint = Endpoint(
        api_id=sample_api.id,
        path="/users/{id}",
        method="GET",
        operation_id="getUser",
        summary="Get user by ID",
        description="Retrieve a user by their unique identifier",
        tags=["users"],
        parameters=[{
            "name": "id",
            "in": "path",
            "required": True,
            "schema": {"type": "integer"}
        }],
        responses={
            "200": {
                "description": "User found",
                "content": {"application/json": {"schema": {"$ref": "#/components/schemas/User"}}}
            },
            "404": {"description": "User not found"}
        },
        searchable_text="users getUser GET user identifier retrieve",
        parameter_names=["id"],
        response_codes=["200", "404"],
        content_types=["application/json"]
    )

    db_session.add(endpoint)
    await db_session.flush()
    await db_session.refresh(endpoint)
    return endpoint


@pytest.fixture
async def sample_security_scheme(db_session, sample_api):
    """Create sample security scheme for testing."""
    security_scheme = SecurityScheme(
        api_id=sample_api.id,
        name="BearerAuth",
        type="http",
        description="Bearer token authentication",
        http_scheme="bearer",
        bearer_format="JWT"
    )

    db_session.add(security_scheme)
    await db_session.flush()
    await db_session.refresh(security_scheme)
    return security_scheme


@pytest.mark.unit
class TestBaseRepository:
    """Test the base repository functionality."""

    async def test_create_entity(self, db_session, sample_api):
        """Test creating an entity."""
        repo = BaseRepository(db_session, APIMetadata)

        new_api = APIMetadata(
            title="New API",
            version="2.0.0",
            openapi_version="3.1.0",
            description="Another test API"
        )

        created = await repo.create(new_api)
        assert created.id is not None
        assert created.title == "New API"
        assert created.version == "2.0.0"

    async def test_create_many_entities(self, db_session):
        """Test bulk creation of entities."""
        repo = BaseRepository(db_session, APIMetadata)

        apis = [
            APIMetadata(title=f"API {i}", version="1.0.0", openapi_version="3.0.0")
            for i in range(5)
        ]

        created = await repo.create_many(apis)
        assert len(created) == 5
        for api in created:
            assert api.id is not None

    async def test_get_by_id(self, db_session, sample_api):
        """Test retrieving entity by ID."""
        repo = BaseRepository(db_session, APIMetadata)

        retrieved = await repo.get_by_id(sample_api.id)
        assert retrieved is not None
        assert retrieved.id == sample_api.id
        assert retrieved.title == sample_api.title

    async def test_get_by_id_not_found(self, db_session):
        """Test retrieving non-existent entity."""
        repo = BaseRepository(db_session, APIMetadata)

        retrieved = await repo.get_by_id(99999)
        assert retrieved is None

    async def test_get_by_id_or_raise(self, db_session, sample_api):
        """Test retrieving entity by ID or raising exception."""
        repo = BaseRepository(db_session, APIMetadata)

        # Should return entity
        retrieved = await repo.get_by_id_or_raise(sample_api.id)
        assert retrieved.id == sample_api.id

        # Should raise exception
        with pytest.raises(NotFoundError):
            await repo.get_by_id_or_raise(99999)

    async def test_update_entity(self, db_session, sample_api):
        """Test updating an entity."""
        repo = BaseRepository(db_session, APIMetadata)

        sample_api.title = "Updated API Title"
        updated = await repo.update(sample_api)

        assert updated.title == "Updated API Title"

    async def test_update_by_id(self, db_session, sample_api):
        """Test updating entity by ID."""
        repo = BaseRepository(db_session, APIMetadata)

        updates = {"title": "Updated via ID", "version": "2.0.0"}
        updated = await repo.update_by_id(sample_api.id, updates)

        assert updated is not None
        assert updated.title == "Updated via ID"
        assert updated.version == "2.0.0"

    async def test_update_by_id_not_found(self, db_session):
        """Test updating non-existent entity."""
        repo = BaseRepository(db_session, APIMetadata)

        result = await repo.update_by_id(99999, {"title": "Not found"})
        assert result is None

    async def test_delete_entity(self, db_session, sample_api):
        """Test deleting an entity."""
        repo = BaseRepository(db_session, APIMetadata)

        result = await repo.delete(sample_api)
        assert result is True

        # Verify deletion
        retrieved = await repo.get_by_id(sample_api.id)
        assert retrieved is None

    async def test_delete_by_id(self, db_session, sample_api):
        """Test deleting entity by ID."""
        repo = BaseRepository(db_session, APIMetadata)

        result = await repo.delete_by_id(sample_api.id)
        assert result is True

        # Try to delete again - should return False
        result = await repo.delete_by_id(sample_api.id)
        assert result is False

    async def test_list_entities(self, db_session):
        """Test listing entities with pagination and filtering."""
        repo = BaseRepository(db_session, APIMetadata)

        # Create multiple APIs
        apis = [
            APIMetadata(title=f"API {i}", version="1.0.0", openapi_version="3.0.0")
            for i in range(10)
        ]
        await repo.create_many(apis)

        # Test basic listing
        all_apis = await repo.list()
        assert len(all_apis) >= 10

        # Test pagination
        page1 = await repo.list(limit=5, offset=0)
        page2 = await repo.list(limit=5, offset=5)
        assert len(page1) == 5
        assert len(page2) == 5
        assert page1[0].id != page2[0].id

        # Test filtering
        filtered = await repo.list(filters={"version": "1.0.0"})
        assert len(filtered) >= 10

    async def test_count_entities(self, db_session):
        """Test counting entities."""
        repo = BaseRepository(db_session, APIMetadata)

        # Create test data
        apis = [
            APIMetadata(title=f"API {i}", version="1.0.0", openapi_version="3.0.0")
            for i in range(5)
        ]
        await repo.create_many(apis)

        total_count = await repo.count()
        assert total_count >= 5

        # Test filtered count
        filtered_count = await repo.count(filters={"version": "1.0.0"})
        assert filtered_count >= 5

    async def test_exists(self, db_session, sample_api):
        """Test checking entity existence."""
        repo = BaseRepository(db_session, APIMetadata)

        # Should exist
        exists = await repo.exists({"title": sample_api.title})
        assert exists is True

        # Should not exist
        exists = await repo.exists({"title": "Non-existent API"})
        assert exists is False

    async def test_bulk_operations(self, db_session):
        """Test bulk insert and update operations."""
        repo = BaseRepository(db_session, APIMetadata)

        # Bulk insert
        data = [
            {"title": f"Bulk API {i}", "version": "1.0.0", "openapi_version": "3.0.0"}
            for i in range(3)
        ]
        await repo.bulk_insert_dicts(data)

        count = await repo.count(filters={"version": "1.0.0"})
        assert count >= 3

        # Get IDs for bulk update
        entities = await repo.list(filters={"version": "1.0.0"})
        update_data = [
            {"id": entity.id, "version": "2.0.0"}
            for entity in entities[:2]
        ]

        updated_count = await repo.bulk_update_dicts(update_data)
        assert updated_count >= 2

    async def test_get_page(self, db_session):
        """Test paginated results with metadata."""
        repo = BaseRepository(db_session, APIMetadata)

        # Create test data
        apis = [
            APIMetadata(title=f"Page API {i}", version="1.0.0", openapi_version="3.0.0")
            for i in range(15)
        ]
        await repo.create_many(apis)

        # Get first page
        page_result = await repo.get_page(page=1, per_page=5)

        assert len(page_result['entities']) == 5
        assert page_result['pagination']['page'] == 1
        assert page_result['pagination']['per_page'] == 5
        assert page_result['pagination']['total_count'] >= 15
        assert page_result['pagination']['total_pages'] >= 3
        assert page_result['pagination']['has_prev'] is False
        assert page_result['pagination']['has_next'] is True

        # Get second page
        page2_result = await repo.get_page(page=2, per_page=5)
        assert page2_result['pagination']['has_prev'] is True


@pytest.mark.unit
class TestMetadataRepository:
    """Test the metadata repository."""

    async def test_find_by_specification_hash(self, db_session, sample_api):
        """Test finding API by specification hash."""
        repo = MetadataRepository(db_session)

        found = await repo.find_by_specification_hash(sample_api.specification_hash)
        assert found is not None
        assert found.id == sample_api.id

        # Test not found
        not_found = await repo.find_by_specification_hash("nonexistent")
        assert not_found is None

    async def test_find_by_title_version(self, db_session, sample_api):
        """Test finding API by title and version."""
        repo = MetadataRepository(db_session)

        found = await repo.find_by_title_version(sample_api.title, sample_api.version)
        assert found is not None
        assert found.id == sample_api.id

        # Test not found
        not_found = await repo.find_by_title_version("Non-existent", "1.0.0")
        assert not_found is None


@pytest.mark.unit
class TestEndpointRepository:
    """Test the endpoint repository."""

    async def test_get_endpoints_by_api(self, db_session, sample_api, sample_endpoint):
        """Test getting endpoints for an API."""
        repo = EndpointRepository(db_session)

        endpoints = await repo.get_endpoints_by_api(sample_api.id)
        assert len(endpoints) >= 1
        assert endpoints[0].id == sample_endpoint.id

    async def test_search_endpoints_by_method(self, db_session, sample_api, sample_endpoint):
        """Test searching endpoints by HTTP method."""
        repo = EndpointRepository(db_session)

        # Create additional endpoints with different methods
        post_endpoint = Endpoint(
            api_id=sample_api.id,
            path="/users",
            method="POST",
            operation_id="createUser",
            summary="Create user",
            searchable_text="users createUser POST create"
        )
        db_session.add(post_endpoint)
        await db_session.flush()

        # Search by GET method
        get_endpoints = await repo.search_endpoints(
            query="users",
            api_id=sample_api.id,
            methods=["GET"]
        )
        assert len(get_endpoints) == 1
        assert get_endpoints[0].method == "GET"

        # Search by POST method
        post_endpoints = await repo.search_endpoints(
            query="users",
            api_id=sample_api.id,
            methods=["POST"]
        )
        assert len(post_endpoints) == 1
        assert post_endpoints[0].method == "POST"

    async def test_search_endpoints_by_tags(self, db_session, sample_api, sample_endpoint):
        """Test searching endpoints by tags."""
        repo = EndpointRepository(db_session)

        # Search by existing tag
        tagged_endpoints = await repo.search_endpoints(
            query="",
            api_id=sample_api.id,
            tags=["users"]
        )
        assert len(tagged_endpoints) >= 1

        # Search by non-existent tag
        no_endpoints = await repo.search_endpoints(
            query="",
            api_id=sample_api.id,
            tags=["nonexistent"]
        )
        assert len(no_endpoints) == 0

    async def test_get_endpoints_by_path_pattern(self, db_session, sample_api, sample_endpoint):
        """Test getting endpoints by path pattern."""
        repo = EndpointRepository(db_session)

        endpoints = await repo.get_endpoints_by_path_pattern(
            api_id=sample_api.id,
            path_pattern="/users%"
        )
        assert len(endpoints) >= 1
        assert endpoints[0].path.startswith("/users")


@pytest.mark.unit
class TestSchemaRepository:
    """Test the schema repository."""

    async def test_get_schemas_by_api(self, db_session, sample_api, sample_schema):
        """Test getting schemas for an API."""
        repo = SchemaRepository(db_session)

        schemas = await repo.get_schemas_by_api(sample_api.id)
        assert len(schemas) >= 1
        assert schemas[0].id == sample_schema.id

    async def test_find_by_name(self, db_session, sample_api, sample_schema):
        """Test finding schema by name."""
        repo = SchemaRepository(db_session)

        found = await repo.find_by_name(sample_api.id, sample_schema.name)
        assert found is not None
        assert found.id == sample_schema.id

        # Test not found
        not_found = await repo.find_by_name(sample_api.id, "NonexistentSchema")
        assert not_found is None

    async def test_search_schemas(self, db_session, sample_api, sample_schema):
        """Test searching schemas."""
        repo = SchemaRepository(db_session)

        # Search by name
        results = await repo.search_schemas(
            query="TestModel",
            api_id=sample_api.id
        )
        assert len(results) >= 1
        assert results[0].name == "TestModel"

        # Search by type
        results = await repo.search_schemas(
            query="",
            api_id=sample_api.id,
            schema_types=["object"]
        )
        assert len(results) >= 1

    async def test_get_most_referenced_schemas(self, db_session, sample_api):
        """Test getting most referenced schemas."""
        repo = SchemaRepository(db_session)

        # Create schemas with different reference counts
        schemas = []
        for i, ref_count in enumerate([5, 3, 8, 1]):
            schema = Schema(
                api_id=sample_api.id,
                name=f"Schema{i}",
                type="object",
                reference_count=ref_count
            )
            db_session.add(schema)
            schemas.append(schema)

        await db_session.flush()

        # Get most referenced
        most_referenced = await repo.get_most_referenced_schemas(
            api_id=sample_api.id,
            limit=2
        )
        assert len(most_referenced) == 2
        assert most_referenced[0].reference_count >= most_referenced[1].reference_count


@pytest.mark.unit
class TestSecurityRepository:
    """Test the security repository."""

    async def test_get_security_schemes_by_api(self, db_session, sample_api, sample_security_scheme):
        """Test getting security schemes for an API."""
        repo = SecurityRepository(db_session)

        schemes = await repo.get_security_schemes_by_api(sample_api.id)
        assert len(schemes) >= 1
        assert schemes[0].id == sample_security_scheme.id

    async def test_find_by_name(self, db_session, sample_api, sample_security_scheme):
        """Test finding security scheme by name."""
        repo = SecurityRepository(db_session)

        found = await repo.find_by_name(sample_api.id, sample_security_scheme.name)
        assert found is not None
        assert found.id == sample_security_scheme.id

        # Test not found
        not_found = await repo.find_by_name(sample_api.id, "NonexistentAuth")
        assert not_found is None

    async def test_get_schemes_by_type(self, db_session, sample_api, sample_security_scheme):
        """Test getting security schemes by type."""
        repo = SecurityRepository(db_session)

        # Create additional schemes of different types
        api_key_scheme = SecurityScheme(
            api_id=sample_api.id,
            name="ApiKeyAuth",
            type="apiKey",
            api_key_name="X-API-Key",
            api_key_location="header"
        )
        db_session.add(api_key_scheme)
        await db_session.flush()

        # Get HTTP schemes
        http_schemes = await repo.get_schemes_by_type(sample_api.id, "http")
        assert len(http_schemes) >= 1
        assert all(s.type == "http" for s in http_schemes)

        # Get API key schemes
        apikey_schemes = await repo.get_schemes_by_type(sample_api.id, "apiKey")
        assert len(apikey_schemes) >= 1
        assert all(s.type == "apiKey" for s in apikey_schemes)


@pytest.mark.integration
class TestRepositoryIntegration:
    """Integration tests for repositories working together."""

    async def test_create_api_with_dependencies(self, db_session):
        """Test creating API with all related entities."""
        # Create repositories
        metadata_repo = MetadataRepository(db_session)
        endpoint_repo = EndpointRepository(db_session)
        schema_repo = SchemaRepository(db_session)
        security_repo = SecurityRepository(db_session)

        # Create API metadata
        api = APIMetadata(
            title="Integration Test API",
            version="1.0.0",
            openapi_version="3.0.0",
            description="Full integration test"
        )
        created_api = await metadata_repo.create(api)

        # Create schema
        user_schema = Schema(
            api_id=created_api.id,
            name="User",
            type="object",
            properties={"id": {"type": "integer"}, "name": {"type": "string"}},
            required=["id", "name"]
        )
        created_schema = await schema_repo.create(user_schema)

        # Create security scheme
        auth_scheme = SecurityScheme(
            api_id=created_api.id,
            name="BearerAuth",
            type="http",
            http_scheme="bearer"
        )
        created_auth = await security_repo.create(auth_scheme)

        # Create endpoint
        endpoint = Endpoint(
            api_id=created_api.id,
            path="/users/{id}",
            method="GET",
            operation_id="getUser",
            summary="Get user by ID",
            security=[{"BearerAuth": []}],
            responses={"200": {"description": "User found"}}
        )
        created_endpoint = await endpoint_repo.create(endpoint)

        # Verify relationships
        api_endpoints = await endpoint_repo.get_endpoints_by_api(created_api.id)
        assert len(api_endpoints) == 1
        assert api_endpoints[0].id == created_endpoint.id

        api_schemas = await schema_repo.get_schemas_by_api(created_api.id)
        assert len(api_schemas) == 1
        assert api_schemas[0].id == created_schema.id

        api_security = await security_repo.get_security_schemes_by_api(created_api.id)
        assert len(api_security) == 1
        assert api_security[0].id == created_auth.id

    async def test_cascade_deletion(self, db_session, sample_api, sample_endpoint, sample_schema):
        """Test that deleting API cascades to related entities."""
        metadata_repo = MetadataRepository(db_session)
        endpoint_repo = EndpointRepository(db_session)
        schema_repo = SchemaRepository(db_session)

        # Verify entities exist
        api_endpoints = await endpoint_repo.get_endpoints_by_api(sample_api.id)
        api_schemas = await schema_repo.get_schemas_by_api(sample_api.id)
        assert len(api_endpoints) >= 1
        assert len(api_schemas) >= 1

        # Delete API
        await metadata_repo.delete(sample_api)
        await db_session.commit()

        # Verify cascade deletion
        remaining_endpoints = await endpoint_repo.get_endpoints_by_api(sample_api.id)
        remaining_schemas = await schema_repo.get_schemas_by_api(sample_api.id)
        assert len(remaining_endpoints) == 0
        assert len(remaining_schemas) == 0


@pytest.mark.performance
class TestRepositoryPerformance:
    """Performance tests for repository operations."""

    async def test_bulk_operations_performance(self, db_session, sample_api):
        """Test performance of bulk operations."""
        import time

        repo = EndpointRepository(db_session)

        # Create large batch of endpoints
        batch_size = 100
        endpoints = []
        for i in range(batch_size):
            endpoint = Endpoint(
                api_id=sample_api.id,
                path=f"/test-{i}",
                method="GET",
                operation_id=f"testOp{i}",
                summary=f"Test operation {i}"
            )
            endpoints.append(endpoint)

        # Time bulk creation
        start_time = time.time()
        await repo.create_many(endpoints)
        await db_session.commit()
        creation_time = time.time() - start_time

        # Bulk creation should be fast
        assert creation_time < 2.0, f"Bulk creation took {creation_time:.2f}s, expected < 2.0s"

        # Time bulk retrieval
        start_time = time.time()
        retrieved = await repo.get_endpoints_by_api(sample_api.id)
        retrieval_time = time.time() - start_time

        assert len(retrieved) >= batch_size
        assert retrieval_time < 0.5, f"Bulk retrieval took {retrieval_time:.2f}s, expected < 0.5s"

    async def test_search_performance(self, db_session, sample_api):
        """Test search performance with large dataset."""
        import time

        repo = EndpointRepository(db_session)

        # Create many endpoints with searchable content
        batch_size = 200
        endpoints = []
        for i in range(batch_size):
            endpoint = Endpoint(
                api_id=sample_api.id,
                path=f"/api/v1/resources/{i}",
                method="GET",
                operation_id=f"getResource{i}",
                summary=f"Get resource {i}",
                description=f"Retrieve resource with ID {i}",
                tags=[f"resource-{i % 10}"],
                searchable_text=f"resource get retrieve ID {i} api endpoint"
            )
            endpoints.append(endpoint)

        await repo.create_many(endpoints)
        await db_session.commit()

        # Time search operation
        start_time = time.time()
        results = await repo.search_endpoints(
            query="resource",
            api_id=sample_api.id,
            limit=50
        )
        search_time = time.time() - start_time

        assert len(results) >= 50
        assert search_time < 0.2, f"Search took {search_time:.2f}s, expected < 0.2s"