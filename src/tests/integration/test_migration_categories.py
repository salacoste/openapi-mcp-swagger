"""Integration tests for category migration (Migration 004).

Epic 6: Hierarchical Endpoint Catalog System - Story 6.1
Tests database migration for endpoint categorization feature.
"""

import pytest
from sqlalchemy import inspect, select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from swagger_mcp_server.storage.database import DatabaseManager
from swagger_mcp_server.storage.migrations import MigrationManager
from swagger_mcp_server.storage.models import APIMetadata, Base, Endpoint, EndpointCategory


@pytest.mark.integration
class TestCategoryMigration:
    """Test category migration (004) upgrade and downgrade."""

    @pytest.fixture
    async def db_session(self, temp_db):
        """Create async database session for testing."""
        engine = create_async_engine(f"sqlite+aiosqlite:///{temp_db}")
        async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        session = async_session()
        try:
            yield session
        finally:
            await session.close()
            await engine.dispose()

    @pytest.fixture
    async def migration_manager(self, temp_db):
        """Create migration manager for testing."""
        engine = create_async_engine(f"sqlite+aiosqlite:///{temp_db}")
        manager = MigrationManager(engine)
        yield manager
        await engine.dispose()

    async def test_migration_upgrade_empty_database(self, db_session, migration_manager):
        """Test migration upgrade on empty database creates all tables and columns."""
        # Apply migration 004
        await migration_manager.upgrade(target_version=4)

        # Verify endpoints table has new category columns
        result = await db_session.execute(
            text("PRAGMA table_info(endpoints)")
        )
        columns = {row[1]: row[2] for row in result.fetchall()}

        assert "category" in columns
        assert "category_group" in columns
        assert "category_display_name" in columns
        assert "category_metadata" in columns

        # Verify endpoint_categories table exists
        result = await db_session.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='endpoint_categories'")
        )
        tables = result.fetchall()
        assert len(tables) == 1

        # Verify endpoint_categories table structure
        result = await db_session.execute(
            text("PRAGMA table_info(endpoint_categories)")
        )
        columns = {row[1]: row[2] for row in result.fetchall()}

        assert "category_name" in columns
        assert "display_name" in columns
        assert "description" in columns
        assert "category_group" in columns
        assert "endpoint_count" in columns
        assert "http_methods" in columns
        assert "api_id" in columns

        # Verify indexes exist
        result = await db_session.execute(
            text("SELECT name FROM sqlite_master WHERE type='index'")
        )
        indexes = {row[0] for row in result.fetchall()}

        assert "idx_endpoints_category" in indexes
        assert "idx_endpoints_category_group" in indexes
        assert "idx_categories_group" in indexes
        assert "idx_categories_api_id" in indexes

    async def test_migration_upgrade_populated_database(self, db_session, migration_manager):
        """Test migration upgrade on database with existing endpoints preserves data."""
        # Create test API metadata
        api = APIMetadata(
            title="Test API",
            version="1.0.0",
            base_url="https://api.test.com",
            source_type="openapi",
        )
        db_session.add(api)
        await db_session.commit()
        await db_session.refresh(api)

        # Create test endpoints before migration
        endpoints = [
            Endpoint(
                api_id=api.id,
                path="/users",
                method="get",
                operation_id="listUsers",
                summary="List users",
            ),
            Endpoint(
                api_id=api.id,
                path="/users",
                method="post",
                operation_id="createUser",
                summary="Create user",
            ),
        ]
        for endpoint in endpoints:
            db_session.add(endpoint)
        await db_session.commit()

        # Get endpoint IDs before migration
        endpoint_ids = [e.id for e in endpoints]

        # Apply migration 004
        await migration_manager.upgrade(target_version=4)

        # Verify existing endpoints still exist
        result = await db_session.execute(
            select(Endpoint).where(Endpoint.id.in_(endpoint_ids))
        )
        migrated_endpoints = result.scalars().all()

        assert len(migrated_endpoints) == 2

        # Verify new category fields are NULL (backward compatible)
        for endpoint in migrated_endpoints:
            assert endpoint.category is None
            assert endpoint.category_group is None
            assert endpoint.category_display_name is None
            assert endpoint.category_metadata is None

    async def test_migration_downgrade(self, db_session, migration_manager):
        """Test migration downgrade removes category tables and columns."""
        # First upgrade to create tables
        await migration_manager.upgrade(target_version=4)

        # Add some test category data
        await db_session.execute(
            text("""
                INSERT INTO endpoint_categories
                (category_name, display_name, endpoint_count, http_methods, api_id)
                VALUES ('test', 'Test Category', 5, '["GET", "POST"]', 1)
            """)
        )
        await db_session.commit()

        # Now downgrade
        await migration_manager.downgrade(target_version=3)

        # Verify endpoints table no longer has category columns
        result = await db_session.execute(
            text("PRAGMA table_info(endpoints)")
        )
        columns = {row[1] for row in result.fetchall()}

        assert "category" not in columns
        assert "category_group" not in columns
        assert "category_display_name" not in columns
        assert "category_metadata" not in columns

        # Verify endpoint_categories table is dropped
        result = await db_session.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='endpoint_categories'")
        )
        tables = result.fetchall()
        assert len(tables) == 0

    async def test_category_data_persistence(self, db_session, migration_manager):
        """Test category data persists correctly after migration."""
        # Apply migration
        await migration_manager.upgrade(target_version=4)

        # Create test API
        api = APIMetadata(
            title="Test API",
            version="1.0.0",
            base_url="https://api.test.com",
            source_type="openapi",
        )
        db_session.add(api)
        await db_session.commit()
        await db_session.refresh(api)

        # Create endpoint with category data
        endpoint = Endpoint(
            api_id=api.id,
            path="/campaigns",
            method="get",
            operation_id="listCampaigns",
            summary="List campaigns",
            category="campaign",
            category_group="Performance API",
            category_display_name="Campaign Management",
            category_metadata={"original_tag": "Campaign"},
        )
        db_session.add(endpoint)
        await db_session.commit()
        await db_session.refresh(endpoint)

        # Create category catalog entry
        await db_session.execute(
            text("""
                INSERT INTO endpoint_categories
                (category_name, display_name, description, category_group, endpoint_count, http_methods, api_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """),
            [
                "campaign",
                "Campaign Management",
                "Campaign operations",
                "Performance API",
                1,
                '["GET"]',
                api.id,
            ],
        )
        await db_session.commit()

        # Query endpoint and verify category data
        result = await db_session.execute(
            select(Endpoint).where(Endpoint.id == endpoint.id)
        )
        saved_endpoint = result.scalar_one()

        assert saved_endpoint.category == "campaign"
        assert saved_endpoint.category_group == "Performance API"
        assert saved_endpoint.category_display_name == "Campaign Management"
        assert saved_endpoint.category_metadata == {"original_tag": "Campaign"}

        # Query category catalog and verify
        result = await db_session.execute(
            text("SELECT * FROM endpoint_categories WHERE category_name = ?"),
            ["campaign"],
        )
        category_row = result.fetchone()

        assert category_row is not None
        assert category_row[0] == "campaign"  # category_name
        assert category_row[1] == "Campaign Management"  # display_name
        assert category_row[3] == "Performance API"  # category_group
        assert category_row[4] == 1  # endpoint_count

    async def test_fts_index_with_category_filtering(self, db_session, migration_manager):
        """Test FTS5 index includes category field for searching."""
        # Apply migration
        await migration_manager.upgrade(target_version=4)

        # Create test API
        api = APIMetadata(
            title="Test API",
            version="1.0.0",
            base_url="https://api.test.com",
            source_type="openapi",
        )
        db_session.add(api)
        await db_session.commit()
        await db_session.refresh(api)

        # Create endpoints with categories
        endpoints = [
            Endpoint(
                api_id=api.id,
                path="/campaigns",
                method="get",
                operation_id="listCampaigns",
                summary="List all campaigns",
                category="campaign",
            ),
            Endpoint(
                api_id=api.id,
                path="/statistics",
                method="get",
                operation_id="getStatistics",
                summary="Get statistics",
                category="statistics",
            ),
        ]
        for endpoint in endpoints:
            db_session.add(endpoint)
        await db_session.commit()

        # Verify FTS search with category filtering works
        result = await db_session.execute(
            text("""
                SELECT e.* FROM endpoints e
                JOIN endpoints_fts ON e.id = endpoints_fts.rowid
                WHERE endpoints_fts MATCH 'campaign'
                  AND LOWER(e.category) = LOWER('campaign')
            """)
        )
        rows = result.fetchall()

        # Should find the campaign endpoint
        assert len(rows) >= 1

    async def test_backward_compatibility_with_existing_queries(self, db_session, migration_manager):
        """Test migration doesn't break existing endpoint queries."""
        # Apply migration
        await migration_manager.upgrade(target_version=4)

        # Create test API and endpoints
        api = APIMetadata(
            title="Test API",
            version="1.0.0",
            base_url="https://api.test.com",
            source_type="openapi",
        )
        db_session.add(api)
        await db_session.commit()
        await db_session.refresh(api)

        endpoint = Endpoint(
            api_id=api.id,
            path="/test",
            method="get",
            operation_id="test",
            summary="Test endpoint",
        )
        db_session.add(endpoint)
        await db_session.commit()

        # Test existing query patterns still work
        result = await db_session.execute(
            select(Endpoint).where(Endpoint.api_id == api.id)
        )
        endpoints = result.scalars().all()
        assert len(endpoints) == 1

        result = await db_session.execute(
            select(Endpoint).where(
                Endpoint.path == "/test",
                Endpoint.method == "get",
            )
        )
        endpoint = result.scalar_one()
        assert endpoint.operation_id == "test"