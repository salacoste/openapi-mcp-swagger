"""Base repository class with common CRUD operations."""

from abc import ABC, abstractmethod
from typing import Any, Dict, Generic, List, Optional, Type, TypeVar, Union

from sqlalchemy import delete, func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from swagger_mcp_server.config.logging import get_logger
from swagger_mcp_server.storage.models import Base

logger = get_logger(__name__)

T = TypeVar("T", bound=Base)


class RepositoryError(Exception):
    """Base exception for repository operations."""

    pass


class NotFoundError(RepositoryError):
    """Raised when a requested entity is not found."""

    pass


class ConflictError(RepositoryError):
    """Raised when an operation conflicts with existing data."""

    pass


class BaseRepository(ABC, Generic[T]):
    """Base repository class providing common CRUD operations."""

    def __init__(self, session: AsyncSession, model_class: Type[T]):
        self.session = session
        self.model_class = model_class
        self.logger = get_logger(f"{__name__}.{model_class.__name__}")

    async def create(self, entity: T) -> T:
        """Create a new entity."""
        try:
            self.session.add(entity)
            await self.session.flush()
            await self.session.refresh(entity)

            self.logger.debug(
                "Entity created",
                entity_type=self.model_class.__name__,
                entity_id=getattr(entity, "id", None),
            )

            return entity

        except Exception as e:
            await self.session.rollback()
            self.logger.error(
                "Failed to create entity",
                entity_type=self.model_class.__name__,
                error=str(e),
            )
            raise RepositoryError(
                f"Failed to create {self.model_class.__name__}: {str(e)}"
            )

    async def create_many(self, entities: List[T]) -> List[T]:
        """Create multiple entities in batch."""
        try:
            self.session.add_all(entities)
            await self.session.flush()

            # Refresh all entities to get their IDs
            for entity in entities:
                await self.session.refresh(entity)

            self.logger.debug(
                "Entities created in batch",
                entity_type=self.model_class.__name__,
                count=len(entities),
            )

            return entities

        except Exception as e:
            await self.session.rollback()
            self.logger.error(
                "Failed to create entities in batch",
                entity_type=self.model_class.__name__,
                count=len(entities),
                error=str(e),
            )
            raise RepositoryError(
                f"Failed to create {self.model_class.__name__} entities: {str(e)}"
            )

    async def get_by_id(self, entity_id: int) -> Optional[T]:
        """Get entity by ID."""
        try:
            stmt = select(self.model_class).where(
                self.model_class.id == entity_id
            )
            result = await self.session.execute(stmt)
            entity = result.scalar_one_or_none()

            if entity:
                self.logger.debug(
                    "Entity retrieved by ID",
                    entity_type=self.model_class.__name__,
                    entity_id=entity_id,
                )

            return entity

        except Exception as e:
            self.logger.error(
                "Failed to get entity by ID",
                entity_type=self.model_class.__name__,
                entity_id=entity_id,
                error=str(e),
            )
            raise RepositoryError(
                f"Failed to get {self.model_class.__name__} by ID: {str(e)}"
            )

    async def get_by_id_or_raise(self, entity_id: int) -> T:
        """Get entity by ID or raise NotFoundError."""
        entity = await self.get_by_id(entity_id)
        if entity is None:
            raise NotFoundError(
                f"{self.model_class.__name__} with ID {entity_id} not found"
            )
        return entity

    async def update(self, entity: T) -> T:
        """Update an existing entity."""
        try:
            await self.session.merge(entity)
            await self.session.flush()
            await self.session.refresh(entity)

            self.logger.debug(
                "Entity updated",
                entity_type=self.model_class.__name__,
                entity_id=getattr(entity, "id", None),
            )

            return entity

        except Exception as e:
            await self.session.rollback()
            self.logger.error(
                "Failed to update entity",
                entity_type=self.model_class.__name__,
                entity_id=getattr(entity, "id", None),
                error=str(e),
            )
            raise RepositoryError(
                f"Failed to update {self.model_class.__name__}: {str(e)}"
            )

    async def update_by_id(
        self, entity_id: int, updates: Dict[str, Any]
    ) -> Optional[T]:
        """Update entity by ID with given field updates."""
        try:
            # First check if entity exists
            entity = await self.get_by_id(entity_id)
            if not entity:
                return None

            # Update fields
            for field, value in updates.items():
                if hasattr(entity, field):
                    setattr(entity, field, value)

            await self.session.flush()
            await self.session.refresh(entity)

            self.logger.debug(
                "Entity updated by ID",
                entity_type=self.model_class.__name__,
                entity_id=entity_id,
                updated_fields=list(updates.keys()),
            )

            return entity

        except Exception as e:
            await self.session.rollback()
            self.logger.error(
                "Failed to update entity by ID",
                entity_type=self.model_class.__name__,
                entity_id=entity_id,
                error=str(e),
            )
            raise RepositoryError(
                f"Failed to update {self.model_class.__name__} by ID: {str(e)}"
            )

    async def delete(self, entity: T) -> bool:
        """Delete an entity."""
        try:
            await self.session.delete(entity)
            await self.session.flush()

            self.logger.debug(
                "Entity deleted",
                entity_type=self.model_class.__name__,
                entity_id=getattr(entity, "id", None),
            )

            return True

        except Exception as e:
            await self.session.rollback()
            self.logger.error(
                "Failed to delete entity",
                entity_type=self.model_class.__name__,
                entity_id=getattr(entity, "id", None),
                error=str(e),
            )
            raise RepositoryError(
                f"Failed to delete {self.model_class.__name__}: {str(e)}"
            )

    async def delete_by_id(self, entity_id: int) -> bool:
        """Delete entity by ID."""
        try:
            stmt = delete(self.model_class).where(
                self.model_class.id == entity_id
            )
            result = await self.session.execute(stmt)

            deleted = result.rowcount > 0
            if deleted:
                await self.session.flush()
                self.logger.debug(
                    "Entity deleted by ID",
                    entity_type=self.model_class.__name__,
                    entity_id=entity_id,
                )

            return deleted

        except Exception as e:
            await self.session.rollback()
            self.logger.error(
                "Failed to delete entity by ID",
                entity_type=self.model_class.__name__,
                entity_id=entity_id,
                error=str(e),
            )
            raise RepositoryError(
                f"Failed to delete {self.model_class.__name__} by ID: {str(e)}"
            )

    async def list(
        self,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        order_by: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[T]:
        """List entities with optional pagination, ordering, and filtering."""
        try:
            stmt = select(self.model_class)

            # Apply filters
            if filters:
                for field, value in filters.items():
                    if hasattr(self.model_class, field):
                        column = getattr(self.model_class, field)
                        if isinstance(value, list):
                            stmt = stmt.where(column.in_(value))
                        else:
                            stmt = stmt.where(column == value)

            # Apply ordering
            if order_by:
                if hasattr(self.model_class, order_by):
                    column = getattr(self.model_class, order_by)
                    stmt = stmt.order_by(column)

            # Apply pagination
            if offset:
                stmt = stmt.offset(offset)
            if limit:
                stmt = stmt.limit(limit)

            result = await self.session.execute(stmt)
            entities = result.scalars().all()

            self.logger.debug(
                "Entities listed",
                entity_type=self.model_class.__name__,
                count=len(entities),
                limit=limit,
                offset=offset,
            )

            return list(entities)

        except Exception as e:
            self.logger.error(
                "Failed to list entities",
                entity_type=self.model_class.__name__,
                limit=limit,
                offset=offset,
                error=str(e),
            )
            raise RepositoryError(
                f"Failed to list {self.model_class.__name__} entities: {str(e)}"
            )

    async def count(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """Count entities with optional filtering."""
        try:
            stmt = select(func.count()).select_from(self.model_class)

            # Apply filters
            if filters:
                for field, value in filters.items():
                    if hasattr(self.model_class, field):
                        column = getattr(self.model_class, field)
                        if isinstance(value, list):
                            stmt = stmt.where(column.in_(value))
                        else:
                            stmt = stmt.where(column == value)

            result = await self.session.execute(stmt)
            count = result.scalar()

            self.logger.debug(
                "Entities counted",
                entity_type=self.model_class.__name__,
                count=count,
            )

            return count or 0

        except Exception as e:
            self.logger.error(
                "Failed to count entities",
                entity_type=self.model_class.__name__,
                error=str(e),
            )
            raise RepositoryError(
                f"Failed to count {self.model_class.__name__} entities: {str(e)}"
            )

    async def exists(self, filters: Dict[str, Any]) -> bool:
        """Check if entities exist with given filters."""
        try:
            stmt = select(func.count()).select_from(self.model_class)

            for field, value in filters.items():
                if hasattr(self.model_class, field):
                    column = getattr(self.model_class, field)
                    if isinstance(value, list):
                        stmt = stmt.where(column.in_(value))
                    else:
                        stmt = stmt.where(column == value)

            result = await self.session.execute(stmt)
            count = result.scalar()

            return (count or 0) > 0

        except Exception as e:
            self.logger.error(
                "Failed to check entity existence",
                entity_type=self.model_class.__name__,
                filters=filters,
                error=str(e),
            )
            raise RepositoryError(
                f"Failed to check {self.model_class.__name__} existence: {str(e)}"
            )

    async def execute_raw_query(
        self, query: str, params: Optional[Dict[str, Any]] = None
    ) -> Any:
        """Execute raw SQL query."""
        try:
            stmt = text(query)
            if params:
                result = await self.session.execute(stmt, params)
            else:
                result = await self.session.execute(stmt)

            return result

        except Exception as e:
            self.logger.error(
                "Failed to execute raw query",
                query=query[:100],  # Log first 100 chars
                error=str(e),
            )
            raise RepositoryError(f"Failed to execute raw query: {str(e)}")

    # Batch operations for better performance
    async def bulk_insert_dicts(self, data: List[Dict[str, Any]]) -> None:
        """Bulk insert dictionaries as entities."""
        try:
            entities = [self.model_class(**item) for item in data]
            self.session.add_all(entities)
            await self.session.flush()

            self.logger.debug(
                "Bulk insert completed",
                entity_type=self.model_class.__name__,
                count=len(data),
            )

        except Exception as e:
            await self.session.rollback()
            self.logger.error(
                "Failed to bulk insert",
                entity_type=self.model_class.__name__,
                count=len(data),
                error=str(e),
            )
            raise RepositoryError(
                f"Failed to bulk insert {self.model_class.__name__}: {str(e)}"
            )

    async def bulk_update_dicts(
        self, updates: List[Dict[str, Any]], match_field: str = "id"
    ) -> int:
        """Bulk update entities using dictionaries."""
        try:
            update_count = 0

            for update_data in updates:
                if match_field not in update_data:
                    continue

                match_value = update_data.pop(match_field)
                stmt = (
                    update(self.model_class)
                    .where(
                        getattr(self.model_class, match_field) == match_value
                    )
                    .values(**update_data)
                )

                result = await self.session.execute(stmt)
                update_count += result.rowcount

            await self.session.flush()

            self.logger.debug(
                "Bulk update completed",
                entity_type=self.model_class.__name__,
                updated_count=update_count,
            )

            return update_count

        except Exception as e:
            await self.session.rollback()
            self.logger.error(
                "Failed to bulk update",
                entity_type=self.model_class.__name__,
                error=str(e),
            )
            raise RepositoryError(
                f"Failed to bulk update {self.model_class.__name__}: {str(e)}"
            )

    async def get_page(
        self,
        page: int = 1,
        per_page: int = 20,
        order_by: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Get paginated results with metadata."""
        try:
            # Calculate offset
            offset = (page - 1) * per_page

            # Get total count
            total_count = await self.count(filters)

            # Get entities
            entities = await self.list(
                limit=per_page,
                offset=offset,
                order_by=order_by,
                filters=filters,
            )

            # Calculate pagination metadata
            total_pages = (total_count + per_page - 1) // per_page
            has_prev = page > 1
            has_next = page < total_pages

            return {
                "entities": entities,
                "pagination": {
                    "page": page,
                    "per_page": per_page,
                    "total_count": total_count,
                    "total_pages": total_pages,
                    "has_prev": has_prev,
                    "has_next": has_next,
                },
            }

        except Exception as e:
            self.logger.error(
                "Failed to get paginated results",
                entity_type=self.model_class.__name__,
                page=page,
                per_page=per_page,
                error=str(e),
            )
            raise RepositoryError(
                f"Failed to get paginated {self.model_class.__name__}: {str(e)}"
            )
