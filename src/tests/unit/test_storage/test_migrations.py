"""Tests for database migration system."""

import asyncio
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from swagger_mcp_server.storage.database import DatabaseConfig, DatabaseManager
from swagger_mcp_server.storage.migrations import (
    Migration,
    MigrationError,
    MigrationManager,
)
from swagger_mcp_server.storage.models import DatabaseMigration


@pytest.fixture
async def temp_db():
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as temp_file:
        temp_path = temp_file.name

    config = DatabaseConfig(
        database_path=temp_path,
        enable_wal=False,  # Disable WAL for simpler testing
        enable_fts=True,
        vacuum_on_startup=False,
    )

    db_manager = DatabaseManager(config)
    await db_manager.initialize()

    yield db_manager

    # Cleanup
    await db_manager.close()
    if os.path.exists(temp_path):
        os.unlink(temp_path)


@pytest.fixture
def sample_migration():
    """Create a sample migration for testing."""
    return Migration(
        version="999",
        name="test_migration",
        description="Test migration for unit tests",
        up_sql="CREATE TABLE test_table (id INTEGER PRIMARY KEY, name TEXT);",
        down_sql="DROP TABLE IF EXISTS test_table;",
    )


@pytest.mark.unit
class TestMigration:
    """Test the Migration class."""

    def test_migration_creation(self):
        """Test migration creation with all fields."""
        migration = Migration(
            version="001",
            name="initial_schema",
            description="Create initial schema",
            up_sql="CREATE TABLE test (id INTEGER);",
            down_sql="DROP TABLE test;",
        )

        assert migration.version == "001"
        assert migration.name == "initial_schema"
        assert migration.description == "Create initial schema"
        assert migration.up_sql == "CREATE TABLE test (id INTEGER);"
        assert migration.down_sql == "DROP TABLE test;"
        assert migration.checksum is not None
        assert len(migration.checksum) == 64  # SHA-256 hex digest

    def test_migration_checksum_consistency(self):
        """Test that migration checksum is consistent."""
        migration1 = Migration(
            version="001",
            name="test",
            up_sql="CREATE TABLE test (id INTEGER);",
            down_sql="DROP TABLE test;",
        )

        migration2 = Migration(
            version="001",
            name="test",
            up_sql="CREATE TABLE test (id INTEGER);",
            down_sql="DROP TABLE test;",
        )

        assert migration1.checksum == migration2.checksum

    def test_migration_checksum_different(self):
        """Test that different migrations have different checksums."""
        migration1 = Migration(
            version="001",
            name="test",
            up_sql="CREATE TABLE test1 (id INTEGER);",
            down_sql="DROP TABLE test1;",
        )

        migration2 = Migration(
            version="001",
            name="test",
            up_sql="CREATE TABLE test2 (id INTEGER);",
            down_sql="DROP TABLE test2;",
        )

        assert migration1.checksum != migration2.checksum

    def test_migration_to_dict(self):
        """Test migration serialization to dictionary."""
        migration = Migration(
            version="001",
            name="test",
            description="Test migration",
            up_sql="CREATE TABLE test (id INTEGER);",
            down_sql="DROP TABLE test;",
        )

        result = migration.to_dict()

        expected_keys = {
            "version",
            "name",
            "up_sql",
            "down_sql",
            "description",
            "checksum",
        }
        assert set(result.keys()) == expected_keys
        assert result["version"] == "001"
        assert result["name"] == "test"
        assert result["description"] == "Test migration"


@pytest.mark.unit
class TestMigrationManager:
    """Test the MigrationManager class."""

    async def test_initialization(self, temp_db):
        """Test migration system initialization."""
        migration_manager = MigrationManager(temp_db)
        await migration_manager.initialize_migration_system()

        # Check that migrations table was created
        result = await temp_db.execute_raw_sql(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='database_migrations'"
        )
        assert len(result) == 1

    async def test_get_applied_migrations_empty(self, temp_db):
        """Test getting applied migrations when none exist."""
        migration_manager = MigrationManager(temp_db)
        await migration_manager.initialize_migration_system()

        applied = await migration_manager.get_applied_migrations()
        assert applied == []

    async def test_get_current_version_none(self, temp_db):
        """Test getting current version when no migrations applied."""
        migration_manager = MigrationManager(temp_db)
        await migration_manager.initialize_migration_system()

        version = await migration_manager.get_current_version()
        assert version is None

    async def test_get_builtin_migrations(self, temp_db):
        """Test getting built-in migrations."""
        migration_manager = MigrationManager(temp_db)
        migrations = migration_manager.get_builtin_migrations()

        assert len(migrations) >= 3  # At least initial schema, FTS5, performance
        versions = [m.version for m in migrations]
        assert "001" in versions  # initial_schema
        assert "002" in versions  # add_fts5_indexes
        assert "003" in versions  # add_performance_indexes

        # Check migration properties
        for migration in migrations:
            assert migration.version
            assert migration.name
            assert migration.up_sql
            assert migration.checksum

    async def test_apply_migration_success(self, temp_db, sample_migration):
        """Test successful migration application."""
        migration_manager = MigrationManager(temp_db)
        await migration_manager.initialize_migration_system()

        # Apply migration
        success = await migration_manager.apply_migration(sample_migration)
        assert success

        # Check that table was created
        result = await temp_db.execute_raw_sql(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='test_table'"
        )
        assert len(result) == 1

        # Check migration was recorded
        applied = await migration_manager.get_applied_migrations()
        assert len(applied) == 1
        assert applied[0].version == sample_migration.version
        assert applied[0].name == sample_migration.name

    async def test_apply_migration_dry_run(self, temp_db, sample_migration):
        """Test migration dry run."""
        migration_manager = MigrationManager(temp_db)
        await migration_manager.initialize_migration_system()

        # Apply migration in dry run mode
        success = await migration_manager.apply_migration(
            sample_migration, dry_run=True
        )
        assert success

        # Check that table was NOT created
        result = await temp_db.execute_raw_sql(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='test_table'"
        )
        assert len(result) == 0

        # Check migration was NOT recorded
        applied = await migration_manager.get_applied_migrations()
        assert len(applied) == 0

    async def test_apply_migration_failure_rollback(self, temp_db):
        """Test migration failure and rollback."""
        migration_manager = MigrationManager(temp_db)
        await migration_manager.initialize_migration_system()

        # Create migration with invalid SQL
        invalid_migration = Migration(
            version="998",
            name="invalid_migration",
            up_sql="CREATE TABLE invalid ( invalid_syntax ERROR );",
            down_sql="DROP TABLE IF EXISTS invalid;",
        )

        # Apply migration should fail
        with pytest.raises(MigrationError):
            await migration_manager.apply_migration(invalid_migration)

        # Check migration was NOT recorded
        applied = await migration_manager.get_applied_migrations()
        assert len(applied) == 0

    async def test_rollback_migration_success(self, temp_db, sample_migration):
        """Test successful migration rollback."""
        migration_manager = MigrationManager(temp_db)
        await migration_manager.initialize_migration_system()

        # Apply migration first
        await migration_manager.apply_migration(sample_migration)

        # Verify table exists
        result = await temp_db.execute_raw_sql(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='test_table'"
        )
        assert len(result) == 1

        # Rollback migration
        success = await migration_manager.rollback_migration(sample_migration.version)
        assert success

        # Check that table was dropped
        result = await temp_db.execute_raw_sql(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='test_table'"
        )
        assert len(result) == 0

        # Check migration record was removed
        applied = await migration_manager.get_applied_migrations()
        assert len(applied) == 0

    async def test_rollback_migration_not_found(self, temp_db):
        """Test rollback of non-existent migration."""
        migration_manager = MigrationManager(temp_db)
        await migration_manager.initialize_migration_system()

        # Try to rollback non-existent migration
        with pytest.raises(MigrationError, match="Migration 999 not found"):
            await migration_manager.rollback_migration("999")

    async def test_rollback_migration_no_rollback_sql(self, temp_db):
        """Test rollback of migration without rollback SQL."""
        migration_manager = MigrationManager(temp_db)
        await migration_manager.initialize_migration_system()

        # Create migration without rollback SQL
        migration_no_rollback = Migration(
            version="997",
            name="no_rollback",
            up_sql="CREATE TABLE no_rollback (id INTEGER);",
            down_sql=None,
        )

        await migration_manager.apply_migration(migration_no_rollback)

        # Try to rollback
        with pytest.raises(MigrationError, match="does not have rollback SQL"):
            await migration_manager.rollback_migration("997")

    async def test_migrate_to_latest(self, temp_db):
        """Test migrating to latest version."""
        migration_manager = MigrationManager(temp_db)

        # Apply all migrations
        applied_versions = await migration_manager.migrate_to_latest()

        # Check that migrations were applied
        assert len(applied_versions) >= 3
        assert "001" in applied_versions
        assert "002" in applied_versions
        assert "003" in applied_versions

        # Check current version
        current_version = await migration_manager.get_current_version()
        assert current_version == max(applied_versions)

        # Run again - should be no pending migrations
        applied_versions_2 = await migration_manager.migrate_to_latest()
        assert applied_versions_2 == []

    async def test_migrate_to_latest_dry_run(self, temp_db):
        """Test migrate to latest in dry run mode."""
        migration_manager = MigrationManager(temp_db)

        # Apply all migrations in dry run
        applied_versions = await migration_manager.migrate_to_latest(dry_run=True)

        # Check that migrations would be applied
        assert len(applied_versions) >= 3

        # Check that no migrations were actually applied
        actual_applied = await migration_manager.get_applied_migrations()
        assert len(actual_applied) == 0

    async def test_get_migration_status(self, temp_db, sample_migration):
        """Test getting migration status."""
        migration_manager = MigrationManager(temp_db)
        await migration_manager.initialize_migration_system()

        # Get status before any migrations
        status = await migration_manager.get_migration_status()
        assert status["current_version"] is None
        assert status["applied_count"] == 0
        assert status["pending_count"] >= 3  # Built-in migrations
        assert not status["is_up_to_date"]

        # Apply one migration
        await migration_manager.apply_migration(sample_migration)

        # Get status again
        status = await migration_manager.get_migration_status()
        assert status["current_version"] == sample_migration.version
        assert status["applied_count"] == 1

    async def test_validate_database_integrity(self, temp_db):
        """Test database integrity validation."""
        migration_manager = MigrationManager(temp_db)
        await migration_manager.migrate_to_latest()

        # Validate integrity
        integrity = await migration_manager.validate_database_integrity()

        assert integrity["is_healthy"]
        assert integrity["sqlite_integrity"] == ["ok"]
        assert len(integrity["foreign_key_violations"]) == 0
        assert len(integrity["missing_tables"]) == 0

        # Check required tables are present
        required_tables = {
            "api_metadata",
            "endpoints",
            "schemas",
            "security_schemes",
            "endpoint_dependencies",
        }
        existing_tables = set()
        tables_result = await temp_db.execute_raw_sql(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        for row in tables_result:
            existing_tables.add(row[0])

        assert required_tables.issubset(existing_tables)

    async def test_reset_database(self, temp_db, sample_migration):
        """Test database reset functionality."""
        migration_manager = MigrationManager(temp_db)
        await migration_manager.initialize_migration_system()

        # Apply a migration
        await migration_manager.apply_migration(sample_migration)

        # Verify migration was applied
        applied = await migration_manager.get_applied_migrations()
        assert len(applied) == 1

        # Reset database (requires confirmation)
        with pytest.raises(MigrationError, match="requires explicit confirmation"):
            await migration_manager.reset_database(confirm=False)

        # Reset with confirmation
        await migration_manager.reset_database(confirm=True)

        # Check that all migrations are gone
        applied = await migration_manager.get_applied_migrations()
        assert len(applied) == 0

        # Check that test table is gone
        result = await temp_db.execute_raw_sql(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='test_table'"
        )
        assert len(result) == 0


@pytest.mark.integration
class TestMigrationIntegration:
    """Integration tests for migration system."""

    async def test_database_manager_migration_integration(self, temp_db):
        """Test integration between DatabaseManager and migration system."""
        # Test migration status
        status = await temp_db.get_migration_status()
        assert "current_version" in status
        assert "applied_count" in status
        assert "pending_count" in status

        # Test manual migration application
        applied = await temp_db.apply_migrations(dry_run=True)
        assert len(applied) >= 3

        # Test integrity validation
        integrity = await temp_db.validate_integrity()
        assert "is_healthy" in integrity
        assert integrity["is_healthy"]

    async def test_full_migration_lifecycle(self, temp_db):
        """Test complete migration lifecycle."""
        migration_manager = MigrationManager(temp_db)

        # Start with clean database
        await migration_manager.initialize_migration_system()

        # Check initial state
        status = await migration_manager.get_migration_status()
        assert not status["is_up_to_date"]
        assert status["pending_count"] >= 3

        # Apply all migrations
        applied = await migration_manager.migrate_to_latest()
        assert len(applied) >= 3

        # Verify final state
        status = await migration_manager.get_migration_status()
        assert status["is_up_to_date"]
        assert status["pending_count"] == 0
        assert status["applied_count"] >= 3

        # Verify database integrity
        integrity = await migration_manager.validate_database_integrity()
        assert integrity["is_healthy"]


@pytest.mark.performance
class TestMigrationPerformance:
    """Performance tests for migration system."""

    async def test_migration_speed(self, temp_db):
        """Test that migrations complete within reasonable time."""
        import time

        migration_manager = MigrationManager(temp_db)

        start_time = time.time()
        await migration_manager.migrate_to_latest()
        end_time = time.time()

        migration_time = end_time - start_time

        # Migrations should complete within 5 seconds
        assert (
            migration_time < 5.0
        ), f"Migrations took {migration_time:.2f}s, expected < 5.0s"

    async def test_integrity_check_speed(self, temp_db):
        """Test that integrity checks complete quickly."""
        import time

        migration_manager = MigrationManager(temp_db)
        await migration_manager.migrate_to_latest()

        start_time = time.time()
        integrity = await migration_manager.validate_database_integrity()
        end_time = time.time()

        check_time = end_time - start_time

        # Integrity check should complete within 1 second
        assert (
            check_time < 1.0
        ), f"Integrity check took {check_time:.2f}s, expected < 1.0s"
        assert integrity["is_healthy"]
