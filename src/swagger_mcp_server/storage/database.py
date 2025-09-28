"""Database connection management and initialization."""

import asyncio
import hashlib
import os
import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional

import aiosqlite
from sqlalchemy import create_engine, event
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from swagger_mcp_server.config.logging import get_logger
from swagger_mcp_server.storage.models import (
    ENDPOINTS_FTS_SQL,
    ENDPOINTS_FTS_TRIGGERS,
    SCHEMAS_FTS_SQL,
    SCHEMAS_FTS_TRIGGERS,
    Base,
    DatabaseMigration,
)

logger = get_logger(__name__)


class DatabaseConfig:
    """Database configuration settings."""

    def __init__(
        self,
        database_path: str = "swagger_mcp.db",
        enable_wal: bool = True,
        connection_timeout: float = 30.0,
        busy_timeout: float = 30.0,
        max_connections: int = 20,
        enable_foreign_keys: bool = True,
        enable_fts: bool = True,
        backup_enabled: bool = True,
        backup_interval: int = 3600,  # 1 hour
        vacuum_on_startup: bool = True,
    ):
        self.database_path = database_path
        self.enable_wal = enable_wal
        self.connection_timeout = connection_timeout
        self.busy_timeout = busy_timeout
        self.max_connections = max_connections
        self.enable_foreign_keys = enable_foreign_keys
        self.enable_fts = enable_fts
        self.backup_enabled = backup_enabled
        self.backup_interval = backup_interval
        self.vacuum_on_startup = vacuum_on_startup

    @property
    def database_url(self) -> str:
        """Get the database URL for SQLAlchemy."""
        return f"sqlite+aiosqlite:///{self.database_path}"

    @property
    def sync_database_url(self) -> str:
        """Get the synchronous database URL for migrations."""
        return f"sqlite:///{self.database_path}"


class DatabaseManager:
    """Manages database connections, initialization, and maintenance."""

    def __init__(self, config: Optional[DatabaseConfig] = None):
        self.config = config or DatabaseConfig()
        self.logger = get_logger(__name__)
        self._engine = None
        self._session_factory = None
        self._initialized = False
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        """Initialize the database and create necessary tables."""
        async with self._lock:
            if self._initialized:
                return

            try:
                self.logger.info(
                    "Initializing database",
                    database_path=self.config.database_path,
                )

                # Create database directory if it doesn't exist
                db_path = Path(self.config.database_path)
                db_path.parent.mkdir(parents=True, exist_ok=True)

                # Create async engine
                self._engine = create_async_engine(
                    self.config.database_url,
                    poolclass=StaticPool,
                    connect_args={
                        "check_same_thread": False,
                        "timeout": self.config.connection_timeout,
                    },
                    echo=False,  # Set to True for SQL logging
                    future=True,
                )

                # Configure SQLite settings
                await self._configure_sqlite()

                # Create session factory
                self._session_factory = async_sessionmaker(
                    self._engine, class_=AsyncSession, expire_on_commit=False
                )

                # Create tables
                async with self._engine.begin() as conn:
                    await conn.run_sync(Base.metadata.create_all)

                # Setup FTS5 tables if enabled
                if self.config.enable_fts:
                    await self._setup_fts()

                # Run migrations
                await self._run_migrations()

                # Vacuum database if configured
                if self.config.vacuum_on_startup:
                    await self._vacuum_database()

                self._initialized = True

                self.logger.info("Database initialization completed successfully")

            except Exception as e:
                self.logger.error("Database initialization failed", error=str(e))
                raise

    async def _configure_sqlite(self) -> None:
        """Configure SQLite-specific settings."""
        async with aiosqlite.connect(self.config.database_path) as conn:
            # Enable WAL mode for better concurrency
            if self.config.enable_wal:
                await conn.execute("PRAGMA journal_mode=WAL")

            # Enable foreign key constraints
            if self.config.enable_foreign_keys:
                await conn.execute("PRAGMA foreign_keys=ON")

            # Set busy timeout
            await conn.execute(
                f"PRAGMA busy_timeout={int(self.config.busy_timeout * 1000)}"
            )

            # Optimize for better performance
            await conn.execute("PRAGMA synchronous=NORMAL")
            await conn.execute("PRAGMA cache_size=10000")  # 10MB cache
            await conn.execute("PRAGMA temp_store=memory")
            await conn.execute("PRAGMA mmap_size=268435456")  # 256MB mmap

            await conn.commit()

    async def _setup_fts(self) -> None:
        """Setup FTS5 virtual tables and triggers."""
        async with aiosqlite.connect(self.config.database_path) as conn:
            try:
                # Create FTS5 tables
                await conn.execute(ENDPOINTS_FTS_SQL)
                await conn.execute(SCHEMAS_FTS_SQL)

                # Create triggers to keep FTS in sync
                for trigger_sql in ENDPOINTS_FTS_TRIGGERS:
                    await conn.execute(trigger_sql)

                for trigger_sql in SCHEMAS_FTS_TRIGGERS:
                    await conn.execute(trigger_sql)

                await conn.commit()

                self.logger.info("FTS5 tables and triggers created successfully")

            except Exception as e:
                self.logger.error("Failed to setup FTS5 tables", error=str(e))
                # Continue without FTS5 if it fails
                pass

    async def _run_migrations(self) -> None:
        """Run any pending database migrations."""
        try:
            from swagger_mcp_server.storage.migrations import MigrationManager

            migration_manager = MigrationManager(self)
            await migration_manager.initialize_migration_system()

            # Run all pending migrations
            applied_versions = await migration_manager.migrate_to_latest()

            if applied_versions:
                self.logger.info(
                    "Database migrations applied successfully",
                    applied_versions=applied_versions,
                )
            else:
                self.logger.info("Database is up to date, no migrations needed")

        except Exception as e:
            self.logger.error("Failed to run database migrations", error=str(e))
            # Don't fail initialization if migrations fail - log and continue
            # This allows manual migration handling if needed

    async def _vacuum_database(self) -> None:
        """Vacuum the database to optimize storage and performance."""
        try:
            async with aiosqlite.connect(self.config.database_path) as conn:
                await conn.execute("VACUUM")
                await conn.commit()

            self.logger.info("Database vacuum completed")
        except Exception as e:
            self.logger.warning("Database vacuum failed", error=str(e))

    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get an async database session."""
        if not self._initialized:
            await self.initialize()

        async with self._session_factory() as session:
            try:
                yield session
            except Exception as e:
                await session.rollback()
                self.logger.error("Database session error, rolling back", error=str(e))
                raise
            finally:
                await session.close()

    async def execute_raw_sql(self, sql: str, params: Optional[tuple] = None) -> Any:
        """Execute raw SQL query."""
        async with aiosqlite.connect(self.config.database_path) as conn:
            if params:
                cursor = await conn.execute(sql, params)
            else:
                cursor = await conn.execute(sql)

            result = await cursor.fetchall()
            await conn.commit()
            return result

    async def health_check(self) -> Dict[str, Any]:
        """Perform database health check."""
        try:
            # Basic connectivity test
            async with self.get_session() as session:
                result = await session.execute("SELECT 1")
                result.scalar()

            # Get database file size
            db_path = Path(self.config.database_path)
            file_size = db_path.stat().st_size if db_path.exists() else 0

            # Get table counts
            table_counts = await self._get_table_counts()

            return {
                "status": "healthy",
                "database_path": self.config.database_path,
                "file_size_bytes": file_size,
                "wal_enabled": self.config.enable_wal,
                "fts_enabled": self.config.enable_fts,
                "table_counts": table_counts,
            }

        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "database_path": self.config.database_path,
            }

    async def _get_table_counts(self) -> Dict[str, int]:
        """Get row counts for all tables."""
        counts = {}
        tables = [
            "api_metadata",
            "endpoints",
            "schemas",
            "security_schemes",
            "endpoint_dependencies",
            "database_migrations",
        ]

        try:
            for table in tables:
                result = await self.execute_raw_sql(f"SELECT COUNT(*) FROM {table}")
                counts[table] = result[0][0] if result else 0
        except Exception as e:
            self.logger.warning("Failed to get table counts", error=str(e))

        return counts

    async def create_backup(self, backup_path: Optional[str] = None) -> str:
        """Create a backup of the database."""
        if not backup_path:
            timestamp = asyncio.get_event_loop().time()
            backup_path = f"{self.config.database_path}.backup.{timestamp}"

        try:
            # Simple file copy for SQLite
            import shutil

            shutil.copy2(self.config.database_path, backup_path)

            # Verify backup integrity
            async with aiosqlite.connect(backup_path) as conn:
                await conn.execute("PRAGMA integrity_check")

            self.logger.info("Database backup created", backup_path=backup_path)

            return backup_path

        except Exception as e:
            self.logger.error(
                "Database backup failed", backup_path=backup_path, error=str(e)
            )
            raise

    async def restore_from_backup(self, backup_path: str) -> None:
        """Restore database from backup."""
        try:
            # Verify backup integrity first
            async with aiosqlite.connect(backup_path) as conn:
                result = await conn.execute("PRAGMA integrity_check")
                integrity_result = await result.fetchone()
                if integrity_result[0] != "ok":
                    raise ValueError(
                        f"Backup integrity check failed: {integrity_result[0]}"
                    )

            # Close existing connections
            if self._engine:
                await self._engine.dispose()

            # Replace current database
            import shutil

            shutil.copy2(backup_path, self.config.database_path)

            # Reinitialize
            self._initialized = False
            await self.initialize()

            self.logger.info("Database restored from backup", backup_path=backup_path)

        except Exception as e:
            self.logger.error(
                "Database restore failed",
                backup_path=backup_path,
                error=str(e),
            )
            raise

    async def get_database_info(self) -> Dict[str, Any]:
        """Get detailed database information."""
        try:
            async with aiosqlite.connect(self.config.database_path) as conn:
                # Get SQLite version
                cursor = await conn.execute("SELECT sqlite_version()")
                sqlite_version = (await cursor.fetchone())[0]

                # Get database size
                cursor = await conn.execute("PRAGMA page_count")
                page_count = (await cursor.fetchone())[0]

                cursor = await conn.execute("PRAGMA page_size")
                page_size = (await cursor.fetchone())[0]

                database_size = page_count * page_size

                # Get table information
                cursor = await conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
                )
                tables = [row[0] for row in await cursor.fetchall()]

                # Get index information
                cursor = await conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='index' ORDER BY name"
                )
                indexes = [row[0] for row in await cursor.fetchall()]

                return {
                    "sqlite_version": sqlite_version,
                    "database_size_bytes": database_size,
                    "page_count": page_count,
                    "page_size": page_size,
                    "tables": tables,
                    "indexes": indexes,
                    "table_counts": await self._get_table_counts(),
                }

        except Exception as e:
            self.logger.error("Failed to get database info", error=str(e))
            return {"error": str(e)}

    async def get_migration_status(self) -> Dict[str, Any]:
        """Get database migration status."""
        try:
            from swagger_mcp_server.storage.migrations import MigrationManager

            migration_manager = MigrationManager(self)
            return await migration_manager.get_migration_status()
        except Exception as e:
            self.logger.error("Failed to get migration status", error=str(e))
            return {"error": str(e)}

    async def apply_migrations(self, dry_run: bool = False) -> List[str]:
        """Apply pending migrations manually."""
        try:
            from swagger_mcp_server.storage.migrations import MigrationManager

            migration_manager = MigrationManager(self)
            await migration_manager.initialize_migration_system()
            return await migration_manager.migrate_to_latest(dry_run=dry_run)
        except Exception as e:
            self.logger.error("Failed to apply migrations", error=str(e))
            raise

    async def validate_integrity(self) -> Dict[str, Any]:
        """Validate database integrity."""
        try:
            from swagger_mcp_server.storage.migrations import MigrationManager

            migration_manager = MigrationManager(self)
            return await migration_manager.validate_database_integrity()
        except Exception as e:
            self.logger.error("Failed to validate database integrity", error=str(e))
            return {"error": str(e)}

    async def close(self) -> None:
        """Close database connections and cleanup."""
        if self._engine:
            await self._engine.dispose()
            self._engine = None

        self._session_factory = None
        self._initialized = False

        self.logger.info("Database connections closed")


# Global database manager instance
_db_manager: Optional[DatabaseManager] = None
_db_config: Optional[DatabaseConfig] = None


def configure_database(config: DatabaseConfig) -> None:
    """Configure the global database instance."""
    global _db_config
    _db_config = config


def get_db_manager() -> DatabaseManager:
    """Get the global database manager instance."""
    global _db_manager, _db_config

    if _db_manager is None:
        config = _db_config or DatabaseConfig()
        _db_manager = DatabaseManager(config)

    return _db_manager


async def initialize_database(
    config: Optional[DatabaseConfig] = None,
) -> DatabaseManager:
    """Initialize and return the database manager."""
    if config:
        configure_database(config)

    db_manager = get_db_manager()
    await db_manager.initialize()
    return db_manager
