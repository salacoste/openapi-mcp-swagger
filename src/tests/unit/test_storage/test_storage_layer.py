"""Tests for the storage layer components."""

import os
import pytest
import tempfile
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock

from swagger_mcp_server.storage.database import DatabaseManager, DatabaseConfig, get_db_manager
from swagger_mcp_server.storage.models import (
    APIMetadata, Endpoint, Schema, SecurityScheme, EndpointDependency
)
from swagger_mcp_server.storage.repositories import (
    EndpointRepository, SchemaRepository, SecurityRepository, MetadataRepository
)
from swagger_mcp_server.storage.migrations import MigrationManager, Migration
from swagger_mcp_server.storage.backup import BackupManager


@pytest.fixture
async def temp_db():
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as temp_file:
        temp_path = temp_file.name

    config = DatabaseConfig(
        database_path=temp_path,
        enable_wal=False,  # Disable WAL for simpler testing
        enable_fts=True,
        vacuum_on_startup=False
    )

    db_manager = DatabaseManager(config)
    await db_manager.initialize()

    yield db_manager

    # Cleanup
    await db_manager.close()
    if os.path.exists(temp_path):
        os.unlink(temp_path)


@pytest.fixture
async def sample_api_metadata():
    """Create sample API metadata for testing."""
    return APIMetadata(
        title="Test API",
        version="1.0.0",
        openapi_version="3.0.0",
        description="A test API for unit testing",
        base_url="https://api.example.com",
        contact_info={"name": "Test Team", "email": "test@example.com"},
        license_info={"name": "MIT", "url": "https://opensource.org/licenses/MIT"},
        servers=[{"url": "https://api.example.com", "description": "Production server"}],
        specification_hash="abc123def456",
        file_path="/path/to/test.json",
        file_size=1024
    )


@pytest.fixture
async def sample_endpoint(sample_api_metadata):
    """Create sample endpoint for testing."""
    return Endpoint(
        api_id=1,  # Will be set after API is created
        path="/users/{id}",
        method="get",
        operation_id="getUserById",
        summary="Get user by ID",
        description="Retrieve a single user by their unique identifier",
        tags=["users"],
        parameters=[
            {
                "name": "id",
                "in": "path",
                "required": True,
                "schema": {"type": "string"}
            }
        ],
        responses={
            "200": {
                "description": "User found",
                "content": {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/User"}
                    }
                }
            },
            "404": {"description": "User not found"}
        },
        searchable_text="get user by id retrieve single user unique identifier",
        parameter_names=["id"],
        response_codes=["200", "404"],
        content_types=["application/json"],
        schema_dependencies=["User"],
        security_dependencies=["bearerAuth"]
    )


@pytest.fixture
async def sample_schema(sample_api_metadata):
    """Create sample schema for testing."""
    return Schema(
        api_id=1,  # Will be set after API is created
        name="User",
        title="User Object",
        type="object",
        description="Represents a user in the system",
        properties={
            "id": {"type": "string", "description": "User ID"},
            "name": {"type": "string", "description": "User name"},
            "email": {"type": "string", "format": "email", "description": "User email"}
        },
        required=["id", "name"],
        searchable_text="user object represents user system id name email",
        property_names=["id", "name", "email"],
        reference_count=1
    )


@pytest.fixture
async def sample_security_scheme(sample_api_metadata):
    """Create sample security scheme for testing."""
    return SecurityScheme(
        api_id=1,  # Will be set after API is created
        name="bearerAuth",
        type="http",
        description="Bearer token authentication",
        http_scheme="bearer",
        bearer_format="JWT",
        reference_count=1
    )


class TestDatabaseManager:
    """Tests for DatabaseManager class."""

    async def test_database_initialization(self, temp_db):
        """Test database initialization."""
        db_manager = temp_db

        assert db_manager._initialized is True
        assert db_manager._engine is not None
        assert db_manager._session_factory is not None

        # Test health check
        health = await db_manager.health_check()
        assert health['status'] == 'healthy'
        assert 'file_size_bytes' in health
        assert 'table_counts' in health

    async def test_session_management(self, temp_db):
        """Test database session management."""
        db_manager = temp_db

        async with db_manager.get_session() as session:
            assert session is not None
            # Test basic query
            result = await session.execute("SELECT 1")
            assert result.scalar() == 1

    async def test_raw_sql_execution(self, temp_db):
        """Test raw SQL execution."""
        db_manager = temp_db

        result = await db_manager.execute_raw_sql("SELECT 1 as test")
        assert len(result) == 1
        assert result[0][0] == 1

        # Test with parameters
        result = await db_manager.execute_raw_sql(
            "SELECT ? as value", ("test_param",)
        )
        assert result[0][0] == "test_param"

    async def test_database_info(self, temp_db):
        """Test database info collection."""
        db_manager = temp_db

        info = await db_manager.get_database_info()
        assert 'sqlite_version' in info
        assert 'database_size_bytes' in info
        assert 'tables' in info
        assert 'indexes' in info
        assert 'table_counts' in info

        # Should contain our expected tables
        expected_tables = {
            'api_metadata', 'endpoints', 'schemas', 'security_schemes',
            'endpoint_dependencies'
        }
        actual_tables = set(info['tables'])
        assert expected_tables.issubset(actual_tables)


class TestRepositories:
    """Tests for repository classes."""

    async def test_metadata_repository(self, temp_db, sample_api_metadata):
        """Test MetadataRepository operations."""
        async with temp_db.get_session() as session:
            repo = MetadataRepository(session)

            # Test create
            created_api = await repo.create(sample_api_metadata)
            assert created_api.id is not None
            assert created_api.title == "Test API"
            assert created_api.version == "1.0.0"

            # Test get by id
            retrieved_api = await repo.get_by_id(created_api.id)
            assert retrieved_api is not None
            assert retrieved_api.title == "Test API"

            # Test get by title and version
            by_title_version = await repo.get_by_title_version("Test API", "1.0.0")
            assert by_title_version is not None
            assert by_title_version.id == created_api.id

            # Test get by specification hash
            by_hash = await repo.get_by_specification_hash("abc123def456")
            assert by_hash is not None
            assert by_hash.id == created_api.id

            # Test search
            search_results = await repo.search_apis("Test")
            assert len(search_results) == 1
            assert search_results[0].title == "Test API"

            # Test update
            created_api.description = "Updated description"
            updated_api = await repo.update(created_api)
            assert updated_api.description == "Updated description"

            # Test statistics
            stats = await repo.get_statistics()
            assert stats['total_apis'] == 1
            assert stats['unique_titles'] == 1

            await session.commit()

    async def test_endpoint_repository(self, temp_db, sample_api_metadata, sample_endpoint):
        """Test EndpointRepository operations."""
        async with temp_db.get_session() as session:
            metadata_repo = MetadataRepository(session)
            endpoint_repo = EndpointRepository(session)

            # Create API first
            api = await metadata_repo.create(sample_api_metadata)
            await session.flush()

            sample_endpoint.api_id = api.id

            # Test create endpoint
            created_endpoint = await endpoint_repo.create(sample_endpoint)
            assert created_endpoint.id is not None
            assert created_endpoint.path == "/users/{id}"
            assert created_endpoint.method == "get"

            # Test get by path and method
            by_path_method = await endpoint_repo.get_by_path_method(
                "/users/{id}", "get", api.id
            )
            assert by_path_method is not None
            assert by_path_method.id == created_endpoint.id

            # Test get by operation ID
            by_operation_id = await endpoint_repo.get_by_operation_id(
                "getUserById", api.id
            )
            assert by_operation_id is not None
            assert by_operation_id.id == created_endpoint.id

            # Test search endpoints
            search_results = await endpoint_repo.search_endpoints("user")
            assert len(search_results) >= 1

            # Test get by tags
            by_tags = await endpoint_repo.get_by_tags(["users"], api.id)
            assert len(by_tags) == 1
            assert by_tags[0].id == created_endpoint.id

            # Test get methods for path
            methods = await endpoint_repo.get_methods_for_path("/users/{id}", api.id)
            assert "get" in methods

            # Test statistics
            stats = await endpoint_repo.get_statistics(api.id)
            assert stats['total_endpoints'] == 1
            assert stats['methods']['get'] == 1

            await session.commit()

    async def test_schema_repository(self, temp_db, sample_api_metadata, sample_schema):
        """Test SchemaRepository operations."""
        async with temp_db.get_session() as session:
            metadata_repo = MetadataRepository(session)
            schema_repo = SchemaRepository(session)

            # Create API first
            api = await metadata_repo.create(sample_api_metadata)
            await session.flush()

            sample_schema.api_id = api.id

            # Test create schema
            created_schema = await schema_repo.create(sample_schema)
            assert created_schema.id is not None
            assert created_schema.name == "User"
            assert created_schema.type == "object"

            # Test get by name
            by_name = await schema_repo.get_by_name("User", api.id)
            assert by_name is not None
            assert by_name.id == created_schema.id

            # Test search schemas
            search_results = await schema_repo.search_schemas("user")
            assert len(search_results) >= 1

            # Test get by type
            by_type = await schema_repo.get_by_type("object", api.id)
            assert len(by_type) == 1
            assert by_type[0].id == created_schema.id

            # Test find schemas with property
            with_property = await schema_repo.find_schemas_with_property("name", api.id)
            assert len(with_property) == 1
            assert with_property[0].id == created_schema.id

            # Test statistics
            stats = await schema_repo.get_statistics(api.id)
            assert stats['total_schemas'] == 1
            assert stats['types']['object'] == 1
            assert stats['referenced_count'] == 1

            await session.commit()

    async def test_security_repository(self, temp_db, sample_api_metadata, sample_security_scheme):
        """Test SecurityRepository operations."""
        async with temp_db.get_session() as session:
            metadata_repo = MetadataRepository(session)
            security_repo = SecurityRepository(session)

            # Create API first
            api = await metadata_repo.create(sample_api_metadata)
            await session.flush()

            sample_security_scheme.api_id = api.id

            # Test create security scheme
            created_scheme = await security_repo.create(sample_security_scheme)
            assert created_scheme.id is not None
            assert created_scheme.name == "bearerAuth"
            assert created_scheme.type == "http"

            # Test get by name
            by_name = await security_repo.get_by_name("bearerAuth", api.id)
            assert by_name is not None
            assert by_name.id == created_scheme.id

            # Test get by type
            by_type = await security_repo.get_by_type("http", api.id)
            assert len(by_type) == 1
            assert by_type[0].id == created_scheme.id

            # Test search schemes
            search_results = await security_repo.search_schemes("bearer")
            assert len(search_results) >= 1

            # Test get HTTP schemes
            http_schemes = await security_repo.get_http_schemes(api.id)
            assert len(http_schemes) == 1
            assert http_schemes[0].id == created_scheme.id

            # Test statistics
            stats = await security_repo.get_statistics(api.id)
            assert stats['total_schemes'] == 1
            assert stats['types']['http'] == 1
            assert stats['used_count'] == 1

            await session.commit()


class TestMigrationSystem:
    """Tests for migration system."""

    async def test_migration_manager_initialization(self, temp_db):
        """Test migration manager initialization."""
        migration_manager = MigrationManager(temp_db)

        await migration_manager.initialize_migration_system()

        # Check that migrations table exists
        info = await temp_db.get_database_info()
        assert 'database_migrations' in info['tables']

    async def test_builtin_migrations(self, temp_db):
        """Test built-in migrations."""
        migration_manager = MigrationManager(temp_db)

        migrations = migration_manager.get_builtin_migrations()
        assert len(migrations) >= 3  # initial_schema, fts5, performance

        # Check migration structure
        initial_migration = migrations[0]
        assert initial_migration.version == "001"
        assert initial_migration.name == "initial_schema"
        assert initial_migration.up_sql is not None
        assert initial_migration.down_sql is not None
        assert initial_migration.checksum is not None

    async def test_migration_status(self, temp_db):
        """Test migration status reporting."""
        migration_manager = MigrationManager(temp_db)
        await migration_manager.initialize_migration_system()

        status = await migration_manager.get_migration_status()
        assert 'current_version' in status
        assert 'applied_count' in status
        assert 'pending_count' in status
        assert 'applied' in status
        assert 'pending' in status
        assert 'is_up_to_date' in status

    async def test_migrate_to_latest(self, temp_db):
        """Test migrating to latest version."""
        migration_manager = MigrationManager(temp_db)
        await migration_manager.initialize_migration_system()

        # Test dry run first
        applied_versions = await migration_manager.migrate_to_latest(dry_run=True)
        assert len(applied_versions) >= 0

        # Test actual migration
        applied_versions = await migration_manager.migrate_to_latest(dry_run=False)
        assert len(applied_versions) >= 0

        # Check status after migration
        status = await migration_manager.get_migration_status()
        assert status['is_up_to_date'] is True

    async def test_database_integrity_validation(self, temp_db):
        """Test database integrity validation."""
        migration_manager = MigrationManager(temp_db)
        await migration_manager.initialize_migration_system()

        integrity = await migration_manager.validate_database_integrity()
        assert 'sqlite_integrity' in integrity
        assert 'foreign_key_violations' in integrity
        assert 'missing_tables' in integrity
        assert 'is_healthy' in integrity

        # Should be healthy after initialization
        assert integrity['is_healthy'] is True
        assert integrity['sqlite_integrity'] == ['ok']
        assert len(integrity['foreign_key_violations']) == 0


class TestBackupSystem:
    """Tests for backup system."""

    async def test_backup_manager_creation(self, temp_db):
        """Test backup manager creation and basic operations."""
        backup_manager = BackupManager(temp_db)

        # Test backup creation
        backup_path = await backup_manager.create_backup(compress=False)
        assert os.path.exists(backup_path)
        assert backup_path.endswith('.db')

        # Test compressed backup
        compressed_backup = await backup_manager.create_backup(compress=True)
        assert os.path.exists(compressed_backup)
        assert compressed_backup.endswith('.gz')

        # Test backup listing
        backups = await backup_manager.list_backups()
        assert len(backups) >= 2

        # Verify backup properties
        backup_info = backups[0]
        assert 'path' in backup_info
        assert 'size_bytes' in backup_info
        assert 'created_at' in backup_info
        assert 'compressed' in backup_info

        # Cleanup
        for backup in backups:
            if os.path.exists(backup['path']):
                os.remove(backup['path'])
            metadata_path = f"{backup['path']}.metadata"
            if os.path.exists(metadata_path):
                os.remove(metadata_path)

    async def test_backup_restore(self, temp_db, sample_api_metadata):
        """Test backup and restore functionality."""
        backup_manager = BackupManager(temp_db)

        # Add some data
        async with temp_db.get_session() as session:
            metadata_repo = MetadataRepository(session)
            await metadata_repo.create(sample_api_metadata)
            await session.commit()

        # Create backup
        backup_path = await backup_manager.create_backup(compress=False)
        assert os.path.exists(backup_path)

        # Verify data exists
        async with temp_db.get_session() as session:
            metadata_repo = MetadataRepository(session)
            apis = await metadata_repo.list()
            assert len(apis) == 1

        # Clear database (simulate data loss)
        await temp_db.execute_raw_sql("DELETE FROM api_metadata")

        # Verify data is gone
        async with temp_db.get_session() as session:
            metadata_repo = MetadataRepository(session)
            apis = await metadata_repo.list()
            assert len(apis) == 0

        # Restore from backup
        await backup_manager.restore_from_backup(backup_path)

        # Verify data is restored
        async with temp_db.get_session() as session:
            metadata_repo = MetadataRepository(session)
            apis = await metadata_repo.list()
            assert len(apis) == 1
            assert apis[0].title == "Test API"

        # Cleanup
        if os.path.exists(backup_path):
            os.remove(backup_path)

    async def test_backup_statistics(self, temp_db):
        """Test backup statistics."""
        backup_manager = BackupManager(temp_db)

        # Create a few backups
        backup_paths = []
        for i in range(3):
            compress = i % 2 == 0  # Alternate compression
            backup_path = await backup_manager.create_backup(compress=compress)
            backup_paths.append(backup_path)

        # Get statistics
        stats = await backup_manager.get_backup_statistics()
        assert stats['total_backups'] >= 3
        assert stats['total_size_bytes'] > 0
        assert stats['compressed_backups'] >= 1
        assert stats['uncompressed_backups'] >= 1
        assert stats['oldest_backup'] is not None
        assert stats['newest_backup'] is not None

        # Cleanup
        for backup_path in backup_paths:
            if os.path.exists(backup_path):
                os.remove(backup_path)
            metadata_path = f"{backup_path}.metadata"
            if os.path.exists(metadata_path):
                os.remove(metadata_path)

    async def test_backup_cleanup(self, temp_db):
        """Test backup cleanup functionality."""
        backup_manager = BackupManager(temp_db)

        # Create multiple backups
        backup_paths = []
        for i in range(5):
            backup_path = await backup_manager.create_backup(compress=False)
            backup_paths.append(backup_path)

        # Test dry run cleanup (keep only 2)
        deleted = await backup_manager.cleanup_old_backups(
            keep_count=2, dry_run=True
        )
        assert len(deleted) >= 3

        # Verify files still exist
        for backup_path in backup_paths:
            assert os.path.exists(backup_path)

        # Test actual cleanup
        deleted = await backup_manager.cleanup_old_backups(
            keep_count=2, dry_run=False
        )
        assert len(deleted) >= 3

        # Verify some files were deleted
        remaining_backups = await backup_manager.list_backups()
        assert len(remaining_backups) <= 2

        # Cleanup remaining
        for backup in remaining_backups:
            if os.path.exists(backup['path']):
                os.remove(backup['path'])


class TestPerformanceAndIntegration:
    """Performance and integration tests."""

    async def test_large_dataset_performance(self, temp_db):
        """Test performance with larger dataset."""
        import time

        async with temp_db.get_session() as session:
            metadata_repo = MetadataRepository(session)
            endpoint_repo = EndpointRepository(session)

            # Create API
            api = APIMetadata(
                title="Performance Test API",
                version="1.0.0",
                openapi_version="3.0.0",
                description="Large API for performance testing"
            )
            api = await metadata_repo.create(api)
            await session.flush()

            # Create many endpoints
            endpoints = []
            start_time = time.time()

            for i in range(100):
                endpoint = Endpoint(
                    api_id=api.id,
                    path=f"/resource{i}/{{id}}",
                    method="get",
                    operation_id=f"getResource{i}",
                    summary=f"Get resource {i}",
                    description=f"Retrieve resource number {i}",
                    searchable_text=f"get resource {i} retrieve"
                )
                endpoints.append(endpoint)

            # Batch create
            created_endpoints = await endpoint_repo.create_many(endpoints)
            creation_time = time.time() - start_time

            assert len(created_endpoints) == 100
            assert creation_time < 5.0  # Should complete in under 5 seconds

            await session.commit()

            # Test search performance
            start_time = time.time()
            search_results = await endpoint_repo.search_endpoints("resource")
            search_time = time.time() - start_time

            assert len(search_results) >= 50  # Should find many results
            assert search_time < 1.0  # Should be fast

    async def test_concurrent_access(self, temp_db):
        """Test concurrent database access."""
        async def create_api(session_manager, title_suffix):
            async with session_manager.get_session() as session:
                metadata_repo = MetadataRepository(session)
                api = APIMetadata(
                    title=f"Concurrent API {title_suffix}",
                    version="1.0.0",
                    openapi_version="3.0.0"
                )
                created_api = await metadata_repo.create(api)
                await session.commit()
                return created_api.id

        # Run multiple concurrent operations
        tasks = []
        for i in range(5):
            task = create_api(temp_db, i)
            tasks.append(task)

        # Wait for all to complete
        api_ids = await asyncio.gather(*tasks)

        assert len(api_ids) == 5
        assert len(set(api_ids)) == 5  # All unique IDs

        # Verify all APIs were created
        async with temp_db.get_session() as session:
            metadata_repo = MetadataRepository(session)
            apis = await metadata_repo.list()
            assert len(apis) == 5

    async def test_full_integration_scenario(self, temp_db):
        """Test complete integration scenario with all components."""
        # Initialize migration system
        migration_manager = MigrationManager(temp_db)
        await migration_manager.initialize_migration_system()

        # Apply migrations
        await migration_manager.migrate_to_latest()

        # Create complete API structure
        async with temp_db.get_session() as session:
            metadata_repo = MetadataRepository(session)
            endpoint_repo = EndpointRepository(session)
            schema_repo = SchemaRepository(session)
            security_repo = SecurityRepository(session)

            # Create API
            api = APIMetadata(
                title="Integration Test API",
                version="1.0.0",
                openapi_version="3.0.0",
                description="Full integration test API"
            )
            api = await metadata_repo.create(api)
            await session.flush()

            # Create security scheme
            security_scheme = SecurityScheme(
                api_id=api.id,
                name="bearerAuth",
                type="http",
                http_scheme="bearer",
                bearer_format="JWT"
            )
            security_scheme = await security_repo.create(security_scheme)

            # Create schema
            user_schema = Schema(
                api_id=api.id,
                name="User",
                type="object",
                properties={
                    "id": {"type": "string"},
                    "name": {"type": "string"}
                },
                required=["id", "name"]
            )
            user_schema = await schema_repo.create(user_schema)

            # Create endpoint
            endpoint = Endpoint(
                api_id=api.id,
                path="/users/{id}",
                method="get",
                operation_id="getUserById",
                summary="Get user by ID",
                schema_dependencies=["User"],
                security_dependencies=["bearerAuth"]
            )
            endpoint = await endpoint_repo.create(endpoint)

            await session.commit()

            # Test searches across all repositories
            api_search = await metadata_repo.search_apis("integration")
            assert len(api_search) == 1

            endpoint_search = await endpoint_repo.search_endpoints("user")
            assert len(endpoint_search) == 1

            schema_search = await schema_repo.search_schemas("user")
            assert len(schema_search) == 1

            security_search = await security_repo.search_schemes("bearer")
            assert len(security_search) == 1

        # Test backup and restore
        backup_manager = BackupManager(temp_db)
        backup_path = await backup_manager.create_backup()

        # Verify we can restore
        await backup_manager.restore_from_backup(backup_path)

        # Cleanup
        if os.path.exists(backup_path):
            os.remove(backup_path)

        # Validate final state
        integrity = await migration_manager.validate_database_integrity()
        assert integrity['is_healthy'] is True

        # Get comprehensive statistics
        async with temp_db.get_session() as session:
            metadata_repo = MetadataRepository(session)
            api_summary = await metadata_repo.get_api_summary(api.id)

            assert api_summary['counts']['endpoints'] == 1
            assert api_summary['counts']['schemas'] == 1
            assert api_summary['counts']['security_schemes'] == 1


@pytest.mark.asyncio
class TestAsyncFixtures:
    """Test fixtures and async setup."""

    async def test_temp_db_fixture(self, temp_db):
        """Test that temp_db fixture works correctly."""
        assert temp_db is not None
        assert temp_db._initialized is True

        # Test basic database operations
        health = await temp_db.health_check()
        assert health['status'] == 'healthy'

    async def test_sample_data_fixtures(
        self, sample_api_metadata, sample_endpoint, sample_schema, sample_security_scheme
    ):
        """Test that sample data fixtures are correctly configured."""
        assert sample_api_metadata.title == "Test API"
        assert sample_endpoint.path == "/users/{id}"
        assert sample_schema.name == "User"
        assert sample_security_scheme.name == "bearerAuth"

        # Test data relationships
        assert sample_endpoint.schema_dependencies == ["User"]
        assert sample_endpoint.security_dependencies == ["bearerAuth"]


# Performance benchmarks for CI/CD
@pytest.mark.performance
class TestPerformanceBenchmarks:
    """Performance benchmarks for storage layer."""

    async def test_query_response_time(self, temp_db):
        """Test that queries meet sub-200ms requirement."""
        import time

        # Setup test data
        async with temp_db.get_session() as session:
            metadata_repo = MetadataRepository(session)
            endpoint_repo = EndpointRepository(session)

            # Create API and endpoints
            api = APIMetadata(
                title="Performance API",
                version="1.0.0",
                openapi_version="3.0.0"
            )
            api = await metadata_repo.create(api)

            # Create 50 endpoints
            endpoints = []
            for i in range(50):
                endpoint = Endpoint(
                    api_id=api.id,
                    path=f"/api/v1/resource{i}",
                    method="get",
                    operation_id=f"getResource{i}",
                    searchable_text=f"get resource {i} endpoint"
                )
                endpoints.append(endpoint)

            await endpoint_repo.create_many(endpoints)
            await session.commit()

            # Test search query performance
            start_time = time.time()
            results = await endpoint_repo.search_endpoints("resource")
            query_time = (time.time() - start_time) * 1000  # Convert to milliseconds

            assert len(results) > 0
            assert query_time < 200  # Must be under 200ms

            # Test individual lookups
            start_time = time.time()
            endpoint = await endpoint_repo.get_by_operation_id("getResource0", api.id)
            lookup_time = (time.time() - start_time) * 1000

            assert endpoint is not None
            assert lookup_time < 50  # Individual lookups should be very fast

    async def test_batch_operation_performance(self, temp_db):
        """Test batch operations performance."""
        import time

        async with temp_db.get_session() as session:
            metadata_repo = MetadataRepository(session)
            endpoint_repo = EndpointRepository(session)

            # Create API
            api = APIMetadata(
                title="Batch Performance API",
                version="1.0.0",
                openapi_version="3.0.0"
            )
            api = await metadata_repo.create(api)

            # Test batch creation performance
            endpoints = []
            for i in range(200):
                endpoint = Endpoint(
                    api_id=api.id,
                    path=f"/batch/resource{i}",
                    method="get",
                    operation_id=f"getBatchResource{i}"
                )
                endpoints.append(endpoint)

            start_time = time.time()
            created_endpoints = await endpoint_repo.create_many(endpoints)
            batch_time = time.time() - start_time

            await session.commit()

            assert len(created_endpoints) == 200
            assert batch_time < 2.0  # Batch creation should be efficient

            # Test batch retrieval performance
            start_time = time.time()
            all_endpoints = await endpoint_repo.get_by_api_id(api.id)
            retrieval_time = time.time() - start_time

            assert len(all_endpoints) == 200
            assert retrieval_time < 1.0  # Batch retrieval should be fast