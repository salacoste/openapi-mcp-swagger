"""Repository for schema data access operations."""

from typing import Any, Dict, List, Optional

from sqlalchemy import and_, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from swagger_mcp_server.config.logging import get_logger
from swagger_mcp_server.storage.models import APIMetadata, Schema
from swagger_mcp_server.storage.repositories.base import (
    BaseRepository,
    RepositoryError,
)

logger = get_logger(__name__)


class SchemaRepository(BaseRepository[Schema]):
    """Repository for schema data access operations."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, Schema)

    async def search_schemas(
        self,
        query: str,
        api_id: Optional[int] = None,
        schema_type: Optional[str] = None,
        deprecated: Optional[bool] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Schema]:
        """Search schemas using full-text search and filters."""
        try:
            if not query.strip():
                # If no query, use regular filtering
                return await self._filter_schemas(
                    api_id=api_id,
                    schema_type=schema_type,
                    deprecated=deprecated,
                    limit=limit,
                    offset=offset,
                )

            # Use FTS5 for full-text search
            fts_query = f"""
            SELECT schemas.*
            FROM schemas
            JOIN schemas_fts ON schemas.id = schemas_fts.rowid
            WHERE schemas_fts MATCH ?
            """

            # Add additional filters
            conditions = []
            params = [query]

            if api_id:
                conditions.append("schemas.api_id = ?")
                params.append(api_id)

            if schema_type:
                conditions.append("schemas.type = ?")
                params.append(schema_type)

            if deprecated is not None:
                conditions.append("schemas.deprecated = ?")
                params.append(deprecated)

            if conditions:
                fts_query += " AND " + " AND ".join(conditions)

            fts_query += f" ORDER BY rank LIMIT ? OFFSET ?"
            params.extend([limit, offset])

            result = await self.session.execute(text(fts_query), params)
            rows = result.fetchall()

            # Convert rows to Schema objects
            schemas = []
            for row in rows:
                schema = Schema()
                for i, column in enumerate(result.keys()):
                    if hasattr(schema, column):
                        setattr(schema, column, row[i])
                schemas.append(schema)

            self.logger.debug(
                "Schemas searched with FTS", query=query, found=len(schemas)
            )

            return schemas

        except Exception as e:
            self.logger.warning(
                "FTS search failed, falling back to LIKE search",
                query=query,
                error=str(e),
            )
            # Fallback to LIKE search if FTS fails
            return await self._like_search_schemas(
                query, api_id, schema_type, deprecated, limit, offset
            )

    async def _like_search_schemas(
        self,
        query: str,
        api_id: Optional[int] = None,
        schema_type: Optional[str] = None,
        deprecated: Optional[bool] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Schema]:
        """Fallback search using LIKE operations."""
        stmt = select(Schema)

        # Text search conditions
        search_terms = query.split()
        text_conditions = []

        for term in search_terms:
            term_pattern = f"%{term}%"
            term_conditions = or_(
                Schema.name.ilike(term_pattern),
                Schema.title.ilike(term_pattern),
                Schema.description.ilike(term_pattern),
                Schema.searchable_text.ilike(term_pattern),
            )
            text_conditions.append(term_conditions)

        if text_conditions:
            stmt = stmt.where(and_(*text_conditions))

        # Additional filters
        if api_id:
            stmt = stmt.where(Schema.api_id == api_id)

        if schema_type:
            stmt = stmt.where(Schema.type == schema_type)

        if deprecated is not None:
            stmt = stmt.where(Schema.deprecated == deprecated)

        stmt = stmt.limit(limit).offset(offset)

        result = await self.session.execute(stmt)
        schemas = result.scalars().all()

        return list(schemas)

    async def _filter_schemas(
        self,
        api_id: Optional[int] = None,
        schema_type: Optional[str] = None,
        deprecated: Optional[bool] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Schema]:
        """Filter schemas without text search."""
        filters = {}

        if api_id:
            filters["api_id"] = api_id

        if schema_type:
            filters["type"] = schema_type

        if deprecated is not None:
            filters["deprecated"] = deprecated

        return await self.list(
            limit=limit, offset=offset, filters=filters, order_by="name"
        )

    async def get_by_name(
        self, name: str, api_id: Optional[int] = None
    ) -> Optional[Schema]:
        """Get schema by name."""
        try:
            stmt = select(Schema).where(Schema.name == name)

            if api_id:
                stmt = stmt.where(Schema.api_id == api_id)

            result = await self.session.execute(stmt)
            schema = result.scalar_one_or_none()

            return schema

        except Exception as e:
            self.logger.error(
                "Failed to get schema by name",
                name=name,
                api_id=api_id,
                error=str(e),
            )
            raise RepositoryError(f"Failed to get schema by name: {str(e)}")

    async def get_by_api_id(
        self, api_id: int, include_deprecated: bool = True
    ) -> List[Schema]:
        """Get all schemas for a specific API."""
        try:
            stmt = select(Schema).where(Schema.api_id == api_id)

            if not include_deprecated:
                stmt = stmt.where(Schema.deprecated == False)

            stmt = stmt.order_by(Schema.name)

            result = await self.session.execute(stmt)
            schemas = result.scalars().all()

            return list(schemas)

        except Exception as e:
            self.logger.error(
                "Failed to get schemas by API ID", api_id=api_id, error=str(e)
            )
            raise RepositoryError(f"Failed to get schemas by API ID: {str(e)}")

    async def get_by_type(
        self, schema_type: str, api_id: Optional[int] = None
    ) -> List[Schema]:
        """Get schemas by type."""
        try:
            stmt = select(Schema).where(Schema.type == schema_type)

            if api_id:
                stmt = stmt.where(Schema.api_id == api_id)

            stmt = stmt.order_by(Schema.name)

            result = await self.session.execute(stmt)
            schemas = result.scalars().all()

            return list(schemas)

        except Exception as e:
            self.logger.error(
                "Failed to get schemas by type",
                schema_type=schema_type,
                api_id=api_id,
                error=str(e),
            )
            raise RepositoryError(f"Failed to get schemas by type: {str(e)}")

    async def get_dependent_schemas(
        self, schema_name: str, api_id: Optional[int] = None
    ) -> List[Schema]:
        """Get schemas that depend on the given schema."""
        try:
            # Find schemas that reference this schema in their dependencies
            stmt = select(Schema).where(
                Schema.schema_dependencies.like(f'%"{schema_name}"%')
            )

            if api_id:
                stmt = stmt.where(Schema.api_id == api_id)

            result = await self.session.execute(stmt)
            schemas = result.scalars().all()

            return list(schemas)

        except Exception as e:
            self.logger.error(
                "Failed to get dependent schemas",
                schema_name=schema_name,
                api_id=api_id,
                error=str(e),
            )
            raise RepositoryError(f"Failed to get dependent schemas: {str(e)}")

    async def get_schema_dependencies(
        self, schema_name: str, api_id: Optional[int] = None
    ) -> List[Schema]:
        """Get schemas that the given schema depends on."""
        try:
            # First get the schema to read its dependencies
            schema = await self.get_by_name(schema_name, api_id)
            if not schema or not schema.schema_dependencies:
                return []

            # Get all schemas that are in the dependencies list
            stmt = select(Schema).where(Schema.name.in_(schema.schema_dependencies))

            if api_id:
                stmt = stmt.where(Schema.api_id == api_id)

            result = await self.session.execute(stmt)
            dependencies = result.scalars().all()

            return list(dependencies)

        except Exception as e:
            self.logger.error(
                "Failed to get schema dependencies",
                schema_name=schema_name,
                api_id=api_id,
                error=str(e),
            )
            raise RepositoryError(f"Failed to get schema dependencies: {str(e)}")

    async def get_most_referenced(
        self, api_id: Optional[int] = None, limit: int = 10
    ) -> List[Schema]:
        """Get schemas ordered by reference count (most referenced first)."""
        try:
            stmt = select(Schema).where(Schema.reference_count > 0)

            if api_id:
                stmt = stmt.where(Schema.api_id == api_id)

            stmt = stmt.order_by(Schema.reference_count.desc()).limit(limit)

            result = await self.session.execute(stmt)
            schemas = result.scalars().all()

            return list(schemas)

        except Exception as e:
            self.logger.error(
                "Failed to get most referenced schemas",
                api_id=api_id,
                error=str(e),
            )
            raise RepositoryError(f"Failed to get most referenced schemas: {str(e)}")

    async def get_unused_schemas(self, api_id: Optional[int] = None) -> List[Schema]:
        """Get schemas that are not referenced by any endpoint or other schema."""
        try:
            stmt = select(Schema).where(Schema.reference_count == 0)

            if api_id:
                stmt = stmt.where(Schema.api_id == api_id)

            stmt = stmt.order_by(Schema.name)

            result = await self.session.execute(stmt)
            schemas = result.scalars().all()

            return list(schemas)

        except Exception as e:
            self.logger.error(
                "Failed to get unused schemas", api_id=api_id, error=str(e)
            )
            raise RepositoryError(f"Failed to get unused schemas: {str(e)}")

    async def get_all_types(self, api_id: Optional[int] = None) -> List[str]:
        """Get all unique schema types."""
        try:
            stmt = select(Schema.type).distinct()

            if api_id:
                stmt = stmt.where(Schema.api_id == api_id)

            stmt = stmt.where(Schema.type.isnot(None))
            stmt = stmt.order_by(Schema.type)

            result = await self.session.execute(stmt)
            types = result.scalars().all()

            return [t for t in types if t]

        except Exception as e:
            self.logger.error(
                "Failed to get all schema types", api_id=api_id, error=str(e)
            )
            raise RepositoryError(f"Failed to get all schema types: {str(e)}")

    async def get_property_names(
        self, schema_name: str, api_id: Optional[int] = None
    ) -> List[str]:
        """Get all property names for a schema."""
        try:
            schema = await self.get_by_name(schema_name, api_id)
            if not schema or not schema.property_names:
                return []

            return schema.property_names

        except Exception as e:
            self.logger.error(
                "Failed to get property names",
                schema_name=schema_name,
                api_id=api_id,
                error=str(e),
            )
            raise RepositoryError(f"Failed to get property names: {str(e)}")

    async def find_schemas_with_property(
        self, property_name: str, api_id: Optional[int] = None
    ) -> List[Schema]:
        """Find schemas that contain a specific property."""
        try:
            # Search in property_names JSON array
            stmt = select(Schema).where(
                Schema.property_names.like(f'%"{property_name}"%')
            )

            if api_id:
                stmt = stmt.where(Schema.api_id == api_id)

            result = await self.session.execute(stmt)
            schemas = result.scalars().all()

            return list(schemas)

        except Exception as e:
            self.logger.error(
                "Failed to find schemas with property",
                property_name=property_name,
                api_id=api_id,
                error=str(e),
            )
            raise RepositoryError(f"Failed to find schemas with property: {str(e)}")

    async def get_statistics(self, api_id: Optional[int] = None) -> Dict[str, Any]:
        """Get schema statistics."""
        try:
            base_query = select(Schema)
            if api_id:
                base_query = base_query.where(Schema.api_id == api_id)

            # Total count
            total_query = select(func.count()).select_from(base_query.subquery())
            total_result = await self.session.execute(total_query)
            total_schemas = total_result.scalar() or 0

            # Type distribution
            type_query = select(Schema.type, func.count(Schema.type).label("count"))
            if api_id:
                type_query = type_query.where(Schema.api_id == api_id)

            type_query = type_query.where(Schema.type.isnot(None))
            type_query = type_query.group_by(Schema.type)
            type_result = await self.session.execute(type_query)
            types = {row.type: row.count for row in type_result.fetchall()}

            # Deprecated count
            deprecated_query = select(func.count()).where(Schema.deprecated == True)
            if api_id:
                deprecated_query = deprecated_query.where(Schema.api_id == api_id)

            deprecated_result = await self.session.execute(deprecated_query)
            deprecated_count = deprecated_result.scalar() or 0

            # Referenced count
            referenced_query = select(func.count()).where(Schema.reference_count > 0)
            if api_id:
                referenced_query = referenced_query.where(Schema.api_id == api_id)

            referenced_result = await self.session.execute(referenced_query)
            referenced_count = referenced_result.scalar() or 0

            # Average properties per schema
            avg_props_query = select(
                func.avg(func.json_array_length(Schema.property_names))
            )
            if api_id:
                avg_props_query = avg_props_query.where(Schema.api_id == api_id)

            avg_props_result = await self.session.execute(avg_props_query)
            avg_properties = avg_props_result.scalar() or 0

            return {
                "total_schemas": total_schemas,
                "types": types,
                "deprecated_count": deprecated_count,
                "referenced_count": referenced_count,
                "unused_count": total_schemas - referenced_count,
                "average_properties": round(float(avg_properties), 2),
                "usage_rate": (
                    (referenced_count / total_schemas * 100) if total_schemas > 0 else 0
                ),
            }

        except Exception as e:
            self.logger.error(
                "Failed to get schema statistics", api_id=api_id, error=str(e)
            )
            raise RepositoryError(f"Failed to get schema statistics: {str(e)}")

    async def update_reference_counts(self, api_id: Optional[int] = None) -> None:
        """Update reference counts for all schemas."""
        try:
            # This would typically be called after importing/updating API data
            # For now, implement a simple version that counts dependencies
            schemas = await self.get_by_api_id(api_id) if api_id else await self.list()

            for schema in schemas:
                # Count how many other schemas reference this one
                dependents = await self.get_dependent_schemas(schema.name, api_id)
                schema.reference_count = len(dependents)
                await self.update(schema)

            self.logger.info(
                "Schema reference counts updated",
                api_id=api_id,
                count=len(schemas),
            )

        except Exception as e:
            self.logger.error(
                "Failed to update reference counts",
                api_id=api_id,
                error=str(e),
            )
            raise RepositoryError(f"Failed to update reference counts: {str(e)}")
