"""Search result optimization and filtering for the Swagger MCP Server.

This module provides sophisticated result processing capabilities including:
- Advanced filtering by endpoint characteristics (HTTP methods, auth, parameters, etc.)
- Result clustering and organization by tags, resources, complexity
- Enhanced ranking and scoring with contextual metadata
- Efficient pagination and result limiting
- Intelligent caching for performance optimization

Integrates with the existing search infrastructure to deliver optimized results.
"""

import asyncio
import hashlib
import logging
import re
import time
from collections import defaultdict
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from ..config.settings import SearchConfig


class ComplexityLevel(Enum):
    """Endpoint complexity classification."""

    SIMPLE = "simple"  # 0-3 parameters, basic responses
    MODERATE = "moderate"  # 4-8 parameters, structured responses
    COMPLEX = "complex"  # 9+ parameters, nested schemas


class AuthenticationType(Enum):
    """Authentication scheme types."""

    NONE = "none"
    BEARER = "bearer"
    API_KEY = "apiKey"
    OAUTH2 = "oauth2"
    BASIC = "basic"
    CUSTOM = "custom"


class OperationType(Enum):
    """REST operation types."""

    CREATE = "create"  # POST operations
    READ = "read"  # GET operations
    UPDATE = "update"  # PUT/PATCH operations
    DELETE = "delete"  # DELETE operations
    LIST = "list"  # GET collections
    UPLOAD = "upload"  # File upload operations
    ACTION = "action"  # Custom actions


@dataclass
class ParameterSummary:
    """Summary of endpoint parameters."""

    total_count: int
    required_count: int
    optional_count: int
    parameter_types: Dict[str, int]  # type -> count
    has_file_upload: bool
    has_complex_types: bool
    common_parameters: List[str]


@dataclass
class AuthenticationInfo:
    """Authentication requirements for endpoint."""

    required: bool
    schemes: List[AuthenticationType]
    scopes: List[str]
    description: str


@dataclass
class ResponseInfo:
    """Response characteristics for endpoint."""

    status_codes: List[int]
    content_types: List[str]
    has_json_response: bool
    has_binary_response: bool
    response_complexity: ComplexityLevel
    common_responses: List[str]


@dataclass
class EnhancedSearchResult:
    """Enhanced search result with comprehensive metadata."""

    # Core endpoint information
    endpoint_id: str
    path: str
    method: str
    summary: str
    description: str

    # Relevance and ranking
    relevance_score: float
    rank_position: int
    ranking_factors: List[str]

    # Contextual metadata
    complexity_level: ComplexityLevel
    parameter_summary: ParameterSummary
    authentication_info: AuthenticationInfo
    response_info: ResponseInfo

    # Organizational metadata
    tags: List[str]
    resource_group: str
    operation_type: OperationType

    # Additional metadata
    deprecated: bool
    version: Optional[str]
    stability: str  # "stable", "beta", "alpha"


@dataclass
class ResultSummary:
    """Summary statistics for result set."""

    total_results: int
    filtered_results: int
    results_by_method: Dict[str, int]
    results_by_auth: Dict[str, int]
    results_by_complexity: Dict[str, int]
    average_relevance_score: float
    processing_time_ms: float


@dataclass
class PaginationInfo:
    """Pagination metadata for results."""

    page: int
    per_page: int
    total_pages: int
    total_results: int
    has_previous: bool
    has_next: bool
    previous_page: Optional[int]
    next_page: Optional[int]


class ResultFilter:
    """Advanced result filtering with multiple criteria support."""

    def __init__(self, config: SearchConfig):
        """Initialize result filter.

        Args:
            config: Search configuration settings
        """
        self.config = config
        self.logger = logging.getLogger(__name__)

    def apply_filters(self, results: List[Dict], filters: Dict[str, Any]) -> List[Dict]:
        """Apply multiple filtering criteria to search results.

        Args:
            results: Raw search results
            filters: Filtering criteria dictionary

        Returns:
            List[Dict]: Filtered results
        """
        if not filters:
            return results

        filtered = results.copy()

        try:
            # HTTP method filtering
            if "methods" in filters and filters["methods"]:
                filtered = self._filter_by_methods(filtered, filters["methods"])

            # Authentication filtering
            if "authentication" in filters:
                filtered = self._filter_by_authentication(
                    filtered, filters["authentication"]
                )

            # Parameter filtering
            if "parameters" in filters:
                filtered = self._filter_by_parameters(filtered, filters["parameters"])

            # Response filtering
            if "response_types" in filters:
                filtered = self._filter_by_response_types(
                    filtered, filters["response_types"]
                )

            # Complexity filtering
            if "complexity" in filters:
                filtered = self._filter_by_complexity(filtered, filters["complexity"])

            # Tag filtering
            if "tags" in filters and filters["tags"]:
                filtered = self._filter_by_tags(filtered, filters["tags"])

            # Deprecated filtering
            if "include_deprecated" in filters and not filters["include_deprecated"]:
                filtered = self._filter_by_deprecated(filtered, False)

            # Custom filtering
            if "custom" in filters:
                filtered = self._apply_custom_filters(filtered, filters["custom"])

        except Exception as e:
            self.logger.error(f"Error applying filters: {e}")
            # Return original results on filter error
            return results

        return filtered

    def _filter_by_methods(self, results: List[Dict], methods: List[str]) -> List[Dict]:
        """Filter by HTTP methods."""
        if not methods:
            return results

        methods_upper = [m.upper() for m in methods]
        return [r for r in results if r.get("http_method", "").upper() in methods_upper]

    def _filter_by_authentication(
        self, results: List[Dict], auth_filter: Dict
    ) -> List[Dict]:
        """Filter by authentication requirements."""
        if auth_filter.get("required") is False:
            # Return endpoints with no authentication
            return [r for r in results if not r.get("security_requirements")]

        if auth_filter.get("required") is True:
            # Return only endpoints with authentication
            return [r for r in results if r.get("security_requirements")]

        if "schemes" in auth_filter:
            # Filter by specific authentication schemes
            required_schemes = set(auth_filter["schemes"])
            return [
                r
                for r in results
                if set(r.get("security_schemes", [])) & required_schemes
            ]

        return results

    def _filter_by_parameters(
        self, results: List[Dict], param_filter: Dict
    ) -> List[Dict]:
        """Filter by parameter characteristics."""
        filtered = results

        if "required_only" in param_filter and param_filter["required_only"]:
            # Only endpoints with required parameters
            filtered = [r for r in filtered if r.get("required_parameters")]

        if "parameter_names" in param_filter:
            # Filter by specific parameter names
            required_params = set(param_filter["parameter_names"])
            filtered = [
                r
                for r in filtered
                if required_params.issubset(set(r.get("parameter_names", [])))
            ]

        if "max_parameters" in param_filter:
            # Limit by maximum parameter count
            max_params = param_filter["max_parameters"]
            filtered = [
                r for r in filtered if len(r.get("parameter_names", [])) <= max_params
            ]

        if "has_file_upload" in param_filter:
            # Filter by file upload capability
            has_upload = param_filter["has_file_upload"]
            filtered = [
                r for r in filtered if r.get("has_file_parameters", False) == has_upload
            ]

        return filtered

    def _filter_by_response_types(
        self, results: List[Dict], response_filter: List[str]
    ) -> List[Dict]:
        """Filter by response content types."""
        if not response_filter:
            return results

        return [
            r
            for r in results
            if any(
                content_type in r.get("response_types", [])
                for content_type in response_filter
            )
        ]

    def _filter_by_complexity(
        self, results: List[Dict], complexity_filter: List[str]
    ) -> List[Dict]:
        """Filter by endpoint complexity levels."""
        if not complexity_filter:
            return results

        return [
            r
            for r in results
            if r.get("complexity_level", "simple") in complexity_filter
        ]

    def _filter_by_tags(self, results: List[Dict], tags: List[str]) -> List[Dict]:
        """Filter by OpenAPI tags."""
        if not tags:
            return results

        return [r for r in results if any(tag in r.get("tags", []) for tag in tags)]

    def _filter_by_deprecated(
        self, results: List[Dict], include_deprecated: bool
    ) -> List[Dict]:
        """Filter by deprecation status."""
        if include_deprecated:
            return results

        return [r for r in results if not r.get("deprecated", False)]

    def _apply_custom_filters(
        self, results: List[Dict], custom_filters: Dict
    ) -> List[Dict]:
        """Apply custom filtering logic."""
        # Placeholder for extensible custom filtering
        # Could be extended with lambda functions or custom filter classes
        return results


class ResultOrganizer:
    """Organizes and clusters search results by various criteria."""

    def __init__(self, config: SearchConfig):
        """Initialize result organizer.

        Args:
            config: Search configuration settings
        """
        self.config = config
        self.logger = logging.getLogger(__name__)

    def organize_results(self, results: List[EnhancedSearchResult]) -> Dict[str, Any]:
        """Organize results by multiple criteria.

        Args:
            results: Enhanced search results

        Returns:
            Dict containing organized result clusters
        """
        try:
            organization = {
                "by_tags": self._cluster_by_tags(results),
                "by_resource": self._cluster_by_resource(results),
                "by_complexity": self._cluster_by_complexity(results),
                "by_method": self._cluster_by_method(results),
                "by_operation_type": self._cluster_by_operation_type(results),
                "by_auth_requirement": self._cluster_by_auth_requirement(results),
            }

            return organization

        except Exception as e:
            self.logger.error(f"Error organizing results: {e}")
            return {"by_relevance": results}

    def _cluster_by_tags(self, results: List[EnhancedSearchResult]) -> Dict[str, List]:
        """Cluster results by OpenAPI tags."""
        clusters = defaultdict(list)

        for result in results:
            if not result.tags:
                clusters["untagged"].append(result)
            else:
                for tag in result.tags:
                    clusters[tag].append(result)

        return dict(clusters)

    def _cluster_by_resource(
        self, results: List[EnhancedSearchResult]
    ) -> Dict[str, List]:
        """Cluster results by REST resource patterns."""
        clusters = defaultdict(list)

        for result in results:
            resource = self._extract_resource_name(result.path)
            clusters[resource].append(result)

        return dict(clusters)

    def _cluster_by_complexity(
        self, results: List[EnhancedSearchResult]
    ) -> Dict[str, List]:
        """Cluster results by complexity level."""
        clusters = defaultdict(list)

        for result in results:
            complexity = result.complexity_level.value
            clusters[complexity].append(result)

        return dict(clusters)

    def _cluster_by_method(
        self, results: List[EnhancedSearchResult]
    ) -> Dict[str, List]:
        """Cluster results by HTTP method."""
        clusters = defaultdict(list)

        for result in results:
            clusters[result.method.upper()].append(result)

        return dict(clusters)

    def _cluster_by_operation_type(
        self, results: List[EnhancedSearchResult]
    ) -> Dict[str, List]:
        """Cluster results by operation type (CRUD operations)."""
        clusters = defaultdict(list)

        for result in results:
            op_type = result.operation_type.value
            clusters[op_type].append(result)

        return dict(clusters)

    def _cluster_by_auth_requirement(
        self, results: List[EnhancedSearchResult]
    ) -> Dict[str, List]:
        """Cluster results by authentication requirements."""
        clusters = defaultdict(list)

        for result in results:
            if result.authentication_info.required:
                auth_types = [
                    scheme.value for scheme in result.authentication_info.schemes
                ]
                for auth_type in auth_types:
                    clusters[f"auth_{auth_type}"].append(result)
            else:
                clusters["no_auth"].append(result)

        return dict(clusters)

    def _extract_resource_name(self, path: str) -> str:
        """Extract resource name from endpoint path."""
        # Remove path parameters and extract main resource
        # e.g., "/api/v1/users/{id}/profile" -> "users"
        path_parts = [
            part for part in path.split("/") if part and not part.startswith("{")
        ]

        # Skip common prefixes like api, v1, etc.
        resource_parts = [
            part for part in path_parts if part not in ["api", "v1", "v2", "v3"]
        ]

        if resource_parts:
            return resource_parts[0]
        elif path_parts:
            return path_parts[-1]
        else:
            return "unknown"


class MetadataEnhancer:
    """Enhances search results with comprehensive contextual metadata."""

    def __init__(self, config: SearchConfig):
        """Initialize metadata enhancer.

        Args:
            config: Search configuration settings
        """
        self.config = config
        self.logger = logging.getLogger(__name__)

    async def enhance_with_metadata(
        self, results: List[Dict]
    ) -> List[EnhancedSearchResult]:
        """Enhance results with comprehensive metadata.

        Args:
            results: Raw search results

        Returns:
            List[EnhancedSearchResult]: Enhanced results with metadata
        """
        enhanced_results = []

        try:
            for i, result in enumerate(results):
                # Analyze parameters
                param_summary = self._analyze_parameters(result.get("parameters", {}))

                # Extract authentication info
                auth_info = self._extract_authentication_info(
                    result.get("security", {})
                )

                # Analyze responses
                response_info = self._analyze_responses(result.get("responses", {}))

                # Determine complexity
                complexity = self._determine_complexity(param_summary, response_info)

                # Extract organizational metadata
                resource_group = self._extract_resource_group(
                    result.get("endpoint_path", "")
                )
                operation_type = self._determine_operation_type(
                    result.get("http_method", ""),
                    result.get("endpoint_path", ""),
                )

                # Extract ranking factors
                ranking_factors = self._extract_ranking_factors(result)

                enhanced_result = EnhancedSearchResult(
                    endpoint_id=result.get("endpoint_id", f"endpoint_{i}"),
                    path=result.get("endpoint_path", ""),
                    method=result.get("http_method", "GET"),
                    summary=result.get("summary", ""),
                    description=result.get("description", ""),
                    relevance_score=float(result.get("score", 0.0)),
                    rank_position=i + 1,
                    ranking_factors=ranking_factors,
                    complexity_level=complexity,
                    parameter_summary=param_summary,
                    authentication_info=auth_info,
                    response_info=response_info,
                    tags=(
                        result.get("tags", "").split(",") if result.get("tags") else []
                    ),
                    resource_group=resource_group,
                    operation_type=operation_type,
                    deprecated=result.get("deprecated", False),
                    version=result.get("version"),
                    stability=result.get("stability", "stable"),
                )

                enhanced_results.append(enhanced_result)

        except Exception as e:
            self.logger.error(f"Error enhancing metadata: {e}")
            # Return basic enhanced results on error
            return self._create_basic_enhanced_results(results)

        return enhanced_results

    def _analyze_parameters(self, parameters: Dict) -> ParameterSummary:
        """Analyze endpoint parameters."""
        if not parameters:
            return ParameterSummary(
                total_count=0,
                required_count=0,
                optional_count=0,
                parameter_types={},
                has_file_upload=False,
                has_complex_types=False,
                common_parameters=[],
            )

        # Parse parameters string or dict
        if isinstance(parameters, str):
            param_names = [p.strip() for p in parameters.split(",") if p.strip()]
            total_count = len(param_names)
            required_count = total_count  # Assume all required if just names
            optional_count = 0
            parameter_types = {"string": total_count}
            has_file_upload = any("file" in name.lower() for name in param_names)
            has_complex_types = False
            common_parameters = param_names
        else:
            # Handle structured parameter data
            total_count = len(parameters)
            required_count = sum(
                1 for p in parameters.values() if p.get("required", False)
            )
            optional_count = total_count - required_count
            parameter_types = {}
            has_file_upload = any(p.get("type") == "file" for p in parameters.values())
            has_complex_types = any(
                p.get("type") in ["object", "array"] for p in parameters.values()
            )
            common_parameters = list(parameters.keys())

            for param in parameters.values():
                param_type = param.get("type", "string")
                parameter_types[param_type] = parameter_types.get(param_type, 0) + 1

        return ParameterSummary(
            total_count=total_count,
            required_count=required_count,
            optional_count=optional_count,
            parameter_types=parameter_types,
            has_file_upload=has_file_upload,
            has_complex_types=has_complex_types,
            common_parameters=common_parameters[:5],  # Limit to top 5
        )

    def _extract_authentication_info(self, security: Dict) -> AuthenticationInfo:
        """Extract authentication information."""
        if not security:
            return AuthenticationInfo(
                required=False,
                schemes=[AuthenticationType.NONE],
                scopes=[],
                description="No authentication required",
            )

        # Parse security requirements
        schemes = []
        scopes = []

        if isinstance(security, dict):
            for scheme_name, scheme_scopes in security.items():
                # Map common scheme names to types
                if "bearer" in scheme_name.lower():
                    schemes.append(AuthenticationType.BEARER)
                elif "api" in scheme_name.lower() and "key" in scheme_name.lower():
                    schemes.append(AuthenticationType.API_KEY)
                elif "oauth" in scheme_name.lower():
                    schemes.append(AuthenticationType.OAUTH2)
                elif "basic" in scheme_name.lower():
                    schemes.append(AuthenticationType.BASIC)
                else:
                    schemes.append(AuthenticationType.CUSTOM)

                if isinstance(scheme_scopes, list):
                    scopes.extend(scheme_scopes)

        if not schemes:
            schemes = [AuthenticationType.CUSTOM]

        description = f"Requires {', '.join(s.value for s in schemes)} authentication"

        return AuthenticationInfo(
            required=True,
            schemes=schemes,
            scopes=scopes,
            description=description,
        )

    def _analyze_responses(self, responses: Dict) -> ResponseInfo:
        """Analyze response characteristics."""
        if not responses:
            return ResponseInfo(
                status_codes=[200],
                content_types=["application/json"],
                has_json_response=True,
                has_binary_response=False,
                response_complexity=ComplexityLevel.SIMPLE,
                common_responses=["200"],
            )

        # Extract status codes
        status_codes = []
        content_types = set()

        if isinstance(responses, dict):
            for status, response_data in responses.items():
                try:
                    status_codes.append(int(status))
                except ValueError:
                    continue

                if isinstance(response_data, dict):
                    content = response_data.get("content", {})
                    if isinstance(content, dict):
                        content_types.update(content.keys())

        if not status_codes:
            status_codes = [200]

        if not content_types:
            content_types = {"application/json"}

        content_types_list = list(content_types)
        has_json_response = any("json" in ct for ct in content_types_list)
        has_binary_response = any(
            ct in ["application/octet-stream", "image/", "video/", "audio/"]
            for ct in content_types_list
        )

        # Determine response complexity based on content types and status codes
        complexity = ComplexityLevel.SIMPLE
        if len(content_types_list) > 2 or len(status_codes) > 3:
            complexity = ComplexityLevel.MODERATE
        if has_binary_response or len(status_codes) > 5:
            complexity = ComplexityLevel.COMPLEX

        return ResponseInfo(
            status_codes=sorted(status_codes),
            content_types=content_types_list,
            has_json_response=has_json_response,
            has_binary_response=has_binary_response,
            response_complexity=complexity,
            common_responses=[str(code) for code in sorted(status_codes)[:3]],
        )

    def _determine_complexity(
        self, param_summary: ParameterSummary, response_info: ResponseInfo
    ) -> ComplexityLevel:
        """Determine overall endpoint complexity."""
        complexity_score = 0

        # Parameter complexity scoring
        if param_summary.total_count <= 3:
            complexity_score += 1
        elif param_summary.total_count <= 8:
            complexity_score += 2
        else:
            complexity_score += 3

        # Additional complexity factors
        if param_summary.has_file_upload:
            complexity_score += 1

        if param_summary.has_complex_types:
            complexity_score += 1

        # Response complexity scoring
        if response_info.response_complexity == ComplexityLevel.MODERATE:
            complexity_score += 1
        elif response_info.response_complexity == ComplexityLevel.COMPLEX:
            complexity_score += 2

        # Determine final complexity
        if complexity_score <= 2:
            return ComplexityLevel.SIMPLE
        elif complexity_score <= 4:
            return ComplexityLevel.MODERATE
        else:
            return ComplexityLevel.COMPLEX

    def _extract_resource_group(self, path: str) -> str:
        """Extract resource group from path."""
        if not path:
            return "unknown"

        # Extract main resource from path
        path_parts = [
            part for part in path.split("/") if part and not part.startswith("{")
        ]

        # Skip common prefixes
        resource_parts = [
            part for part in path_parts if part not in ["api", "v1", "v2", "v3"]
        ]

        return resource_parts[0] if resource_parts else "unknown"

    def _determine_operation_type(self, method: str, path: str) -> OperationType:
        """Determine REST operation type."""
        method = method.upper()
        path_lower = path.lower()

        # File upload detection
        if "upload" in path_lower or "file" in path_lower:
            return OperationType.UPLOAD

        # Method-based classification
        if method == "POST":
            # Check if it's a collection endpoint (likely CREATE)
            if path.endswith("}"):  # Individual resource action
                return OperationType.ACTION
            else:  # Collection endpoint
                return OperationType.CREATE
        elif method == "GET":
            # Check if it's a collection vs individual resource
            if path.endswith("}"):  # Individual resource
                return OperationType.READ
            else:  # Collection
                return OperationType.LIST
        elif method in ["PUT", "PATCH"]:
            return OperationType.UPDATE
        elif method == "DELETE":
            return OperationType.DELETE
        else:
            return OperationType.ACTION

    def _extract_ranking_factors(self, result: Dict) -> List[str]:
        """Extract factors that influenced ranking."""
        factors = []

        score = result.get("score", 0)
        if score > 0.8:
            factors.append("high_relevance")
        elif score > 0.5:
            factors.append("medium_relevance")
        else:
            factors.append("low_relevance")

        # Common endpoint patterns
        path = result.get("endpoint_path", "").lower()
        if any(common in path for common in ["user", "auth", "login"]):
            factors.append("common_endpoint")

        # Method-based factors
        method = result.get("http_method", "")
        if method == "GET":
            factors.append("read_operation")
        elif method == "POST":
            factors.append("create_operation")

        return factors

    def _create_basic_enhanced_results(
        self, results: List[Dict]
    ) -> List[EnhancedSearchResult]:
        """Create basic enhanced results when full enhancement fails."""
        enhanced_results = []

        for i, result in enumerate(results):
            enhanced_result = EnhancedSearchResult(
                endpoint_id=result.get("endpoint_id", f"endpoint_{i}"),
                path=result.get("endpoint_path", ""),
                method=result.get("http_method", "GET"),
                summary=result.get("summary", ""),
                description=result.get("description", ""),
                relevance_score=float(result.get("score", 0.0)),
                rank_position=i + 1,
                ranking_factors=["basic_ranking"],
                complexity_level=ComplexityLevel.SIMPLE,
                parameter_summary=ParameterSummary(0, 0, 0, {}, False, False, []),
                authentication_info=AuthenticationInfo(
                    False, [AuthenticationType.NONE], [], "Unknown"
                ),
                response_info=ResponseInfo(
                    [200],
                    ["application/json"],
                    True,
                    False,
                    ComplexityLevel.SIMPLE,
                    ["200"],
                ),
                tags=[],
                resource_group="unknown",
                operation_type=OperationType.READ,
                deprecated=False,
                version=None,
                stability="stable",
            )
            enhanced_results.append(enhanced_result)

        return enhanced_results


class ResultCache:
    """Intelligent caching for processed search results."""

    def __init__(self, max_cache_size: int = 1000, ttl_seconds: int = 300):
        """Initialize result cache.

        Args:
            max_cache_size: Maximum number of cached entries
            ttl_seconds: Time to live for cached entries
        """
        self.cache = {}
        self.access_times = {}
        self.access_count = {}
        self.max_size = max_cache_size
        self.ttl = ttl_seconds
        self.logger = logging.getLogger(__name__)

    def get_cache_key(self, query: str, filters: Dict, pagination: Dict) -> str:
        """Generate cache key for query combination.

        Args:
            query: Search query string
            filters: Applied filters
            pagination: Pagination settings

        Returns:
            str: Cache key hash
        """
        cache_data = f"{query}:{sorted(filters.items())}:{sorted(pagination.items())}"
        return hashlib.md5(cache_data.encode()).hexdigest()

    async def get_cached_results(self, cache_key: str) -> Optional[Dict]:
        """Retrieve cached results if available and not expired.

        Args:
            cache_key: Cache key to look up

        Returns:
            Optional[Dict]: Cached results or None
        """
        current_time = time.time()

        if cache_key in self.cache:
            # Check if entry has expired
            if current_time - self.access_times[cache_key] > self.ttl:
                # Remove expired entry
                del self.cache[cache_key]
                del self.access_times[cache_key]
                del self.access_count[cache_key]
                return None

            # Update access stats
            self.access_times[cache_key] = current_time
            self.access_count[cache_key] = self.access_count.get(cache_key, 0) + 1

            self.logger.debug(f"Cache hit for key: {cache_key[:8]}...")
            return self.cache[cache_key]

        self.logger.debug(f"Cache miss for key: {cache_key[:8]}...")
        return None

    async def cache_results(self, cache_key: str, results: Dict):
        """Cache processed results with LRU eviction.

        Args:
            cache_key: Cache key for storage
            results: Results to cache
        """
        current_time = time.time()

        # Evict entries if cache is full
        if len(self.cache) >= self.max_size:
            self._evict_lru_entries()

        # Store results
        self.cache[cache_key] = results
        self.access_times[cache_key] = current_time
        self.access_count[cache_key] = 1

        self.logger.debug(f"Cached results for key: {cache_key[:8]}...")

    def _evict_lru_entries(self):
        """Evict least recently used entries."""
        if not self.access_times:
            return

        # Find and remove oldest entries (remove 20% of cache)
        entries_to_remove = max(1, len(self.cache) // 5)
        oldest_entries = sorted(self.access_times.items(), key=lambda x: x[1])[
            :entries_to_remove
        ]

        for cache_key, _ in oldest_entries:
            del self.cache[cache_key]
            del self.access_times[cache_key]
            del self.access_count[cache_key]

        self.logger.debug(f"Evicted {entries_to_remove} cache entries")

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache performance statistics.

        Returns:
            Dict with cache statistics
        """
        total_accesses = sum(self.access_count.values())

        return {
            "entries": len(self.cache),
            "max_size": self.max_size,
            "total_accesses": total_accesses,
            "hit_rate": total_accesses / max(1, len(self.access_count)),
            "oldest_entry_age": (
                time.time() - min(self.access_times.values())
                if self.access_times
                else 0
            ),
        }


class ResultProcessor:
    """Main result processor coordinating filtering, enhancement, and caching."""

    def __init__(self, config: SearchConfig):
        """Initialize result processor.

        Args:
            config: Search configuration settings
        """
        self.config = config
        self.logger = logging.getLogger(__name__)

        # Initialize components
        self.filter = ResultFilter(config)
        self.organizer = ResultOrganizer(config)
        self.enhancer = MetadataEnhancer(config)
        self.cache = ResultCache(
            max_cache_size=getattr(config.performance, "cache_size", 1000),
            ttl_seconds=getattr(config.performance, "cache_ttl", 300),
        )

    async def process_search_results(
        self,
        raw_results: List[Dict],
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        pagination: Optional[Dict[str, int]] = None,
    ) -> Dict[str, Any]:
        """Process raw search results into enhanced, filtered, and organized results.

        Args:
            raw_results: Raw search results from search engine
            query: Original search query
            filters: Filtering criteria
            pagination: Pagination settings

        Returns:
            Dict containing processed results and metadata
        """
        start_time = time.time()

        if filters is None:
            filters = {}
        if pagination is None:
            pagination = {"page": 1, "per_page": 20}

        try:
            # Check cache first
            cache_key = self.cache.get_cache_key(query, filters, pagination)
            cached_results = await self.cache.get_cached_results(cache_key)
            if cached_results:
                return cached_results

            # Process results
            processed_results = await self._process_results_pipeline(
                raw_results, filters, pagination
            )

            # Add processing metadata
            processing_time = (time.time() - start_time) * 1000  # Convert to ms
            processed_results["processing_time_ms"] = processing_time
            processed_results["cache_key"] = cache_key

            # Cache results
            await self.cache.cache_results(cache_key, processed_results)

            return processed_results

        except Exception as e:
            self.logger.error(f"Error processing search results: {e}")
            # Return basic results on error
            return self._create_fallback_results(raw_results, filters, pagination)

    async def _process_results_pipeline(
        self,
        raw_results: List[Dict],
        filters: Dict[str, Any],
        pagination: Dict[str, int],
    ) -> Dict[str, Any]:
        """Execute the complete result processing pipeline."""

        # Step 1: Apply filtering
        filtered_results = self.filter.apply_filters(raw_results, filters)

        # Step 2: Enhance with metadata
        enhanced_results = await self.enhancer.enhance_with_metadata(filtered_results)

        # Step 3: Apply pagination
        paginated_results, pagination_info = self._paginate_results(
            enhanced_results, pagination
        )

        # Step 4: Organize results
        organized_results = self.organizer.organize_results(enhanced_results)

        # Step 5: Generate summary
        result_summary = self._generate_result_summary(
            raw_results, filtered_results, enhanced_results
        )

        return {
            "results": [asdict(result) for result in paginated_results],
            "pagination": asdict(pagination_info),
            "organization": organized_results,
            "summary": asdict(result_summary),
            "filters_applied": filters,
            "total_before_filters": len(raw_results),
            "total_after_filters": len(filtered_results),
        }

    def _paginate_results(
        self, results: List[EnhancedSearchResult], pagination: Dict[str, int]
    ) -> Tuple[List[EnhancedSearchResult], PaginationInfo]:
        """Apply pagination to results."""
        page = pagination.get("page", 1)
        per_page = pagination.get("per_page", 20)

        # Ensure reasonable limits
        per_page = min(per_page, 100)  # Max 100 results per page
        page = max(page, 1)  # Min page 1

        total_results = len(results)
        total_pages = (total_results + per_page - 1) // per_page

        start_index = (page - 1) * per_page
        end_index = start_index + per_page

        paginated_results = results[start_index:end_index]

        pagination_info = PaginationInfo(
            page=page,
            per_page=per_page,
            total_pages=total_pages,
            total_results=total_results,
            has_previous=page > 1,
            has_next=page < total_pages,
            previous_page=page - 1 if page > 1 else None,
            next_page=page + 1 if page < total_pages else None,
        )

        return paginated_results, pagination_info

    def _generate_result_summary(
        self,
        raw_results: List[Dict],
        filtered_results: List[Dict],
        enhanced_results: List[EnhancedSearchResult],
    ) -> ResultSummary:
        """Generate summary statistics for the result set."""

        # Count by method
        methods = defaultdict(int)
        for result in enhanced_results:
            methods[result.method.upper()] += 1

        # Count by auth requirement
        auth_counts = defaultdict(int)
        for result in enhanced_results:
            if result.authentication_info.required:
                auth_counts["required"] += 1
            else:
                auth_counts["none"] += 1

        # Count by complexity
        complexity_counts = defaultdict(int)
        for result in enhanced_results:
            complexity_counts[result.complexity_level.value] += 1

        # Calculate average relevance
        avg_relevance = 0.0
        if enhanced_results:
            avg_relevance = sum(r.relevance_score for r in enhanced_results) / len(
                enhanced_results
            )

        return ResultSummary(
            total_results=len(raw_results),
            filtered_results=len(filtered_results),
            results_by_method=dict(methods),
            results_by_auth=dict(auth_counts),
            results_by_complexity=dict(complexity_counts),
            average_relevance_score=avg_relevance,
            processing_time_ms=0.0,  # Set by caller
        )

    def _create_fallback_results(
        self,
        raw_results: List[Dict],
        filters: Dict[str, Any],
        pagination: Dict[str, int],
    ) -> Dict[str, Any]:
        """Create fallback results when processing fails."""

        page = pagination.get("page", 1)
        per_page = pagination.get("per_page", 20)

        start_index = (page - 1) * per_page
        end_index = start_index + per_page
        paginated_raw = raw_results[start_index:end_index]

        pagination_info = PaginationInfo(
            page=page,
            per_page=per_page,
            total_pages=(len(raw_results) + per_page - 1) // per_page,
            total_results=len(raw_results),
            has_previous=page > 1,
            has_next=end_index < len(raw_results),
            previous_page=page - 1 if page > 1 else None,
            next_page=page + 1 if end_index < len(raw_results) else None,
        )

        return {
            "results": paginated_raw,
            "pagination": asdict(pagination_info),
            "organization": {"by_relevance": paginated_raw},
            "summary": {
                "total_results": len(raw_results),
                "filtered_results": len(raw_results),
                "processing_time_ms": 0.0,
            },
            "filters_applied": filters,
            "error": "Fallback results due to processing error",
        }
