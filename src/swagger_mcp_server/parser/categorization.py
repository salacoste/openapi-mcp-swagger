"""Category extraction engine for OpenAPI specifications.

Epic 6: Hierarchical Endpoint Catalog System
Implements automatic categorization using hybrid strategy:
1. Priority 1: Extract from operation.tags array
2. Priority 2: Extract hierarchy from x-tagGroups vendor extension
3. Priority 3: Fallback to path-based categorization
4. Priority 4: Default to "Uncategorized"
"""

import asyncio
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Dict, List, Optional, Tuple

from swagger_mcp_server.config.logging import get_logger

logger = get_logger(__name__)


@dataclass
class CategoryInfo:
    """Structured category information for an endpoint."""

    category: str  # Primary category name (machine-readable)
    display_name: Optional[str] = None  # Human-readable display name
    description: Optional[str] = None  # Category description
    category_group: Optional[str] = None  # Parent group name
    metadata: Optional[Dict] = None  # Additional category metadata

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON storage."""
        return {
            "category": self.category,
            "display_name": self.display_name,
            "description": self.description,
            "category_group": self.category_group,
            "metadata": self.metadata or {},
        }


class CategorizationEngine:
    """Engine for automatic endpoint categorization."""

    # Pre-compiled regex patterns for path extraction
    PATH_PATTERNS = [
        re.compile(r"^/api/(?:v\d+/)?([^/]+)/?"),  # /api/v1/category or /api/category
        re.compile(r"^/(?:v\d+/)?([^/]+)/?"),  # /v1/category or /category
        re.compile(r"^/([^/]+)/?"),  # /category
    ]

    def __init__(self):
        """Initialize categorization engine."""
        self.logger = logger
        self._tag_definitions: Dict[str, Dict] = {}
        self._tag_groups: List[Dict] = []

    def set_tag_definitions(self, tags: List[Dict]) -> None:
        """Set tag definitions from OpenAPI spec root.

        Args:
            tags: List of tag definition objects with name, description, x-displayName
        """
        self._tag_definitions = {
            tag.get("name", ""): tag for tag in tags if tag.get("name")
        }
        self.logger.debug("Tag definitions loaded", count=len(self._tag_definitions))

    def set_tag_groups(self, tag_groups: List[Dict]) -> None:
        """Set x-tagGroups vendor extension from OpenAPI spec root.

        Args:
            tag_groups: List of tag group objects with name and tags array
        """
        self._tag_groups = tag_groups or []
        self.logger.debug("Tag groups loaded", count=len(self._tag_groups))

    def categorize_endpoint(
        self, operation: Dict, path: str
    ) -> CategoryInfo:
        """Categorize an endpoint using hybrid strategy.

        Args:
            operation: OpenAPI operation object
            path: Endpoint path

        Returns:
            CategoryInfo with extracted category data
        """
        # Validate inputs
        if not isinstance(operation, dict):
            self.logger.warning(
                "Invalid operation object, using default category",
                path=path,
                operation_type=type(operation).__name__,
            )
            return self._get_default_category()

        if not path or not isinstance(path, str):
            self.logger.warning(
                "Invalid path, using default category",
                path=path,
            )
            return self._get_default_category()

        try:
            tags = operation.get("tags", [])

            # Priority 1: Extract from tags
            if tags and isinstance(tags, list):
                category_info = self.extract_category_from_tags(tags)
                if category_info:
                    self.logger.debug(
                        "Category extracted from tags",
                        path=path,
                        category=category_info.category,
                    )
                    return category_info

            # Priority 2: Extract from path
            category = self.extract_category_from_path(path)
            if category:
                self.logger.debug(
                    "Category extracted from path", path=path, category=category
                )
                return CategoryInfo(
                    category=category,
                    display_name=category.replace("_", " ").title(),
                )

            # Priority 3: Default to Uncategorized
            self.logger.debug("Using default category", path=path)
            return self._get_default_category()

        except Exception as e:
            self.logger.error(
                "Error during categorization, using default",
                path=path,
                error=str(e),
            )
            return self._get_default_category()

    def _get_default_category(self) -> CategoryInfo:
        """Get default category for uncategorized endpoints.

        Returns:
            Default CategoryInfo object
        """
        return CategoryInfo(
            category="Uncategorized",
            display_name="Uncategorized",
            description="Endpoints without explicit categorization",
        )

    def extract_category_from_tags(
        self, tags: List[str]
    ) -> Optional[CategoryInfo]:
        """Extract category information from operation tags.

        Args:
            tags: List of tag strings from operation

        Returns:
            CategoryInfo if tags are found, None otherwise
        """
        if not tags:
            return None

        # Use first tag as primary category
        primary_tag = tags[0]

        # Lookup tag definition for metadata
        tag_def = self._tag_definitions.get(primary_tag, {})

        # Resolve hierarchy from tag groups
        category_group = self._resolve_category_group(primary_tag)

        return CategoryInfo(
            category=self.normalize_category_name(primary_tag),
            display_name=tag_def.get("x-displayName") or tag_def.get("name") or primary_tag,
            description=tag_def.get("description"),
            category_group=category_group,
            metadata={
                "original_tag": primary_tag,
                "all_tags": tags,
            },
        )

    def _resolve_category_group(self, tag: str) -> Optional[str]:
        """Resolve parent group for a tag from x-tagGroups.

        Args:
            tag: Tag name to lookup

        Returns:
            Group name if found, None otherwise
        """
        for group in self._tag_groups:
            group_tags = group.get("tags", [])
            if tag in group_tags:
                return group.get("name")
        return None

    @lru_cache(maxsize=256)
    def extract_category_from_path(self, path: str) -> Optional[str]:
        """Extract category from URL path using pattern matching.

        Args:
            path: Endpoint path (e.g., /api/v1/campaign/list)

        Returns:
            Category name if extracted, None otherwise

        Examples:
            /api/v1/campaign/list -> campaign
            /api/client/statistics -> client
            /campaign -> campaign
        """
        if not path or path == "/":
            return None

        # Try each pattern in order of specificity
        for pattern in self.PATH_PATTERNS:
            match = pattern.match(path)
            if match:
                category = match.group(1)
                # Filter out common non-category segments
                if category.lower() not in {"api", "v1", "v2", "v3", "v4", "client"}:
                    return self.normalize_category_name(category)

        return None

    @staticmethod
    @lru_cache(maxsize=512)
    def normalize_category_name(raw_name: str) -> str:
        """Normalize category name to consistent format.

        Args:
            raw_name: Raw category name (may contain spaces, special chars)

        Returns:
            Normalized category name (lowercase, underscores)

        Examples:
            "Campaign Management" -> "campaign_management"
            "Search-Promo" -> "search_promo"
            "Статистика" -> "статистика"
        """
        if not raw_name:
            return "uncategorized"

        # Convert to lowercase
        normalized = raw_name.lower()

        # Replace hyphens and spaces with underscores
        normalized = re.sub(r"[-\s]+", "_", normalized)

        # Remove special characters except underscores and unicode letters
        normalized = re.sub(r"[^\w]", "", normalized)

        # Remove leading/trailing underscores
        normalized = normalized.strip("_")

        return normalized or "uncategorized"

    def resolve_category_hierarchy(
        self, tags: List[str]
    ) -> Tuple[Optional[str], Optional[str]]:
        """Resolve category hierarchy from tags and tag groups.

        Args:
            tags: List of tag strings

        Returns:
            Tuple of (category, group) where both may be None
        """
        if not tags:
            return None, None

        primary_tag = tags[0]
        category = self.normalize_category_name(primary_tag)
        group = self._resolve_category_group(primary_tag)

        return category, group


class CategoryCatalog:
    """Builds and manages category catalog for an API.

    Thread-safe for async contexts using asyncio.Lock.
    """

    def __init__(self):
        """Initialize category catalog."""
        self.logger = logger
        self._categories: Dict[str, Dict] = {}
        self._lock = asyncio.Lock()

    async def add_endpoint(
        self, category_info: CategoryInfo, method: str
    ) -> None:
        """Add endpoint to category catalog (async, thread-safe).

        Args:
            category_info: Category information
            method: HTTP method (GET, POST, etc.)
        """
        async with self._lock:
            category = category_info.category

            if category not in self._categories:
                self._categories[category] = {
                    "category_name": category,
                    "display_name": category_info.display_name or category,
                    "description": category_info.description,
                    "category_group": category_info.category_group,
                    "endpoint_count": 0,
                    "http_methods": set(),
                }

            # Update statistics
            self._categories[category]["endpoint_count"] += 1
            self._categories[category]["http_methods"].add(method.upper())

    def add_endpoint_sync(
        self, category_info: CategoryInfo, method: str
    ) -> None:
        """Add endpoint to category catalog (synchronous version).

        Use this for non-async contexts. For async contexts, use add_endpoint().

        Args:
            category_info: Category information
            method: HTTP method (GET, POST, etc.)
        """
        category = category_info.category

        if category not in self._categories:
            self._categories[category] = {
                "category_name": category,
                "display_name": category_info.display_name or category,
                "description": category_info.description,
                "category_group": category_info.category_group,
                "endpoint_count": 0,
                "http_methods": set(),
            }

        # Update statistics
        self._categories[category]["endpoint_count"] += 1
        self._categories[category]["http_methods"].add(method.upper())

    def get_categories(self) -> List[Dict]:
        """Get list of all categories with statistics.

        Returns:
            List of category dictionaries ready for database insertion
        """
        categories = []
        for cat_data in self._categories.values():
            # Convert set to sorted list
            cat_dict = cat_data.copy()
            cat_dict["http_methods"] = sorted(cat_dict["http_methods"])
            categories.append(cat_dict)

        # Sort by endpoint count (descending) then name
        categories.sort(key=lambda x: (-x["endpoint_count"], x["category_name"]))

        self.logger.debug("Category catalog built", categories=len(categories))
        return categories

    def get_statistics(self) -> Dict:
        """Get catalog statistics.

        Returns:
            Statistics dictionary
        """
        return {
            "total_categories": len(self._categories),
            "categories_with_groups": sum(
                1 for cat in self._categories.values() if cat["category_group"]
            ),
            "total_endpoints": sum(
                cat["endpoint_count"] for cat in self._categories.values()
            ),
        }