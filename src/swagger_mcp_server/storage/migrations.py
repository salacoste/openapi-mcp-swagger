"""Database migration system for schema versioning and evolution."""

import hashlib
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import aiosqlite
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from swagger_mcp_server.config.logging import get_logger
from swagger_mcp_server.storage.database import DatabaseManager
from swagger_mcp_server.storage.models import DatabaseMigration

logger = get_logger(__name__)


class MigrationError(Exception):
    """Base exception for migration operations."""

    pass


class Migration:
    """Represents a single database migration."""

    def __init__(
        self,
        version: str,
        name: str,
        up_sql: str,
        down_sql: Optional[str] = None,
        description: Optional[str] = None,
    ):
        self.version = version
        self.name = name
        self.up_sql = up_sql
        self.down_sql = down_sql
        self.description = description
        self.checksum = self._calculate_checksum()

    def _calculate_checksum(self) -> str:
        """Calculate SHA-256 checksum of the migration content."""
        content = f"{self.version}{self.name}{self.up_sql}{self.down_sql or ''}"
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        """Convert migration to dictionary."""
        return {
            "version": self.version,
            "name": self.name,
            "up_sql": self.up_sql,
            "down_sql": self.down_sql,
            "description": self.description,
            "checksum": self.checksum,
        }


class MigrationManager:
    """Manages database migrations and schema versioning."""

    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.logger = get_logger(__name__)
        self.migrations_dir = Path(__file__).parent / "migration_scripts"
        self.migrations_dir.mkdir(exist_ok=True)

    async def initialize_migration_system(self) -> None:
        """Initialize the migration system and create the migrations table."""
        try:
            # Ensure database is initialized
            await self.db_manager.initialize()

            # Create migrations table if it doesn't exist
            create_migrations_table = """
            CREATE TABLE IF NOT EXISTS database_migrations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                version TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                rollback_sql TEXT,
                checksum TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """

            await self.db_manager.execute_raw_sql(create_migrations_table)

            self.logger.info("Migration system initialized successfully")

        except Exception as e:
            self.logger.error("Failed to initialize migration system", error=str(e))
            raise MigrationError(f"Failed to initialize migration system: {str(e)}")

    async def get_applied_migrations(self) -> List[DatabaseMigration]:
        """Get list of applied migrations."""
        try:
            async with self.db_manager.get_session() as session:
                stmt = select(DatabaseMigration).order_by(DatabaseMigration.version)
                result = await session.execute(stmt)
                migrations = result.scalars().all()
                return list(migrations)

        except Exception as e:
            self.logger.error("Failed to get applied migrations", error=str(e))
            raise MigrationError(f"Failed to get applied migrations: {str(e)}")

    async def get_current_version(self) -> Optional[str]:
        """Get the current database schema version."""
        try:
            applied = await self.get_applied_migrations()
            if applied:
                return applied[-1].version
            return None

        except Exception as e:
            self.logger.error("Failed to get current version", error=str(e))
            raise MigrationError(f"Failed to get current version: {str(e)}")

    def get_builtin_migrations(self) -> List[Migration]:
        """Get built-in migrations for the current schema."""
        migrations = [
            Migration(
                version="001",
                name="initial_schema",
                description="Create initial database schema with all tables",
                up_sql=self._get_initial_schema_sql(),
                down_sql=self._get_drop_all_tables_sql(),
            ),
            Migration(
                version="002",
                name="add_fts5_indexes",
                description="Add FTS5 full-text search indexes",
                up_sql=self._get_fts5_setup_sql(),
                down_sql=self._get_fts5_teardown_sql(),
            ),
            Migration(
                version="003",
                name="add_performance_indexes",
                description="Add performance-optimized indexes",
                up_sql=self._get_performance_indexes_sql(),
                down_sql=self._get_drop_performance_indexes_sql(),
            ),
        ]
        return migrations

    def _get_initial_schema_sql(self) -> str:
        """Get SQL for initial schema creation."""
        return """
        -- API Metadata table
        CREATE TABLE IF NOT EXISTS api_metadata (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            version TEXT NOT NULL,
            openapi_version TEXT NOT NULL,
            description TEXT,
            base_url TEXT,
            contact_info TEXT, -- JSON
            license_info TEXT, -- JSON
            servers TEXT, -- JSON
            external_docs TEXT, -- JSON
            extensions TEXT, -- JSON
            specification_hash TEXT,
            file_path TEXT,
            file_size INTEGER,
            parse_metadata TEXT, -- JSON
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- Endpoints table
        CREATE TABLE IF NOT EXISTS endpoints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            api_id INTEGER NOT NULL REFERENCES api_metadata(id) ON DELETE CASCADE,
            path TEXT NOT NULL,
            method TEXT NOT NULL,
            operation_id TEXT,
            summary TEXT,
            description TEXT,
            tags TEXT, -- JSON
            parameters TEXT, -- JSON
            request_body TEXT, -- JSON
            responses TEXT, -- JSON
            security TEXT, -- JSON
            callbacks TEXT, -- JSON
            deprecated BOOLEAN DEFAULT FALSE,
            extensions TEXT, -- JSON
            searchable_text TEXT,
            parameter_names TEXT, -- JSON
            response_codes TEXT, -- JSON
            content_types TEXT, -- JSON
            schema_dependencies TEXT, -- JSON
            security_dependencies TEXT, -- JSON
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(api_id, path, method)
        );

        -- Schemas table
        CREATE TABLE IF NOT EXISTS schemas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            api_id INTEGER NOT NULL REFERENCES api_metadata(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            title TEXT,
            type TEXT,
            format TEXT,
            description TEXT,
            properties TEXT, -- JSON
            required TEXT, -- JSON
            additional_properties TEXT, -- JSON
            items TEXT, -- JSON
            enum TEXT, -- JSON
            example TEXT, -- JSON
            default_value TEXT, -- JSON (renamed from 'default' to avoid keyword)
            minimum TEXT, -- JSON
            maximum TEXT, -- JSON
            min_length INTEGER,
            max_length INTEGER,
            pattern TEXT,
            min_items INTEGER,
            max_items INTEGER,
            unique_items BOOLEAN,
            all_of TEXT, -- JSON
            one_of TEXT, -- JSON
            any_of TEXT, -- JSON
            not_schema TEXT, -- JSON
            deprecated BOOLEAN DEFAULT FALSE,
            read_only BOOLEAN DEFAULT FALSE,
            write_only BOOLEAN DEFAULT FALSE,
            extensions TEXT, -- JSON
            searchable_text TEXT,
            property_names TEXT, -- JSON
            schema_dependencies TEXT, -- JSON
            reference_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(api_id, name)
        );

        -- Security schemes table
        CREATE TABLE IF NOT EXISTS security_schemes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            api_id INTEGER NOT NULL REFERENCES api_metadata(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            type TEXT NOT NULL,
            description TEXT,
            api_key_name TEXT,
            api_key_location TEXT,
            http_scheme TEXT,
            bearer_format TEXT,
            oauth2_flows TEXT, -- JSON
            openid_connect_url TEXT,
            extensions TEXT, -- JSON
            reference_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(api_id, name)
        );

        -- Endpoint dependencies table
        CREATE TABLE IF NOT EXISTS endpoint_dependencies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            endpoint_id INTEGER NOT NULL REFERENCES endpoints(id) ON DELETE CASCADE,
            schema_id INTEGER NOT NULL REFERENCES schemas(id) ON DELETE CASCADE,
            dependency_type TEXT NOT NULL,
            context TEXT, -- JSON
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(endpoint_id, schema_id, dependency_type)
        );

        -- Basic indexes for performance
        CREATE INDEX IF NOT EXISTS ix_api_metadata_title_version ON api_metadata(title, version);
        CREATE INDEX IF NOT EXISTS ix_api_metadata_specification_hash ON api_metadata(specification_hash);
        CREATE INDEX IF NOT EXISTS ix_endpoints_api_id ON endpoints(api_id);
        CREATE INDEX IF NOT EXISTS ix_endpoints_method ON endpoints(method);
        CREATE INDEX IF NOT EXISTS ix_endpoints_path ON endpoints(path);
        CREATE INDEX IF NOT EXISTS ix_endpoints_operation_id ON endpoints(operation_id);
        CREATE INDEX IF NOT EXISTS ix_schemas_api_id ON schemas(api_id);
        CREATE INDEX IF NOT EXISTS ix_schemas_name ON schemas(name);
        CREATE INDEX IF NOT EXISTS ix_schemas_type ON schemas(type);
        CREATE INDEX IF NOT EXISTS ix_security_schemes_api_id ON security_schemes(api_id);
        CREATE INDEX IF NOT EXISTS ix_security_schemes_name ON security_schemes(name);
        CREATE INDEX IF NOT EXISTS ix_security_schemes_type ON security_schemes(type);
        """

    def _get_fts5_setup_sql(self) -> str:
        """Get SQL for FTS5 setup."""
        from swagger_mcp_server.storage.models import (
            ENDPOINTS_FTS_SQL,
            ENDPOINTS_FTS_TRIGGERS,
            SCHEMAS_FTS_SQL,
            SCHEMAS_FTS_TRIGGERS,
        )

        sql_parts = [
            ENDPOINTS_FTS_SQL,
            SCHEMAS_FTS_SQL,
            *ENDPOINTS_FTS_TRIGGERS,
            *SCHEMAS_FTS_TRIGGERS,
        ]

        return "\n\n".join(sql_parts)

    def _get_performance_indexes_sql(self) -> str:
        """Get SQL for performance indexes."""
        return """
        -- Additional performance indexes
        CREATE INDEX IF NOT EXISTS ix_endpoints_deprecated ON endpoints(deprecated);
        CREATE INDEX IF NOT EXISTS ix_endpoints_searchable_text ON endpoints(searchable_text);
        CREATE INDEX IF NOT EXISTS ix_schemas_deprecated ON schemas(deprecated);
        CREATE INDEX IF NOT EXISTS ix_schemas_reference_count ON schemas(reference_count);
        CREATE INDEX IF NOT EXISTS ix_schemas_searchable_text ON schemas(searchable_text);
        CREATE INDEX IF NOT EXISTS ix_security_schemes_reference_count ON security_schemes(reference_count);
        CREATE INDEX IF NOT EXISTS ix_endpoint_dependencies_endpoint_id ON endpoint_dependencies(endpoint_id);
        CREATE INDEX IF NOT EXISTS ix_endpoint_dependencies_schema_id ON endpoint_dependencies(schema_id);
        CREATE INDEX IF NOT EXISTS ix_endpoint_dependencies_type ON endpoint_dependencies(dependency_type);

        -- Composite indexes for common queries
        CREATE INDEX IF NOT EXISTS ix_endpoints_api_method ON endpoints(api_id, method);
        CREATE INDEX IF NOT EXISTS ix_endpoints_api_deprecated ON endpoints(api_id, deprecated);
        CREATE INDEX IF NOT EXISTS ix_schemas_api_type ON schemas(api_id, type);
        CREATE INDEX IF NOT EXISTS ix_schemas_api_deprecated ON schemas(api_id, deprecated);
        """

    def _get_drop_all_tables_sql(self) -> str:
        """Get SQL to drop all tables."""
        return """
        DROP TABLE IF EXISTS endpoint_dependencies;
        DROP TABLE IF EXISTS security_schemes;
        DROP TABLE IF EXISTS schemas;
        DROP TABLE IF EXISTS endpoints;
        DROP TABLE IF EXISTS api_metadata;
        """

    def _get_fts5_teardown_sql(self) -> str:
        """Get SQL to drop FTS5 tables and triggers."""
        return """
        DROP TRIGGER IF EXISTS endpoints_fts_insert;
        DROP TRIGGER IF EXISTS endpoints_fts_delete;
        DROP TRIGGER IF EXISTS endpoints_fts_update;
        DROP TRIGGER IF EXISTS schemas_fts_insert;
        DROP TRIGGER IF EXISTS schemas_fts_delete;
        DROP TRIGGER IF EXISTS schemas_fts_update;
        DROP TABLE IF EXISTS endpoints_fts;
        DROP TABLE IF EXISTS schemas_fts;
        """

    def _get_drop_performance_indexes_sql(self) -> str:
        """Get SQL to drop performance indexes."""
        return """
        DROP INDEX IF EXISTS ix_endpoints_deprecated;
        DROP INDEX IF EXISTS ix_endpoints_searchable_text;
        DROP INDEX IF EXISTS ix_schemas_deprecated;
        DROP INDEX IF EXISTS ix_schemas_reference_count;
        DROP INDEX IF EXISTS ix_schemas_searchable_text;
        DROP INDEX IF EXISTS ix_security_schemes_reference_count;
        DROP INDEX IF EXISTS ix_endpoint_dependencies_endpoint_id;
        DROP INDEX IF EXISTS ix_endpoint_dependencies_schema_id;
        DROP INDEX IF EXISTS ix_endpoint_dependencies_type;
        DROP INDEX IF EXISTS ix_endpoints_api_method;
        DROP INDEX IF EXISTS ix_endpoints_api_deprecated;
        DROP INDEX IF EXISTS ix_schemas_api_type;
        DROP INDEX IF EXISTS ix_schemas_api_deprecated;
        """

    async def apply_migration(
        self, migration: Migration, dry_run: bool = False
    ) -> bool:
        """Apply a single migration."""
        try:
            self.logger.info(
                "Applying migration",
                version=migration.version,
                name=migration.name,
                dry_run=dry_run,
            )

            if dry_run:
                self.logger.info(
                    "DRY RUN - Would execute SQL",
                    sql=migration.up_sql[:200] + "..."
                    if len(migration.up_sql) > 200
                    else migration.up_sql,
                )
                return True

            # Create backup before migration
            backup_path = await self.db_manager.create_backup(
                f"{self.db_manager.config.database_path}.pre_migration_{migration.version}"
            )

            try:
                # Execute migration SQL
                await self.db_manager.execute_raw_sql(migration.up_sql)

                # Record migration in database
                async with self.db_manager.get_session() as session:
                    migration_record = DatabaseMigration(
                        version=migration.version,
                        name=migration.name,
                        applied_at=datetime.now(timezone.utc),
                        rollback_sql=migration.down_sql,
                        checksum=migration.checksum,
                    )

                    session.add(migration_record)
                    await session.commit()

                self.logger.info(
                    "Migration applied successfully",
                    version=migration.version,
                    name=migration.name,
                )

                return True

            except Exception as e:
                self.logger.error(
                    "Migration failed, restoring backup",
                    version=migration.version,
                    name=migration.name,
                    error=str(e),
                )

                # Restore from backup
                await self.db_manager.restore_from_backup(backup_path)
                raise

        except Exception as e:
            self.logger.error(
                "Failed to apply migration",
                version=migration.version,
                name=migration.name,
                error=str(e),
            )
            raise MigrationError(
                f"Failed to apply migration {migration.version}: {str(e)}"
            )

    async def rollback_migration(self, version: str, dry_run: bool = False) -> bool:
        """Rollback a migration."""
        try:
            self.logger.info("Rolling back migration", version=version, dry_run=dry_run)

            # Get migration record
            async with self.db_manager.get_session() as session:
                stmt = select(DatabaseMigration).where(
                    DatabaseMigration.version == version
                )
                result = await session.execute(stmt)
                migration_record = result.scalar_one_or_none()

                if not migration_record:
                    raise MigrationError(f"Migration {version} not found")

                if not migration_record.rollback_sql:
                    raise MigrationError(
                        f"Migration {version} does not have rollback SQL"
                    )

                if dry_run:
                    self.logger.info(
                        "DRY RUN - Would execute rollback SQL",
                        sql=migration_record.rollback_sql[:200] + "..."
                        if len(migration_record.rollback_sql) > 200
                        else migration_record.rollback_sql,
                    )
                    return True

                # Create backup before rollback
                backup_path = await self.db_manager.create_backup(
                    f"{self.db_manager.config.database_path}.pre_rollback_{version}"
                )

                try:
                    # Execute rollback SQL
                    await self.db_manager.execute_raw_sql(migration_record.rollback_sql)

                    # Remove migration record
                    await session.delete(migration_record)
                    await session.commit()

                    self.logger.info(
                        "Migration rolled back successfully", version=version
                    )

                    return True

                except Exception as e:
                    self.logger.error(
                        "Rollback failed, restoring backup",
                        version=version,
                        error=str(e),
                    )

                    # Restore from backup
                    await self.db_manager.restore_from_backup(backup_path)
                    raise

        except Exception as e:
            self.logger.error(
                "Failed to rollback migration", version=version, error=str(e)
            )
            raise MigrationError(f"Failed to rollback migration {version}: {str(e)}")

    async def migrate_to_latest(self, dry_run: bool = False) -> List[str]:
        """Apply all pending migrations to bring database to latest version."""
        try:
            await self.initialize_migration_system()

            applied_migrations = await self.get_applied_migrations()
            applied_versions = {m.version for m in applied_migrations}

            available_migrations = self.get_builtin_migrations()
            pending_migrations = [
                m for m in available_migrations if m.version not in applied_versions
            ]

            # Sort by version
            pending_migrations.sort(key=lambda x: x.version)

            if not pending_migrations:
                self.logger.info("No pending migrations found")
                return []

            applied_versions_list = []

            for migration in pending_migrations:
                success = await self.apply_migration(migration, dry_run)
                if success:
                    applied_versions_list.append(migration.version)
                else:
                    break

            if applied_versions_list:
                self.logger.info(
                    "Migrations completed",
                    applied_versions=applied_versions_list,
                    dry_run=dry_run,
                )

            return applied_versions_list

        except Exception as e:
            self.logger.error("Failed to migrate to latest", error=str(e))
            raise MigrationError(f"Failed to migrate to latest: {str(e)}")

    async def get_migration_status(self) -> Dict[str, Any]:
        """Get detailed migration status."""
        try:
            await self.initialize_migration_system()

            applied_migrations = await self.get_applied_migrations()
            available_migrations = self.get_builtin_migrations()

            applied_versions = {m.version: m for m in applied_migrations}
            available_versions = {m.version: m for m in available_migrations}

            pending = []
            applied = []
            unknown = []

            for version, migration in available_versions.items():
                if version in applied_versions:
                    applied_record = applied_versions[version]
                    applied.append(
                        {
                            "version": version,
                            "name": migration.name,
                            "description": migration.description,
                            "applied_at": applied_record.applied_at.isoformat()
                            if applied_record.applied_at
                            else None,
                            "checksum_matches": applied_record.checksum
                            == migration.checksum,
                        }
                    )
                else:
                    pending.append(
                        {
                            "version": version,
                            "name": migration.name,
                            "description": migration.description,
                        }
                    )

            # Check for unknown applied migrations
            for version, applied_record in applied_versions.items():
                if version not in available_versions:
                    unknown.append(
                        {
                            "version": version,
                            "name": applied_record.name,
                            "applied_at": applied_record.applied_at.isoformat()
                            if applied_record.applied_at
                            else None,
                        }
                    )

            current_version = await self.get_current_version()

            return {
                "current_version": current_version,
                "applied_count": len(applied),
                "pending_count": len(pending),
                "unknown_count": len(unknown),
                "applied": applied,
                "pending": pending,
                "unknown": unknown,
                "is_up_to_date": len(pending) == 0,
            }

        except Exception as e:
            self.logger.error("Failed to get migration status", error=str(e))
            raise MigrationError(f"Failed to get migration status: {str(e)}")

    async def validate_database_integrity(self) -> Dict[str, Any]:
        """Validate database integrity after migrations."""
        try:
            integrity_results = {}

            # SQLite integrity check
            integrity_result = await self.db_manager.execute_raw_sql(
                "PRAGMA integrity_check"
            )
            integrity_results["sqlite_integrity"] = [row[0] for row in integrity_result]

            # Foreign key check
            fk_result = await self.db_manager.execute_raw_sql(
                "PRAGMA foreign_key_check"
            )
            integrity_results["foreign_key_violations"] = [
                {
                    "table": row[0],
                    "rowid": row[1],
                    "parent": row[2],
                    "fkid": row[3],
                }
                for row in fk_result
            ]

            # Check for required tables
            tables_result = await self.db_manager.execute_raw_sql(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )
            existing_tables = {row[0] for row in tables_result}

            required_tables = {
                "api_metadata",
                "endpoints",
                "schemas",
                "security_schemes",
                "endpoint_dependencies",
                "database_migrations",
            }

            missing_tables = required_tables - existing_tables
            integrity_results["missing_tables"] = list(missing_tables)

            # Check for FTS tables if applicable
            fts_tables = {"endpoints_fts", "schemas_fts"}
            existing_fts = fts_tables & existing_tables
            integrity_results["fts_tables"] = list(existing_fts)

            # Overall status
            is_healthy = (
                integrity_results["sqlite_integrity"] == ["ok"]
                and len(integrity_results["foreign_key_violations"]) == 0
                and len(integrity_results["missing_tables"]) == 0
            )

            integrity_results["is_healthy"] = is_healthy

            return integrity_results

        except Exception as e:
            self.logger.error("Failed to validate database integrity", error=str(e))
            raise MigrationError(f"Failed to validate database integrity: {str(e)}")

    async def reset_database(self, confirm: bool = False) -> None:
        """Reset database to initial state (WARNING: destroys all data)."""
        if not confirm:
            raise MigrationError("Database reset requires explicit confirmation")

        try:
            self.logger.warning("RESETTING DATABASE - ALL DATA WILL BE LOST")

            # Create final backup
            backup_path = await self.db_manager.create_backup(
                f"{self.db_manager.config.database_path}.pre_reset"
            )

            self.logger.info(f"Final backup created: {backup_path}")

            # Drop all tables
            drop_sql = self._get_drop_all_tables_sql()
            await self.db_manager.execute_raw_sql(drop_sql)

            # Drop FTS tables
            fts_drop_sql = self._get_fts5_teardown_sql()
            await self.db_manager.execute_raw_sql(fts_drop_sql)

            # Drop migrations table
            await self.db_manager.execute_raw_sql(
                "DROP TABLE IF EXISTS database_migrations"
            )

            # Reinitialize
            await self.initialize_migration_system()

            self.logger.info("Database reset completed successfully")

        except Exception as e:
            self.logger.error("Failed to reset database", error=str(e))
            raise MigrationError(f"Failed to reset database: {str(e)}")
