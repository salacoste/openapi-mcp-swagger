"""Repository for API metadata data access operations."""

from typing import Any, Dict, List, Optional

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from swagger_mcp_server.config.logging import get_logger
from swagger_mcp_server.storage.models import APIMetadata
from swagger_mcp_server.storage.repositories.base import (
    BaseRepository,
    RepositoryError,
)

logger = get_logger(__name__)


class MetadataRepository(BaseRepository[APIMetadata]):
    """Repository for API metadata data access operations."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, APIMetadata)

    async def get_by_title_version(
        self, title: str, version: str
    ) -> Optional[APIMetadata]:
        """Get API metadata by title and version."""
        try:
            stmt = select(APIMetadata).where(
                and_(APIMetadata.title == title, APIMetadata.version == version)
            )

            result = await self.session.execute(stmt)
            metadata = result.scalar_one_or_none()

            return metadata

        except Exception as e:
            self.logger.error(
                "Failed to get API metadata by title and version",
                title=title,
                version=version,
                error=str(e),
            )
            raise RepositoryError(f"Failed to get API metadata: {str(e)}")

    async def get_by_specification_hash(self, spec_hash: str) -> Optional[APIMetadata]:
        """Get API metadata by specification hash."""
        try:
            stmt = select(APIMetadata).where(
                APIMetadata.specification_hash == spec_hash
            )

            result = await self.session.execute(stmt)
            metadata = result.scalar_one_or_none()

            return metadata

        except Exception as e:
            self.logger.error(
                "Failed to get API metadata by specification hash",
                spec_hash=spec_hash,
                error=str(e),
            )
            raise RepositoryError(f"Failed to get API metadata by hash: {str(e)}")

    async def get_by_file_path(self, file_path: str) -> Optional[APIMetadata]:
        """Get API metadata by file path."""
        try:
            stmt = select(APIMetadata).where(APIMetadata.file_path == file_path)

            result = await self.session.execute(stmt)
            metadata = result.scalar_one_or_none()

            return metadata

        except Exception as e:
            self.logger.error(
                "Failed to get API metadata by file path",
                file_path=file_path,
                error=str(e),
            )
            raise RepositoryError(f"Failed to get API metadata by file path: {str(e)}")

    async def search_apis(
        self,
        query: str,
        openapi_version: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[APIMetadata]:
        """Search APIs by title, description, and other metadata."""
        try:
            if not query.strip():
                return await self._filter_apis(openapi_version, limit, offset)

            # Text search conditions
            search_terms = query.split()
            text_conditions = []

            for term in search_terms:
                term_pattern = f"%{term}%"
                term_conditions = or_(
                    APIMetadata.title.ilike(term_pattern),
                    APIMetadata.description.ilike(term_pattern),
                    APIMetadata.version.ilike(term_pattern),
                    APIMetadata.base_url.ilike(term_pattern),
                )
                text_conditions.append(term_conditions)

            stmt = select(APIMetadata)
            if text_conditions:
                stmt = stmt.where(and_(*text_conditions))

            # Additional filters
            if openapi_version:
                stmt = stmt.where(APIMetadata.openapi_version == openapi_version)

            stmt = stmt.order_by(APIMetadata.title, APIMetadata.version)
            stmt = stmt.limit(limit).offset(offset)

            result = await self.session.execute(stmt)
            apis = result.scalars().all()

            return list(apis)

        except Exception as e:
            self.logger.error("Failed to search APIs", query=query, error=str(e))
            raise RepositoryError(f"Failed to search APIs: {str(e)}")

    async def _filter_apis(
        self,
        openapi_version: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[APIMetadata]:
        """Filter APIs without text search."""
        filters = {}

        if openapi_version:
            filters["openapi_version"] = openapi_version

        return await self.list(
            limit=limit, offset=offset, filters=filters, order_by="title"
        )

    async def get_all_titles(self) -> List[str]:
        """Get all unique API titles."""
        try:
            stmt = select(APIMetadata.title).distinct().order_by(APIMetadata.title)

            result = await self.session.execute(stmt)
            titles = result.scalars().all()

            return list(titles)

        except Exception as e:
            self.logger.error("Failed to get all API titles", error=str(e))
            raise RepositoryError(f"Failed to get all API titles: {str(e)}")

    async def get_versions_for_title(self, title: str) -> List[str]:
        """Get all versions for a specific API title."""
        try:
            stmt = select(APIMetadata.version).where(APIMetadata.title == title)
            stmt = stmt.order_by(APIMetadata.version.desc())

            result = await self.session.execute(stmt)
            versions = result.scalars().all()

            return list(versions)

        except Exception as e:
            self.logger.error(
                "Failed to get versions for API title",
                title=title,
                error=str(e),
            )
            raise RepositoryError(f"Failed to get versions for API title: {str(e)}")

    async def get_latest_version(self, title: str) -> Optional[APIMetadata]:
        """Get the latest version of an API by title."""
        try:
            stmt = select(APIMetadata).where(APIMetadata.title == title)
            stmt = stmt.order_by(APIMetadata.created_at.desc())
            stmt = stmt.limit(1)

            result = await self.session.execute(stmt)
            metadata = result.scalar_one_or_none()

            return metadata

        except Exception as e:
            self.logger.error("Failed to get latest version", title=title, error=str(e))
            raise RepositoryError(f"Failed to get latest version: {str(e)}")

    async def get_by_openapi_version(self, openapi_version: str) -> List[APIMetadata]:
        """Get all APIs by OpenAPI version."""
        try:
            stmt = select(APIMetadata).where(
                APIMetadata.openapi_version == openapi_version
            )
            stmt = stmt.order_by(APIMetadata.title, APIMetadata.version)

            result = await self.session.execute(stmt)
            apis = result.scalars().all()

            return list(apis)

        except Exception as e:
            self.logger.error(
                "Failed to get APIs by OpenAPI version",
                openapi_version=openapi_version,
                error=str(e),
            )
            raise RepositoryError(f"Failed to get APIs by OpenAPI version: {str(e)}")

    async def get_all_openapi_versions(self) -> List[str]:
        """Get all unique OpenAPI versions."""
        try:
            stmt = select(APIMetadata.openapi_version).distinct()
            stmt = stmt.order_by(APIMetadata.openapi_version)

            result = await self.session.execute(stmt)
            versions = result.scalars().all()

            return list(versions)

        except Exception as e:
            self.logger.error("Failed to get all OpenAPI versions", error=str(e))
            raise RepositoryError(f"Failed to get all OpenAPI versions: {str(e)}")

    async def get_large_apis(
        self, size_threshold_bytes: int = 1048576
    ) -> List[APIMetadata]:
        """Get APIs larger than the specified size threshold (default 1MB)."""
        try:
            stmt = select(APIMetadata).where(
                APIMetadata.file_size >= size_threshold_bytes
            )
            stmt = stmt.order_by(APIMetadata.file_size.desc())

            result = await self.session.execute(stmt)
            apis = result.scalars().all()

            return list(apis)

        except Exception as e:
            self.logger.error(
                "Failed to get large APIs",
                size_threshold=size_threshold_bytes,
                error=str(e),
            )
            raise RepositoryError(f"Failed to get large APIs: {str(e)}")

    async def get_recently_added(self, limit: int = 10) -> List[APIMetadata]:
        """Get recently added APIs."""
        try:
            stmt = select(APIMetadata).order_by(APIMetadata.created_at.desc())
            stmt = stmt.limit(limit)

            result = await self.session.execute(stmt)
            apis = result.scalars().all()

            return list(apis)

        except Exception as e:
            self.logger.error(
                "Failed to get recently added APIs", limit=limit, error=str(e)
            )
            raise RepositoryError(f"Failed to get recently added APIs: {str(e)}")

    async def get_recently_updated(self, limit: int = 10) -> List[APIMetadata]:
        """Get recently updated APIs."""
        try:
            stmt = select(APIMetadata).order_by(APIMetadata.updated_at.desc())
            stmt = stmt.limit(limit)

            result = await self.session.execute(stmt)
            apis = result.scalars().all()

            return list(apis)

        except Exception as e:
            self.logger.error(
                "Failed to get recently updated APIs",
                limit=limit,
                error=str(e),
            )
            raise RepositoryError(f"Failed to get recently updated APIs: {str(e)}")

    async def get_statistics(self) -> Dict[str, Any]:
        """Get API metadata statistics."""
        try:
            # Total count
            total_query = select(func.count()).select_from(APIMetadata)
            total_result = await self.session.execute(total_query)
            total_apis = total_result.scalar() or 0

            # OpenAPI version distribution
            version_query = select(
                APIMetadata.openapi_version,
                func.count(APIMetadata.openapi_version).label("count"),
            ).group_by(APIMetadata.openapi_version)

            version_result = await self.session.execute(version_query)
            versions = {
                row.openapi_version: row.count for row in version_result.fetchall()
            }

            # File size statistics
            size_query = select(
                func.min(APIMetadata.file_size).label("min_size"),
                func.max(APIMetadata.file_size).label("max_size"),
                func.avg(APIMetadata.file_size).label("avg_size"),
            ).where(APIMetadata.file_size.isnot(None))

            size_result = await self.session.execute(size_query)
            size_stats = size_result.fetchone()

            # Count APIs with different components
            with_contact_query = select(func.count()).where(
                APIMetadata.contact_info.isnot(None)
            )
            with_contact_result = await self.session.execute(with_contact_query)
            with_contact = with_contact_result.scalar() or 0

            with_license_query = select(func.count()).where(
                APIMetadata.license_info.isnot(None)
            )
            with_license_result = await self.session.execute(with_license_query)
            with_license = with_license_result.scalar() or 0

            with_servers_query = select(func.count()).where(
                APIMetadata.servers.isnot(None)
            )
            with_servers_result = await self.session.execute(with_servers_query)
            with_servers = with_servers_result.scalar() or 0

            # Unique titles (may have multiple versions)
            unique_titles_query = select(func.count(func.distinct(APIMetadata.title)))
            unique_titles_result = await self.session.execute(unique_titles_query)
            unique_titles = unique_titles_result.scalar() or 0

            return {
                "total_apis": total_apis,
                "unique_titles": unique_titles,
                "openapi_versions": versions,
                "file_size": {
                    "min_bytes": size_stats.min_size if size_stats else 0,
                    "max_bytes": size_stats.max_size if size_stats else 0,
                    "avg_bytes": (
                        round(float(size_stats.avg_size), 2)
                        if size_stats and size_stats.avg_size
                        else 0
                    ),
                },
                "metadata_completeness": {
                    "with_contact": with_contact,
                    "with_license": with_license,
                    "with_servers": with_servers,
                    "contact_coverage": (
                        (with_contact / total_apis * 100) if total_apis > 0 else 0
                    ),
                    "license_coverage": (
                        (with_license / total_apis * 100) if total_apis > 0 else 0
                    ),
                    "servers_coverage": (
                        (with_servers / total_apis * 100) if total_apis > 0 else 0
                    ),
                },
            }

        except Exception as e:
            self.logger.error("Failed to get API metadata statistics", error=str(e))
            raise RepositoryError(f"Failed to get API metadata statistics: {str(e)}")

    async def find_duplicates_by_hash(self) -> List[List[APIMetadata]]:
        """Find duplicate APIs by specification hash."""
        try:
            # Find specification hashes that appear more than once
            duplicate_hashes_query = (
                select(APIMetadata.specification_hash)
                .group_by(APIMetadata.specification_hash)
                .having(func.count() > 1)
            )

            duplicate_hashes_result = await self.session.execute(duplicate_hashes_query)
            duplicate_hashes = [row[0] for row in duplicate_hashes_result.fetchall()]

            if not duplicate_hashes:
                return []

            # Get all APIs with duplicate hashes
            duplicates = []
            for spec_hash in duplicate_hashes:
                stmt = select(APIMetadata).where(
                    APIMetadata.specification_hash == spec_hash
                )
                result = await self.session.execute(stmt)
                apis = result.scalars().all()
                duplicates.append(list(apis))

            return duplicates

        except Exception as e:
            self.logger.error("Failed to find duplicate APIs", error=str(e))
            raise RepositoryError(f"Failed to find duplicate APIs: {str(e)}")

    async def cleanup_old_versions(
        self, keep_versions: int = 5, dry_run: bool = True
    ) -> List[APIMetadata]:
        """Clean up old versions of APIs, keeping only the most recent versions."""
        try:
            # Get all unique titles
            titles = await self.get_all_titles()

            to_delete = []

            for title in titles:
                # Get all versions for this title, ordered by creation date (newest first)
                stmt = select(APIMetadata).where(APIMetadata.title == title)
                stmt = stmt.order_by(APIMetadata.created_at.desc())

                result = await self.session.execute(stmt)
                versions = result.scalars().all()

                # Mark older versions for deletion if we have more than keep_versions
                if len(versions) > keep_versions:
                    old_versions = versions[keep_versions:]
                    to_delete.extend(old_versions)

            if not dry_run:
                for api in to_delete:
                    await self.delete(api)

                self.logger.info(
                    "Old API versions cleaned up",
                    deleted_count=len(to_delete),
                    keep_versions=keep_versions,
                )

            return to_delete

        except Exception as e:
            self.logger.error(
                "Failed to cleanup old versions",
                keep_versions=keep_versions,
                error=str(e),
            )
            raise RepositoryError(f"Failed to cleanup old versions: {str(e)}")

    async def get_api_summary(self, api_id: int) -> Dict[str, Any]:
        """Get a comprehensive summary of an API including counts of related entities."""
        try:
            from swagger_mcp_server.storage.models import (
                Endpoint,
                Schema,
                SecurityScheme,
            )

            # Get the API metadata
            api = await self.get_by_id(api_id)
            if not api:
                return {}

            # Count related entities
            endpoints_count = await self.session.execute(
                select(func.count()).where(Endpoint.api_id == api_id)
            )
            endpoints = endpoints_count.scalar() or 0

            schemas_count = await self.session.execute(
                select(func.count()).where(Schema.api_id == api_id)
            )
            schemas = schemas_count.scalar() or 0

            security_schemes_count = await self.session.execute(
                select(func.count()).where(SecurityScheme.api_id == api_id)
            )
            security_schemes = security_schemes_count.scalar() or 0

            # Count deprecated endpoints
            deprecated_endpoints_count = await self.session.execute(
                select(func.count()).where(
                    and_(Endpoint.api_id == api_id, Endpoint.deprecated == True)
                )
            )
            deprecated_endpoints = deprecated_endpoints_count.scalar() or 0

            return {
                "api": api.to_dict(),
                "counts": {
                    "endpoints": endpoints,
                    "schemas": schemas,
                    "security_schemes": security_schemes,
                    "deprecated_endpoints": deprecated_endpoints,
                },
                "health": {
                    "deprecation_rate": (
                        (deprecated_endpoints / endpoints * 100) if endpoints > 0 else 0
                    ),
                    "has_schemas": schemas > 0,
                    "has_security": security_schemes > 0,
                },
            }

        except Exception as e:
            self.logger.error("Failed to get API summary", api_id=api_id, error=str(e))
            raise RepositoryError(f"Failed to get API summary: {str(e)}")
