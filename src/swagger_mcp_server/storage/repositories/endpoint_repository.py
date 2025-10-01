"""Repository for endpoint data access operations."""

from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from swagger_mcp_server.config.logging import get_logger
from swagger_mcp_server.storage.models import APIMetadata, Endpoint
from swagger_mcp_server.storage.repositories.base import (
    BaseRepository,
    RepositoryError,
)

logger = get_logger(__name__)


class EndpointRepository(BaseRepository[Endpoint]):
    """Repository for endpoint data access operations."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, Endpoint)

    async def search_endpoints(
        self,
        query: str,
        api_id: Optional[int] = None,
        methods: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        deprecated: Optional[bool] = None,
        category: Optional[str] = None,
        category_group: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Endpoint]:
        """Search endpoints using full-text search and filters.

        Epic 6: Enhanced with category filtering support.
        """
        try:
            if not query.strip():
                # If no query, use regular filtering
                return await self._filter_endpoints(
                    api_id=api_id,
                    methods=methods,
                    tags=tags,
                    deprecated=deprecated,
                    category=category,
                    category_group=category_group,
                    limit=limit,
                    offset=offset,
                )

            # Use FTS5 for full-text search
            fts_query = f"""
            SELECT endpoints.*
            FROM endpoints
            JOIN endpoints_fts ON endpoints.id = endpoints_fts.rowid
            WHERE endpoints_fts MATCH ?
            """

            # Add additional filters
            conditions = []
            params = [query]

            if api_id:
                conditions.append("endpoints.api_id = ?")
                params.append(api_id)

            if methods:
                method_placeholders = ",".join(["?" for _ in methods])
                conditions.append(f"endpoints.method IN ({method_placeholders})")
                params.extend(methods)

            if tags:
                # Search in tags JSON array
                tag_conditions = []
                for tag in tags:
                    tag_conditions.append("JSON_EXTRACT(endpoints.tags, '$') LIKE ?")
                    params.append(f'%"{tag}"%')
                if tag_conditions:
                    conditions.append(f"({' OR '.join(tag_conditions)})")

            if deprecated is not None:
                conditions.append("endpoints.deprecated = ?")
                params.append(deprecated)

            # Epic 6: Category filtering using JOIN with endpoint_categories table
            # Match category by finding tag in endpoints that matches category_name
            # Tags are stored as JSON strings like ["Campaign"] or ["Ad", "Edit"]
            # Categories are normalized (lowercase, underscores): "campaign", "ad", "search_promo"
            # Tags use Title-Case: "Campaign", "Ad", "Search-Promo"
            if category:
                conditions.append("""
                    EXISTS (
                        SELECT 1 FROM endpoint_categories ec
                        WHERE ec.api_id = endpoints.api_id
                          AND LOWER(ec.category_name) = LOWER(?)
                          AND (
                              endpoints.tags LIKE '%' || UPPER(SUBSTR(ec.category_name, 1, 1)) || SUBSTR(REPLACE(ec.category_name, '_', '-'), 2) || '%'
                          )
                    )
                """)
                params.append(category)

            if category_group:
                conditions.append("""
                    EXISTS (
                        SELECT 1 FROM endpoint_categories ec
                        WHERE ec.api_id = endpoints.api_id
                          AND LOWER(ec.category_group) = LOWER(?)
                          AND (
                              endpoints.tags LIKE '%' || UPPER(SUBSTR(ec.category_name, 1, 1)) || SUBSTR(REPLACE(ec.category_name, '_', '-'), 2) || '%'
                          )
                    )
                """)
                params.append(category_group)

            if conditions:
                fts_query += " AND " + " AND ".join(conditions)

            fts_query += f" ORDER BY rank LIMIT ? OFFSET ?"
            params.extend([limit, offset])

            result = await self.session.execute(text(fts_query), params)
            rows = result.fetchall()

            # Convert rows to Endpoint objects
            endpoints = []
            for row in rows:
                endpoint = Endpoint()
                for i, column in enumerate(result.keys()):
                    if hasattr(endpoint, column):
                        setattr(endpoint, column, row[i])
                endpoints.append(endpoint)

            self.logger.debug(
                "Endpoints searched with FTS",
                query=query,
                found=len(endpoints),
            )

            return endpoints

        except Exception as e:
            self.logger.warning(
                "FTS search failed, falling back to LIKE search",
                query=query,
                error=str(e),
            )
            # Fallback to LIKE search if FTS fails
            return await self._like_search_endpoints(
                query, api_id, methods, tags, deprecated, category, category_group, limit, offset
            )

    async def _like_search_endpoints(
        self,
        query: str,
        api_id: Optional[int] = None,
        methods: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        deprecated: Optional[bool] = None,
        category: Optional[str] = None,
        category_group: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Endpoint]:
        """Fallback search using LIKE operations. Epic 6: Enhanced with category filtering."""
        stmt = select(Endpoint)

        # Text search conditions
        search_terms = query.split()
        text_conditions = []

        for term in search_terms:
            term_pattern = f"%{term}%"
            term_conditions = or_(
                Endpoint.path.ilike(term_pattern),
                Endpoint.operation_id.ilike(term_pattern),
                Endpoint.summary.ilike(term_pattern),
                Endpoint.description.ilike(term_pattern),
                Endpoint.searchable_text.ilike(term_pattern),
            )
            text_conditions.append(term_conditions)

        if text_conditions:
            stmt = stmt.where(and_(*text_conditions))

        # Additional filters
        if api_id:
            stmt = stmt.where(Endpoint.api_id == api_id)

        if methods:
            stmt = stmt.where(Endpoint.method.in_(methods))

        if tags:
            # JSON array search for tags
            tag_conditions = []
            for tag in tags:
                tag_conditions.append(Endpoint.tags.like(f'%"{tag}"%'))
            if tag_conditions:
                stmt = stmt.where(or_(*tag_conditions))

        if deprecated is not None:
            stmt = stmt.where(Endpoint.deprecated == deprecated)

        # Epic 6: Category filtering using subquery with endpoint_categories table
        # Tags are stored as JSON strings like ["Campaign"] with Title-Case
        # Categories use lowercase with underscores: "campaign", "search_promo"
        if category:
            # Use raw SQL for EXISTS subquery with tag matching
            category_filter = text("""
                EXISTS (
                    SELECT 1 FROM endpoint_categories ec
                    WHERE ec.api_id = endpoints.api_id
                      AND LOWER(ec.category_name) = LOWER(:category_param)
                      AND endpoints.tags LIKE '%' || UPPER(SUBSTR(ec.category_name, 1, 1)) || SUBSTR(REPLACE(ec.category_name, '_', '-'), 2) || '%'
                )
            """)
            stmt = stmt.where(category_filter.bindparams(category_param=category))

        if category_group:
            # Use raw SQL for EXISTS subquery with tag matching
            group_filter = text("""
                EXISTS (
                    SELECT 1 FROM endpoint_categories ec
                    WHERE ec.api_id = endpoints.api_id
                      AND LOWER(ec.category_group) = LOWER(:group_param)
                      AND endpoints.tags LIKE '%' || UPPER(SUBSTR(ec.category_name, 1, 1)) || SUBSTR(REPLACE(ec.category_name, '_', '-'), 2) || '%'
                )
            """)
            stmt = stmt.where(group_filter.bindparams(group_param=category_group))

        stmt = stmt.limit(limit).offset(offset)

        result = await self.session.execute(stmt)
        endpoints = result.scalars().all()

        return list(endpoints)

    async def _filter_endpoints(
        self,
        api_id: Optional[int] = None,
        methods: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        deprecated: Optional[bool] = None,
        category: Optional[str] = None,
        category_group: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Endpoint]:
        """Filter endpoints without text search. Epic 6: Enhanced with category filtering."""
        filters = {}

        if api_id:
            filters["api_id"] = api_id

        if deprecated is not None:
            filters["deprecated"] = deprecated

        # For methods and tags, we need custom filtering
        stmt = select(Endpoint)

        for field, value in filters.items():
            if hasattr(Endpoint, field):
                column = getattr(Endpoint, field)
                stmt = stmt.where(column == value)

        if methods:
            stmt = stmt.where(Endpoint.method.in_(methods))

        if tags:
            tag_conditions = []
            for tag in tags:
                tag_conditions.append(Endpoint.tags.like(f'%"{tag}"%'))
            if tag_conditions:
                stmt = stmt.where(or_(*tag_conditions))

        # Epic 6: Category filtering using subquery with endpoint_categories table
        # Tags are stored as JSON strings like ["Campaign"] with Title-Case
        # Categories use lowercase with underscores: "campaign", "search_promo"
        if category:
            # Use raw SQL for EXISTS subquery with tag matching
            category_filter = text("""
                EXISTS (
                    SELECT 1 FROM endpoint_categories ec
                    WHERE ec.api_id = endpoints.api_id
                      AND LOWER(ec.category_name) = LOWER(:category_param)
                      AND endpoints.tags LIKE '%' || UPPER(SUBSTR(ec.category_name, 1, 1)) || SUBSTR(REPLACE(ec.category_name, '_', '-'), 2) || '%'
                )
            """)
            stmt = stmt.where(category_filter.bindparams(category_param=category))

        if category_group:
            # Use raw SQL for EXISTS subquery with tag matching
            group_filter = text("""
                EXISTS (
                    SELECT 1 FROM endpoint_categories ec
                    WHERE ec.api_id = endpoints.api_id
                      AND LOWER(ec.category_group) = LOWER(:group_param)
                      AND endpoints.tags LIKE '%' || UPPER(SUBSTR(ec.category_name, 1, 1)) || SUBSTR(REPLACE(ec.category_name, '_', '-'), 2) || '%'
                )
            """)
            stmt = stmt.where(group_filter.bindparams(group_param=category_group))

        stmt = stmt.limit(limit).offset(offset)

        result = await self.session.execute(stmt)
        endpoints = result.scalars().all()

        return list(endpoints)

    async def get_by_path_method(
        self, path: str, method: str, api_id: Optional[int] = None
    ) -> Optional[Endpoint]:
        """Get endpoint by path and method."""
        try:
            stmt = select(Endpoint).where(
                and_(Endpoint.path == path, Endpoint.method == method.lower())
            )

            if api_id:
                stmt = stmt.where(Endpoint.api_id == api_id)

            result = await self.session.execute(stmt)
            endpoint = result.scalar_one_or_none()

            return endpoint

        except Exception as e:
            self.logger.error(
                "Failed to get endpoint by path and method",
                path=path,
                method=method,
                api_id=api_id,
                error=str(e),
            )
            raise RepositoryError(f"Failed to get endpoint: {str(e)}")

    async def get_by_operation_id(
        self, operation_id: str, api_id: Optional[int] = None
    ) -> Optional[Endpoint]:
        """Get endpoint by operation ID."""
        try:
            stmt = select(Endpoint).where(Endpoint.operation_id == operation_id)

            if api_id:
                stmt = stmt.where(Endpoint.api_id == api_id)

            result = await self.session.execute(stmt)
            endpoint = result.scalar_one_or_none()

            return endpoint

        except Exception as e:
            self.logger.error(
                "Failed to get endpoint by operation ID",
                operation_id=operation_id,
                api_id=api_id,
                error=str(e),
            )
            raise RepositoryError(f"Failed to get endpoint by operation ID: {str(e)}")

    async def get_by_tags(
        self,
        tags: List[str],
        api_id: Optional[int] = None,
        match_all: bool = False,
    ) -> List[Endpoint]:
        """Get endpoints by tags."""
        try:
            stmt = select(Endpoint)

            if api_id:
                stmt = stmt.where(Endpoint.api_id == api_id)

            # Build tag conditions
            tag_conditions = []
            for tag in tags:
                tag_conditions.append(Endpoint.tags.like(f'%"{tag}"%'))

            if tag_conditions:
                if match_all:
                    stmt = stmt.where(and_(*tag_conditions))
                else:
                    stmt = stmt.where(or_(*tag_conditions))

            result = await self.session.execute(stmt)
            endpoints = result.scalars().all()

            return list(endpoints)

        except Exception as e:
            self.logger.error(
                "Failed to get endpoints by tags",
                tags=tags,
                api_id=api_id,
                error=str(e),
            )
            raise RepositoryError(f"Failed to get endpoints by tags: {str(e)}")

    async def get_by_api_id(
        self, api_id: int, include_deprecated: bool = True
    ) -> List[Endpoint]:
        """Get all endpoints for a specific API."""
        try:
            stmt = select(Endpoint).where(Endpoint.api_id == api_id)

            if not include_deprecated:
                stmt = stmt.where(Endpoint.deprecated == False)

            stmt = stmt.order_by(Endpoint.path, Endpoint.method)

            result = await self.session.execute(stmt)
            endpoints = result.scalars().all()

            return list(endpoints)

        except Exception as e:
            self.logger.error(
                "Failed to get endpoints by API ID",
                api_id=api_id,
                error=str(e),
            )
            raise RepositoryError(f"Failed to get endpoints by API ID: {str(e)}")

    async def get_methods_for_path(
        self, path: str, api_id: Optional[int] = None
    ) -> List[str]:
        """Get all HTTP methods available for a path."""
        try:
            stmt = select(Endpoint.method).where(Endpoint.path == path)

            if api_id:
                stmt = stmt.where(Endpoint.api_id == api_id)

            result = await self.session.execute(stmt)
            methods = result.scalars().all()

            return list(methods)

        except Exception as e:
            self.logger.error(
                "Failed to get methods for path",
                path=path,
                api_id=api_id,
                error=str(e),
            )
            raise RepositoryError(f"Failed to get methods for path: {str(e)}")

    async def get_all_tags(self, api_id: Optional[int] = None) -> List[str]:
        """Get all unique tags from endpoints."""
        try:
            # Raw SQL to extract tags from JSON arrays
            query = """
            SELECT DISTINCT json_each.value as tag
            FROM endpoints, json_each(endpoints.tags)
            WHERE json_each.value IS NOT NULL
            """

            params = []
            if api_id:
                query += " AND endpoints.api_id = ?"
                params.append(api_id)

            query += " ORDER BY tag"

            result = await self.session.execute(text(query), params)
            rows = result.fetchall()

            tags = [row[0] for row in rows if row[0]]
            return tags

        except Exception as e:
            self.logger.error("Failed to get all tags", api_id=api_id, error=str(e))
            raise RepositoryError(f"Failed to get all tags: {str(e)}")

    async def get_statistics(self, api_id: Optional[int] = None) -> Dict[str, Any]:
        """Get endpoint statistics."""
        try:
            base_query = select(Endpoint)
            if api_id:
                base_query = base_query.where(Endpoint.api_id == api_id)

            # Total count
            total_query = select(func.count()).select_from(base_query.subquery())
            total_result = await self.session.execute(total_query)
            total_endpoints = total_result.scalar() or 0

            # Method distribution
            method_query = select(
                Endpoint.method, func.count(Endpoint.method).label("count")
            )
            if api_id:
                method_query = method_query.where(Endpoint.api_id == api_id)

            method_query = method_query.group_by(Endpoint.method)
            method_result = await self.session.execute(method_query)
            methods = {row.method: row.count for row in method_result.fetchall()}

            # Deprecated count
            deprecated_query = select(func.count()).where(Endpoint.deprecated == True)
            if api_id:
                deprecated_query = deprecated_query.where(Endpoint.api_id == api_id)

            deprecated_result = await self.session.execute(deprecated_query)
            deprecated_count = deprecated_result.scalar() or 0

            # Endpoints with operation IDs
            operation_id_query = select(func.count()).where(
                and_(
                    Endpoint.operation_id.isnot(None),
                    Endpoint.operation_id != "",
                )
            )
            if api_id:
                operation_id_query = operation_id_query.where(Endpoint.api_id == api_id)

            operation_id_result = await self.session.execute(operation_id_query)
            with_operation_id = operation_id_result.scalar() or 0

            return {
                "total_endpoints": total_endpoints,
                "methods": methods,
                "deprecated_count": deprecated_count,
                "with_operation_id": with_operation_id,
                "documentation_coverage": (
                    (with_operation_id / total_endpoints * 100)
                    if total_endpoints > 0
                    else 0
                ),
            }

        except Exception as e:
            self.logger.error(
                "Failed to get endpoint statistics",
                api_id=api_id,
                error=str(e),
            )
            raise RepositoryError(f"Failed to get endpoint statistics: {str(e)}")

    async def find_similar_endpoints(
        self,
        path: str,
        method: str,
        api_id: Optional[int] = None,
        limit: int = 5,
    ) -> List[Endpoint]:
        """Find endpoints similar to the given path and method."""
        try:
            # Simple similarity based on path segments
            path_segments = [seg for seg in path.split("/") if seg]
            if not path_segments:
                return []

            # Build LIKE conditions for path segments
            like_conditions = []
            for segment in path_segments:
                if not segment.startswith("{"):  # Skip path parameters
                    like_conditions.append(Endpoint.path.like(f"%/{segment}/%"))

            if not like_conditions:
                return []

            stmt = select(Endpoint).where(or_(*like_conditions))

            # Prefer same method
            if method:
                stmt = stmt.order_by(
                    func.case((Endpoint.method == method.lower(), 0), else_=1)
                )

            if api_id:
                stmt = stmt.where(Endpoint.api_id == api_id)

            # Exclude exact match
            stmt = stmt.where(
                not_(
                    and_(
                        Endpoint.path == path,
                        Endpoint.method == method.lower(),
                    )
                )
            )

            stmt = stmt.limit(limit)

            result = await self.session.execute(stmt)
            endpoints = result.scalars().all()

            return list(endpoints)

        except Exception as e:
            self.logger.error(
                "Failed to find similar endpoints",
                path=path,
                method=method,
                error=str(e),
            )
            raise RepositoryError(f"Failed to find similar endpoints: {str(e)}")

    async def get_categories(
        self,
        api_id: Optional[int] = None,
        category_group: Optional[str] = None,
        include_empty: bool = False,
        sort_by: str = "name",
    ) -> List[Dict[str, Any]]:
        """Get endpoint categories with optional filtering and sorting.

        Epic 6: Hierarchical Endpoint Catalog System

        Args:
            api_id: Optional API ID filter
            category_group: Optional parent group filter
            include_empty: Include categories with 0 endpoints
            sort_by: Sort order ["name", "endpointCount", "group"]

        Returns:
            List of category dictionaries

        Raises:
            RepositoryError: If query fails
        """
        try:
            # Build SQL query
            query = """
            SELECT
                category_name,
                display_name,
                description,
                category_group,
                endpoint_count,
                http_methods,
                api_id
            FROM endpoint_categories
            WHERE (? IS NULL OR api_id = ?)
              AND (? IS NULL OR category_group = ?)
              AND (? = 1 OR endpoint_count > 0)
            """

            # Add sorting
            if sort_by == "name":
                query += " ORDER BY category_name ASC"
            elif sort_by == "endpointCount":
                query += " ORDER BY endpoint_count DESC, category_name ASC"
            elif sort_by == "group":
                query += " ORDER BY category_group ASC, category_name ASC"
            else:
                query += " ORDER BY category_name ASC"

            # Execute query
            result = await self.session.execute(
                text(query),
                [
                    api_id,
                    api_id,
                    category_group,
                    category_group,
                    1 if include_empty else 0,
                ],
            )

            rows = result.fetchall()

            # Convert to dictionaries
            categories = []
            for row in rows:
                import json

                categories.append(
                    {
                        "name": row[0],
                        "displayName": row[1],
                        "description": row[2],
                        "group": row[3],
                        "endpointCount": row[4],
                        "httpMethods": json.loads(row[5]) if row[5] else [],
                        "api_id": row[6],
                    }
                )

            self.logger.debug(
                "Categories retrieved",
                count=len(categories),
                api_id=api_id,
                category_group=category_group,
            )

            return categories

        except Exception as e:
            self.logger.error(
                "Failed to get categories",
                api_id=api_id,
                category_group=category_group,
                error=str(e),
            )
            raise RepositoryError(f"Failed to get categories: {str(e)}")

    async def get_category_groups(
        self, api_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get category groups with aggregated statistics.

        Epic 6: Hierarchical Endpoint Catalog System

        Args:
            api_id: Optional API ID filter

        Returns:
            List of group dictionaries with categoryCount, totalEndpoints, categories

        Raises:
            RepositoryError: If query fails
        """
        try:
            query = """
            SELECT
                category_group,
                COUNT(DISTINCT category_name) as category_count,
                SUM(endpoint_count) as total_endpoints,
                GROUP_CONCAT(category_name, ',') as categories
            FROM endpoint_categories
            WHERE category_group IS NOT NULL
              AND (? IS NULL OR api_id = ?)
            GROUP BY category_group
            ORDER BY category_group ASC
            """

            result = await self.session.execute(text(query), [api_id, api_id])
            rows = result.fetchall()

            groups = []
            for row in rows:
                groups.append(
                    {
                        "name": row[0],
                        "categoryCount": row[1],
                        "totalEndpoints": row[2],
                        "categories": row[3].split(",") if row[3] else [],
                    }
                )

            self.logger.debug("Category groups retrieved", count=len(groups))

            return groups

        except Exception as e:
            self.logger.error("Failed to get category groups", error=str(e))
            raise RepositoryError(f"Failed to get category groups: {str(e)}")

    async def get_endpoints_by_category(
        self,
        category: str,
        api_id: Optional[int] = None,
        include_deprecated: bool = True,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Endpoint]:
        """Get endpoints filtered by category with pagination.

        Epic 6: Hierarchical Endpoint Catalog System - AC 5

        Args:
            category: Category name to filter by (case-insensitive)
            api_id: Optional API ID filter
            include_deprecated: Include deprecated endpoints
            limit: Maximum number of results
            offset: Pagination offset

        Returns:
            List of Endpoint objects matching the category

        Raises:
            RepositoryError: If query fails
        """
        try:
            stmt = select(Endpoint).where(
                func.lower(Endpoint.category) == func.lower(category)
            )

            if api_id:
                stmt = stmt.where(Endpoint.api_id == api_id)

            if not include_deprecated:
                stmt = stmt.where(Endpoint.deprecated == False)

            stmt = stmt.order_by(Endpoint.path, Endpoint.method)
            stmt = stmt.limit(limit).offset(offset)

            result = await self.session.execute(stmt)
            endpoints = result.scalars().all()

            self.logger.debug(
                "Endpoints retrieved by category",
                category=category,
                count=len(endpoints),
                api_id=api_id,
            )

            return list(endpoints)

        except Exception as e:
            self.logger.error(
                "Failed to get endpoints by category",
                category=category,
                api_id=api_id,
                error=str(e),
            )
            raise RepositoryError(f"Failed to get endpoints by category: {str(e)}")
