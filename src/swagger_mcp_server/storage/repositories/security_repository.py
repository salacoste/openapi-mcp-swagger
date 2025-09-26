"""Repository for security scheme data access operations."""

from typing import Any, Dict, List, Optional
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from swagger_mcp_server.storage.models import SecurityScheme
from swagger_mcp_server.storage.repositories.base import BaseRepository, RepositoryError
from swagger_mcp_server.config.logging import get_logger

logger = get_logger(__name__)


class SecurityRepository(BaseRepository[SecurityScheme]):
    """Repository for security scheme data access operations."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, SecurityScheme)

    async def get_by_name(
        self,
        name: str,
        api_id: Optional[int] = None
    ) -> Optional[SecurityScheme]:
        """Get security scheme by name."""
        try:
            stmt = select(SecurityScheme).where(SecurityScheme.name == name)

            if api_id:
                stmt = stmt.where(SecurityScheme.api_id == api_id)

            result = await self.session.execute(stmt)
            scheme = result.scalar_one_or_none()

            return scheme

        except Exception as e:
            self.logger.error(
                "Failed to get security scheme by name",
                name=name,
                api_id=api_id,
                error=str(e)
            )
            raise RepositoryError(f"Failed to get security scheme by name: {str(e)}")

    async def get_by_api_id(
        self,
        api_id: int
    ) -> List[SecurityScheme]:
        """Get all security schemes for a specific API."""
        try:
            stmt = select(SecurityScheme).where(SecurityScheme.api_id == api_id)
            stmt = stmt.order_by(SecurityScheme.name)

            result = await self.session.execute(stmt)
            schemes = result.scalars().all()

            return list(schemes)

        except Exception as e:
            self.logger.error(
                "Failed to get security schemes by API ID",
                api_id=api_id,
                error=str(e)
            )
            raise RepositoryError(f"Failed to get security schemes by API ID: {str(e)}")

    async def get_by_type(
        self,
        scheme_type: str,
        api_id: Optional[int] = None
    ) -> List[SecurityScheme]:
        """Get security schemes by type."""
        try:
            stmt = select(SecurityScheme).where(SecurityScheme.type == scheme_type)

            if api_id:
                stmt = stmt.where(SecurityScheme.api_id == api_id)

            stmt = stmt.order_by(SecurityScheme.name)

            result = await self.session.execute(stmt)
            schemes = result.scalars().all()

            return list(schemes)

        except Exception as e:
            self.logger.error(
                "Failed to get security schemes by type",
                scheme_type=scheme_type,
                api_id=api_id,
                error=str(e)
            )
            raise RepositoryError(f"Failed to get security schemes by type: {str(e)}")

    async def get_api_key_schemes(
        self,
        api_id: Optional[int] = None
    ) -> List[SecurityScheme]:
        """Get API key security schemes."""
        return await self.get_by_type('apiKey', api_id)

    async def get_oauth2_schemes(
        self,
        api_id: Optional[int] = None
    ) -> List[SecurityScheme]:
        """Get OAuth2 security schemes."""
        return await self.get_by_type('oauth2', api_id)

    async def get_http_schemes(
        self,
        api_id: Optional[int] = None
    ) -> List[SecurityScheme]:
        """Get HTTP security schemes."""
        return await self.get_by_type('http', api_id)

    async def get_openid_connect_schemes(
        self,
        api_id: Optional[int] = None
    ) -> List[SecurityScheme]:
        """Get OpenID Connect security schemes."""
        return await self.get_by_type('openIdConnect', api_id)

    async def get_mutual_tls_schemes(
        self,
        api_id: Optional[int] = None
    ) -> List[SecurityScheme]:
        """Get Mutual TLS security schemes."""
        return await self.get_by_type('mutualTLS', api_id)

    async def search_schemes(
        self,
        query: str,
        api_id: Optional[int] = None,
        scheme_type: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[SecurityScheme]:
        """Search security schemes by name and description."""
        try:
            if not query.strip():
                return await self._filter_schemes(api_id, scheme_type, limit, offset)

            # Text search conditions
            search_terms = query.split()
            text_conditions = []

            for term in search_terms:
                term_pattern = f"%{term}%"
                term_conditions = or_(
                    SecurityScheme.name.ilike(term_pattern),
                    SecurityScheme.description.ilike(term_pattern),
                    SecurityScheme.api_key_name.ilike(term_pattern),
                    SecurityScheme.http_scheme.ilike(term_pattern)
                )
                text_conditions.append(term_conditions)

            stmt = select(SecurityScheme)
            if text_conditions:
                stmt = stmt.where(and_(*text_conditions))

            # Additional filters
            if api_id:
                stmt = stmt.where(SecurityScheme.api_id == api_id)

            if scheme_type:
                stmt = stmt.where(SecurityScheme.type == scheme_type)

            stmt = stmt.limit(limit).offset(offset)

            result = await self.session.execute(stmt)
            schemes = result.scalars().all()

            return list(schemes)

        except Exception as e:
            self.logger.error(
                "Failed to search security schemes",
                query=query,
                api_id=api_id,
                error=str(e)
            )
            raise RepositoryError(f"Failed to search security schemes: {str(e)}")

    async def _filter_schemes(
        self,
        api_id: Optional[int] = None,
        scheme_type: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[SecurityScheme]:
        """Filter security schemes without text search."""
        filters = {}

        if api_id:
            filters['api_id'] = api_id

        if scheme_type:
            filters['type'] = scheme_type

        return await self.list(
            limit=limit,
            offset=offset,
            filters=filters,
            order_by='name'
        )

    async def get_most_used(
        self,
        api_id: Optional[int] = None,
        limit: int = 10
    ) -> List[SecurityScheme]:
        """Get security schemes ordered by reference count (most used first)."""
        try:
            stmt = select(SecurityScheme).where(SecurityScheme.reference_count > 0)

            if api_id:
                stmt = stmt.where(SecurityScheme.api_id == api_id)

            stmt = stmt.order_by(SecurityScheme.reference_count.desc()).limit(limit)

            result = await self.session.execute(stmt)
            schemes = result.scalars().all()

            return list(schemes)

        except Exception as e:
            self.logger.error(
                "Failed to get most used security schemes",
                api_id=api_id,
                error=str(e)
            )
            raise RepositoryError(f"Failed to get most used security schemes: {str(e)}")

    async def get_unused_schemes(
        self,
        api_id: Optional[int] = None
    ) -> List[SecurityScheme]:
        """Get security schemes that are not used by any endpoint."""
        try:
            stmt = select(SecurityScheme).where(SecurityScheme.reference_count == 0)

            if api_id:
                stmt = stmt.where(SecurityScheme.api_id == api_id)

            stmt = stmt.order_by(SecurityScheme.name)

            result = await self.session.execute(stmt)
            schemes = result.scalars().all()

            return list(schemes)

        except Exception as e:
            self.logger.error(
                "Failed to get unused security schemes",
                api_id=api_id,
                error=str(e)
            )
            raise RepositoryError(f"Failed to get unused security schemes: {str(e)}")

    async def get_all_types(self, api_id: Optional[int] = None) -> List[str]:
        """Get all unique security scheme types."""
        try:
            stmt = select(SecurityScheme.type).distinct()

            if api_id:
                stmt = stmt.where(SecurityScheme.api_id == api_id)

            stmt = stmt.order_by(SecurityScheme.type)

            result = await self.session.execute(stmt)
            types = result.scalars().all()

            return list(types)

        except Exception as e:
            self.logger.error(
                "Failed to get all security scheme types",
                api_id=api_id,
                error=str(e)
            )
            raise RepositoryError(f"Failed to get all security scheme types: {str(e)}")

    async def get_oauth2_flows(
        self,
        scheme_name: str,
        api_id: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """Get OAuth2 flows for a security scheme."""
        try:
            scheme = await self.get_by_name(scheme_name, api_id)
            if not scheme or scheme.type != 'oauth2':
                return None

            return scheme.oauth2_flows

        except Exception as e:
            self.logger.error(
                "Failed to get OAuth2 flows",
                scheme_name=scheme_name,
                api_id=api_id,
                error=str(e)
            )
            raise RepositoryError(f"Failed to get OAuth2 flows: {str(e)}")

    async def get_by_http_scheme(
        self,
        http_scheme: str,
        api_id: Optional[int] = None
    ) -> List[SecurityScheme]:
        """Get HTTP security schemes by HTTP scheme type."""
        try:
            stmt = select(SecurityScheme).where(
                and_(
                    SecurityScheme.type == 'http',
                    SecurityScheme.http_scheme == http_scheme
                )
            )

            if api_id:
                stmt = stmt.where(SecurityScheme.api_id == api_id)

            result = await self.session.execute(stmt)
            schemes = result.scalars().all()

            return list(schemes)

        except Exception as e:
            self.logger.error(
                "Failed to get security schemes by HTTP scheme",
                http_scheme=http_scheme,
                api_id=api_id,
                error=str(e)
            )
            raise RepositoryError(f"Failed to get security schemes by HTTP scheme: {str(e)}")

    async def get_by_api_key_location(
        self,
        location: str,
        api_id: Optional[int] = None
    ) -> List[SecurityScheme]:
        """Get API key security schemes by location."""
        try:
            stmt = select(SecurityScheme).where(
                and_(
                    SecurityScheme.type == 'apiKey',
                    SecurityScheme.api_key_location == location
                )
            )

            if api_id:
                stmt = stmt.where(SecurityScheme.api_id == api_id)

            result = await self.session.execute(stmt)
            schemes = result.scalars().all()

            return list(schemes)

        except Exception as e:
            self.logger.error(
                "Failed to get security schemes by API key location",
                location=location,
                api_id=api_id,
                error=str(e)
            )
            raise RepositoryError(f"Failed to get security schemes by API key location: {str(e)}")

    async def get_statistics(self, api_id: Optional[int] = None) -> Dict[str, Any]:
        """Get security scheme statistics."""
        try:
            base_query = select(SecurityScheme)
            if api_id:
                base_query = base_query.where(SecurityScheme.api_id == api_id)

            # Total count
            total_query = select(func.count()).select_from(
                base_query.subquery()
            )
            total_result = await self.session.execute(total_query)
            total_schemes = total_result.scalar() or 0

            # Type distribution
            type_query = select(
                SecurityScheme.type,
                func.count(SecurityScheme.type).label('count')
            )
            if api_id:
                type_query = type_query.where(SecurityScheme.api_id == api_id)

            type_query = type_query.group_by(SecurityScheme.type)
            type_result = await self.session.execute(type_query)
            types = {row.type: row.count for row in type_result.fetchall()}

            # Used count
            used_query = select(func.count()).where(SecurityScheme.reference_count > 0)
            if api_id:
                used_query = used_query.where(SecurityScheme.api_id == api_id)

            used_result = await self.session.execute(used_query)
            used_count = used_result.scalar() or 0

            # HTTP scheme distribution
            http_schemes = {}
            if 'http' in types:
                http_query = select(
                    SecurityScheme.http_scheme,
                    func.count(SecurityScheme.http_scheme).label('count')
                ).where(SecurityScheme.type == 'http')

                if api_id:
                    http_query = http_query.where(SecurityScheme.api_id == api_id)

                http_query = http_query.group_by(SecurityScheme.http_scheme)
                http_result = await self.session.execute(http_query)
                http_schemes = {row.http_scheme: row.count for row in http_result.fetchall()}

            # API key location distribution
            api_key_locations = {}
            if 'apiKey' in types:
                location_query = select(
                    SecurityScheme.api_key_location,
                    func.count(SecurityScheme.api_key_location).label('count')
                ).where(SecurityScheme.type == 'apiKey')

                if api_id:
                    location_query = location_query.where(SecurityScheme.api_id == api_id)

                location_query = location_query.group_by(SecurityScheme.api_key_location)
                location_result = await self.session.execute(location_query)
                api_key_locations = {row.api_key_location: row.count for row in location_result.fetchall()}

            return {
                'total_schemes': total_schemes,
                'types': types,
                'used_count': used_count,
                'unused_count': total_schemes - used_count,
                'usage_rate': (
                    (used_count / total_schemes * 100)
                    if total_schemes > 0 else 0
                ),
                'http_schemes': http_schemes,
                'api_key_locations': api_key_locations,
            }

        except Exception as e:
            self.logger.error(
                "Failed to get security scheme statistics",
                api_id=api_id,
                error=str(e)
            )
            raise RepositoryError(f"Failed to get security scheme statistics: {str(e)}")

    async def update_reference_counts(self, api_id: Optional[int] = None) -> None:
        """Update reference counts for all security schemes."""
        try:
            # This would typically be called after importing/updating API data
            # For now, reset all counts to 0 and let the endpoint import update them
            schemes = await self.get_by_api_id(api_id) if api_id else await self.list()

            for scheme in schemes:
                scheme.reference_count = 0
                await self.update(scheme)

            self.logger.info(
                "Security scheme reference counts reset",
                api_id=api_id,
                count=len(schemes)
            )

        except Exception as e:
            self.logger.error(
                "Failed to update reference counts",
                api_id=api_id,
                error=str(e)
            )
            raise RepositoryError(f"Failed to update reference counts: {str(e)}")

    async def increment_reference_count(
        self,
        scheme_name: str,
        api_id: Optional[int] = None
    ) -> None:
        """Increment reference count for a security scheme."""
        try:
            scheme = await self.get_by_name(scheme_name, api_id)
            if scheme:
                scheme.reference_count = (scheme.reference_count or 0) + 1
                await self.update(scheme)

        except Exception as e:
            self.logger.error(
                "Failed to increment reference count",
                scheme_name=scheme_name,
                api_id=api_id,
                error=str(e)
            )
            raise RepositoryError(f"Failed to increment reference count: {str(e)}")

    async def decrement_reference_count(
        self,
        scheme_name: str,
        api_id: Optional[int] = None
    ) -> None:
        """Decrement reference count for a security scheme."""
        try:
            scheme = await self.get_by_name(scheme_name, api_id)
            if scheme and scheme.reference_count > 0:
                scheme.reference_count -= 1
                await self.update(scheme)

        except Exception as e:
            self.logger.error(
                "Failed to decrement reference count",
                scheme_name=scheme_name,
                api_id=api_id,
                error=str(e)
            )
            raise RepositoryError(f"Failed to decrement reference count: {str(e)}")