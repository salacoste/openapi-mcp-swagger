"""Database backup and recovery utilities."""

import asyncio
import gzip
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiosqlite

from swagger_mcp_server.config.logging import get_logger
from swagger_mcp_server.storage.database import DatabaseManager

logger = get_logger(__name__)


class BackupError(Exception):
    """Base exception for backup operations."""

    pass


class BackupManager:
    """Manages database backup and recovery operations."""

    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.logger = get_logger(__name__)

    async def create_backup(
        self,
        backup_path: Optional[str] = None,
        compress: bool = True,
        include_metadata: bool = True,
    ) -> str:
        """Create a database backup."""
        try:
            if not backup_path:
                timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
                backup_name = f"swagger_mcp_backup_{timestamp}"
                backup_path = f"{self.db_manager.config.database_path}.{backup_name}"

            if compress and not backup_path.endswith(".gz"):
                backup_path += ".gz"

            self.logger.info(
                "Creating database backup",
                backup_path=backup_path,
                compress=compress,
            )

            # Ensure the database is properly closed for backup
            await self._ensure_database_synced()

            if compress:
                await self._create_compressed_backup(backup_path, include_metadata)
            else:
                await self._create_simple_backup(backup_path, include_metadata)

            # Verify backup integrity
            await self._verify_backup_integrity(backup_path, compress)

            backup_size = os.path.getsize(backup_path)
            self.logger.info(
                "Database backup created successfully",
                backup_path=backup_path,
                size_bytes=backup_size,
                compressed=compress,
            )

            return backup_path

        except Exception as e:
            self.logger.error(
                "Failed to create database backup",
                backup_path=backup_path,
                error=str(e),
            )
            raise BackupError(f"Failed to create backup: {str(e)}")

    async def _ensure_database_synced(self) -> None:
        """Ensure database is synced to disk."""
        try:
            # WAL checkpoint to ensure all data is written
            async with aiosqlite.connect(self.db_manager.config.database_path) as conn:
                await conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                await conn.commit()

        except Exception as e:
            self.logger.warning("Failed to sync database", error=str(e))

    async def _create_simple_backup(
        self, backup_path: str, include_metadata: bool
    ) -> None:
        """Create a simple file copy backup."""
        # Simple file copy for SQLite
        shutil.copy2(self.db_manager.config.database_path, backup_path)

        if include_metadata:
            await self._add_backup_metadata(backup_path)

    async def _create_compressed_backup(
        self, backup_path: str, include_metadata: bool
    ) -> None:
        """Create a compressed backup."""
        with open(self.db_manager.config.database_path, "rb") as source:
            with gzip.open(backup_path, "wb") as target:
                shutil.copyfileobj(source, target)

        if include_metadata:
            await self._add_backup_metadata(backup_path)

    async def _add_backup_metadata(self, backup_path: str) -> None:
        """Add metadata file alongside backup."""
        try:
            metadata = await self._collect_backup_metadata()
            metadata_path = f"{backup_path}.metadata"

            with open(metadata_path, "w") as f:
                import json

                json.dump(metadata, f, indent=2, default=str)

        except Exception as e:
            self.logger.warning(
                "Failed to create backup metadata",
                backup_path=backup_path,
                error=str(e),
            )

    async def _collect_backup_metadata(self) -> Dict[str, Any]:
        """Collect metadata about the backup."""
        try:
            db_info = await self.db_manager.get_database_info()
            health_check = await self.db_manager.health_check()

            return {
                "backup_created_at": datetime.now(timezone.utc).isoformat(),
                "database_path": self.db_manager.config.database_path,
                "database_info": db_info,
                "health_check": health_check,
                "config": {
                    "enable_wal": self.db_manager.config.enable_wal,
                    "enable_fts": self.db_manager.config.enable_fts,
                },
            }

        except Exception as e:
            self.logger.warning("Failed to collect backup metadata", error=str(e))
            return {
                "backup_created_at": datetime.now(timezone.utc).isoformat(),
                "error": str(e),
            }

    async def _verify_backup_integrity(
        self, backup_path: str, is_compressed: bool
    ) -> None:
        """Verify backup file integrity."""
        try:
            if is_compressed:
                await self._verify_compressed_backup(backup_path)
            else:
                await self._verify_simple_backup(backup_path)

        except Exception as e:
            raise BackupError(f"Backup integrity verification failed: {str(e)}")

    async def _verify_simple_backup(self, backup_path: str) -> None:
        """Verify a simple backup file."""
        # Try to open the backup database and run integrity check
        async with aiosqlite.connect(backup_path) as conn:
            cursor = await conn.execute("PRAGMA integrity_check")
            result = await cursor.fetchone()
            if result[0] != "ok":
                raise BackupError(f"Backup integrity check failed: {result[0]}")

    async def _verify_compressed_backup(self, backup_path: str) -> None:
        """Verify a compressed backup file."""
        # Extract to temporary file and verify
        with tempfile.NamedTemporaryFile(suffix=".db") as temp_file:
            with gzip.open(backup_path, "rb") as compressed:
                shutil.copyfileobj(compressed, temp_file)
                temp_file.flush()

            await self._verify_simple_backup(temp_file.name)

    async def restore_from_backup(
        self,
        backup_path: str,
        target_path: Optional[str] = None,
        verify_before_restore: bool = True,
    ) -> None:
        """Restore database from backup."""
        try:
            if not os.path.exists(backup_path):
                raise BackupError(f"Backup file not found: {backup_path}")

            if not target_path:
                target_path = self.db_manager.config.database_path

            is_compressed = backup_path.endswith(".gz")

            self.logger.info(
                "Restoring database from backup",
                backup_path=backup_path,
                target_path=target_path,
                compressed=is_compressed,
            )

            # Verify backup integrity before restore
            if verify_before_restore:
                await self._verify_backup_integrity(backup_path, is_compressed)

            # Create backup of current database if it exists
            current_backup_path = None
            if os.path.exists(target_path):
                current_backup_path = await self._backup_current_database(target_path)

            try:
                # Close existing connections
                if self.db_manager._engine:
                    await self.db_manager._engine.dispose()

                # Restore the backup
                if is_compressed:
                    await self._restore_compressed_backup(backup_path, target_path)
                else:
                    await self._restore_simple_backup(backup_path, target_path)

                # Reinitialize database manager
                self.db_manager._initialized = False
                await self.db_manager.initialize()

                # Verify restored database
                health_check = await self.db_manager.health_check()
                if health_check["status"] != "healthy":
                    raise BackupError(
                        f"Restored database failed health check: {health_check}"
                    )

                self.logger.info(
                    "Database restored successfully",
                    backup_path=backup_path,
                    target_path=target_path,
                )

            except Exception as e:
                # Restore original database if restore failed
                if current_backup_path and os.path.exists(current_backup_path):
                    self.logger.info(
                        "Restore failed, reverting to original database",
                        current_backup=current_backup_path,
                    )
                    shutil.copy2(current_backup_path, target_path)

                raise

        except Exception as e:
            self.logger.error(
                "Failed to restore from backup",
                backup_path=backup_path,
                target_path=target_path,
                error=str(e),
            )
            raise BackupError(f"Failed to restore from backup: {str(e)}")

    async def _backup_current_database(self, target_path: str) -> str:
        """Create backup of current database before restore."""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        current_backup_path = f"{target_path}.pre_restore_{timestamp}"
        shutil.copy2(target_path, current_backup_path)
        return current_backup_path

    async def _restore_simple_backup(self, backup_path: str, target_path: str) -> None:
        """Restore from a simple backup file."""
        shutil.copy2(backup_path, target_path)

    async def _restore_compressed_backup(
        self, backup_path: str, target_path: str
    ) -> None:
        """Restore from a compressed backup file."""
        with gzip.open(backup_path, "rb") as source:
            with open(target_path, "wb") as target:
                shutil.copyfileobj(source, target)

    async def list_backups(
        self, backup_dir: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List available backup files."""
        try:
            if not backup_dir:
                backup_dir = str(Path(self.db_manager.config.database_path).parent)

            backup_pattern = Path(self.db_manager.config.database_path).name
            backup_files = []

            for file_path in Path(backup_dir).glob(f"{backup_pattern}*"):
                if file_path.is_file() and not file_path.name.endswith(".metadata"):
                    try:
                        stat = file_path.stat()
                        backup_info = {
                            "path": str(file_path),
                            "name": file_path.name,
                            "size_bytes": stat.st_size,
                            "created_at": datetime.fromtimestamp(
                                stat.st_ctime, timezone.utc
                            ),
                            "modified_at": datetime.fromtimestamp(
                                stat.st_mtime, timezone.utc
                            ),
                            "compressed": file_path.name.endswith(".gz"),
                            "has_metadata": (
                                file_path.parent / f"{file_path.name}.metadata"
                            ).exists(),
                        }

                        # Load metadata if available
                        metadata_path = file_path.parent / f"{file_path.name}.metadata"
                        if metadata_path.exists():
                            try:
                                import json

                                with open(metadata_path, "r") as f:
                                    metadata = json.load(f)
                                backup_info["metadata"] = metadata
                            except Exception as e:
                                self.logger.warning(
                                    "Failed to load backup metadata",
                                    metadata_path=str(metadata_path),
                                    error=str(e),
                                )

                        backup_files.append(backup_info)

                    except Exception as e:
                        self.logger.warning(
                            "Failed to get backup file info",
                            file_path=str(file_path),
                            error=str(e),
                        )

            # Sort by creation time (newest first)
            backup_files.sort(key=lambda x: x["created_at"], reverse=True)

            return backup_files

        except Exception as e:
            self.logger.error(
                "Failed to list backups", backup_dir=backup_dir, error=str(e)
            )
            raise BackupError(f"Failed to list backups: {str(e)}")

    async def cleanup_old_backups(
        self,
        keep_count: int = 10,
        max_age_days: Optional[int] = 30,
        backup_dir: Optional[str] = None,
        dry_run: bool = False,
    ) -> List[str]:
        """Clean up old backup files."""
        try:
            backups = await self.list_backups(backup_dir)

            if not backups:
                return []

            to_delete = []

            # Delete by count (keep only the most recent N backups)
            if len(backups) > keep_count:
                old_backups_by_count = backups[keep_count:]
                to_delete.extend(old_backups_by_count)

            # Delete by age
            if max_age_days:
                cutoff_date = datetime.now(timezone.utc).replace(
                    hour=0, minute=0, second=0, microsecond=0
                ) - datetime.timedelta(days=max_age_days)

                old_backups_by_age = [
                    backup for backup in backups if backup["created_at"] < cutoff_date
                ]
                to_delete.extend(old_backups_by_age)

            # Remove duplicates
            to_delete = list({backup["path"]: backup for backup in to_delete}.values())

            if not to_delete:
                self.logger.info("No old backups to clean up")
                return []

            deleted_paths = []

            for backup in to_delete:
                try:
                    if dry_run:
                        self.logger.info(
                            "DRY RUN - Would delete backup",
                            path=backup["path"],
                        )
                    else:
                        os.remove(backup["path"])
                        # Also remove metadata file if it exists
                        metadata_path = f"{backup['path']}.metadata"
                        if os.path.exists(metadata_path):
                            os.remove(metadata_path)

                        self.logger.info("Deleted old backup", path=backup["path"])

                    deleted_paths.append(backup["path"])

                except Exception as e:
                    self.logger.error(
                        "Failed to delete backup",
                        path=backup["path"],
                        error=str(e),
                    )

            self.logger.info(
                "Backup cleanup completed",
                deleted_count=len(deleted_paths),
                keep_count=keep_count,
                max_age_days=max_age_days,
                dry_run=dry_run,
            )

            return deleted_paths

        except Exception as e:
            self.logger.error(
                "Failed to cleanup old backups",
                keep_count=keep_count,
                max_age_days=max_age_days,
                error=str(e),
            )
            raise BackupError(f"Failed to cleanup old backups: {str(e)}")

    async def create_incremental_backup(
        self, base_backup_path: str, incremental_path: Optional[str] = None
    ) -> str:
        """Create an incremental backup (SQLite doesn't support this natively)."""
        # For SQLite, we create a full backup but document it as incremental
        # A true incremental backup would require WAL file management
        self.logger.warning(
            "SQLite incremental backup creates full backup - "
            "true incremental backup not supported"
        )

        if not incremental_path:
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            incremental_path = f"{base_backup_path}.incremental_{timestamp}.gz"

        return await self.create_backup(incremental_path, compress=True)

    async def get_backup_statistics(
        self, backup_dir: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get statistics about backup files."""
        try:
            backups = await self.list_backups(backup_dir)

            if not backups:
                return {
                    "total_backups": 0,
                    "total_size_bytes": 0,
                    "compressed_backups": 0,
                    "oldest_backup": None,
                    "newest_backup": None,
                    "average_size_bytes": 0,
                }

            total_size = sum(backup["size_bytes"] for backup in backups)
            compressed_count = sum(1 for backup in backups if backup["compressed"])

            return {
                "total_backups": len(backups),
                "total_size_bytes": total_size,
                "compressed_backups": compressed_count,
                "uncompressed_backups": len(backups) - compressed_count,
                "oldest_backup": backups[-1]["created_at"] if backups else None,
                "newest_backup": backups[0]["created_at"] if backups else None,
                "average_size_bytes": total_size // len(backups) if backups else 0,
                "compression_ratio": (
                    compressed_count / len(backups) * 100 if backups else 0
                ),
            }

        except Exception as e:
            self.logger.error(
                "Failed to get backup statistics",
                backup_dir=backup_dir,
                error=str(e),
            )
            raise BackupError(f"Failed to get backup statistics: {str(e)}")
