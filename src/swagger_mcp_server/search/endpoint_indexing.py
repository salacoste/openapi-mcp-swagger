"""Intelligent endpoint indexing for comprehensive search capabilities.

This module implements the comprehensive endpoint indexing system from Story 3.2,
creating rich searchable documents that capture complete endpoint semantic context.
"""

import asyncio
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set
from urllib.parse import urlparse


@dataclass
class EndpointSearchDocument:
    """Comprehensive search document for API endpoint.

    This dataclass captures all searchable aspects of an API endpoint
    as specified in Story 3.2 requirements.
    """

    # Core identification
    endpoint_id: str
    endpoint_path: str
    http_method: str

    # Searchable content
    operation_summary: str = ""
    operation_description: str = ""
    operation_id: str = ""
    path_segments: List[str] = field(default_factory=list)

    # Parameters
    parameter_names: List[str] = field(default_factory=list)
    parameter_descriptions: str = ""
    parameter_types: List[str] = field(default_factory=list)
    required_parameters: List[str] = field(default_factory=list)
    optional_parameters: List[str] = field(default_factory=list)
    path_parameters: List[str] = field(default_factory=list)
    query_parameters: List[str] = field(default_factory=list)
    header_parameters: List[str] = field(default_factory=list)

    # Response information
    response_types: List[str] = field(default_factory=list)
    response_schemas: List[str] = field(default_factory=list)
    status_codes: List[int] = field(default_factory=list)
    response_descriptions: str = ""

    # Security and metadata
    security_requirements: List[str] = field(default_factory=list)
    security_scopes: List[str] = field(default_factory=list)
    security_schemes: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    deprecated: bool = False

    # Composite search fields
    searchable_text: str = ""
    keywords: List[str] = field(default_factory=list)
    resource_name: str = ""
    operation_type: str = ""

    # Additional metadata for search optimization
    content_types: List[str] = field(default_factory=list)
    has_request_body: bool = False
    has_examples: bool = False
    external_docs: str = ""


class EndpointDocumentProcessor:
    """Processes normalized endpoint data into comprehensive search documents.

    This class implements the document creation pipeline from Story 3.2,
    extracting and organizing all searchable content from endpoint data.
    """

    # REST operation patterns for classification
    OPERATION_PATTERNS = {
        "create": ["post", "put"],
        "read": ["get"],
        "update": ["put", "patch"],
        "delete": ["delete"],
        "list": ["get"],
        "search": ["get", "post"],
    }

    # Common stop words to exclude from keywords
    STOP_WORDS = {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "for",
        "from",
        "in",
        "is",
        "it",
        "of",
        "on",
        "that",
        "the",
        "to",
        "will",
        "with",
    }

    def __init__(self):
        """Initialize the endpoint document processor."""
        pass

    async def create_endpoint_document(
        self, endpoint_data: Dict[str, Any]
    ) -> EndpointSearchDocument:
        """Create comprehensive search document from endpoint data.

        Args:
            endpoint_data: Normalized endpoint data from database

        Returns:
            EndpointSearchDocument: Complete search document ready for indexing

        Raises:
            ValueError: If required endpoint data is missing
        """
        if not endpoint_data.get("id") or not endpoint_data.get("path"):
            raise ValueError("Endpoint data must include 'id' and 'path' fields")

        # Extract path information
        path_segments = self.extract_path_segments(endpoint_data["path"])
        path_parameters = self.extract_path_parameters(endpoint_data["path"])

        # Process parameters comprehensively
        parameter_info = await self.process_parameters(
            endpoint_data.get("parameters", [])
        )

        # Merge path parameters from URL with processed parameters
        for path_param in path_parameters:
            if path_param not in parameter_info["path_params"]:
                parameter_info["path_params"].append(path_param)
                parameter_info["names"].append(path_param)

        # Extract response information
        response_info = await self.extract_response_info(
            endpoint_data.get("responses", {})
        )

        # Process security requirements
        security_info = await self.extract_security_info(
            endpoint_data.get("security", [])
        )

        # Extract operation details
        operation_info = self.extract_operation_info(endpoint_data)

        # Determine resource name and operation type
        resource_name = self.extract_resource_name(endpoint_data["path"])
        operation_type = self.classify_operation_type(
            endpoint_data.get("method", "").lower(),
            endpoint_data["path"],
            operation_info["summary"],
        )

        # Create composite searchable text
        searchable_text = self.create_composite_text(
            endpoint_data, parameter_info, response_info, operation_info
        )

        # Extract keywords
        keywords = self.extract_keywords(searchable_text, endpoint_data)

        return EndpointSearchDocument(
            endpoint_id=str(endpoint_data["id"]),
            endpoint_path=endpoint_data["path"],
            http_method=endpoint_data.get("method", "").upper(),
            operation_summary=operation_info["summary"],
            operation_description=operation_info["description"],
            operation_id=operation_info["operation_id"],
            path_segments=path_segments,
            parameter_names=parameter_info["names"],
            parameter_descriptions=parameter_info["descriptions"],
            parameter_types=parameter_info["types"],
            required_parameters=parameter_info["required"],
            optional_parameters=parameter_info["optional"],
            path_parameters=parameter_info["path_params"],
            query_parameters=parameter_info["query_params"],
            header_parameters=parameter_info["header_params"],
            response_types=response_info["content_types"],
            response_schemas=response_info["schema_names"],
            status_codes=response_info["status_codes"],
            response_descriptions=response_info["descriptions"],
            security_requirements=security_info["schemes"],
            security_scopes=security_info["scopes"],
            security_schemes=security_info["scheme_types"],
            tags=endpoint_data.get("tags", []),
            deprecated=endpoint_data.get("deprecated", False),
            searchable_text=searchable_text,
            keywords=keywords,
            resource_name=resource_name,
            operation_type=operation_type,
            content_types=response_info["content_types"],
            has_request_body=bool(endpoint_data.get("requestBody")),
            has_examples=self.has_examples(endpoint_data),
            external_docs=operation_info.get("external_docs", ""),
        )

    def extract_path_segments(self, path: str) -> List[str]:
        """Extract searchable path segments.

        Args:
            path: API endpoint path

        Returns:
            List[str]: Clean path segments for hierarchical search
        """
        # Remove path parameters: /users/{id}/posts → /users/posts
        clean_path = re.sub(r"\{[^}]+\}", "", path)
        clean_path = re.sub(r":[^/]+", "", clean_path)  # Handle :id style parameters

        # Split and filter segments
        segments = [
            seg.lower()
            for seg in clean_path.split("/")
            if seg and seg not in ("api", "v1", "v2", "v3")
        ]

        return segments

    def extract_path_parameters(self, path: str) -> List[str]:
        """Extract path parameter names.

        Args:
            path: API endpoint path

        Returns:
            List[str]: Path parameter names
        """
        # Handle both {param} and :param styles
        curly_params = re.findall(r"\{([^}]+)\}", path)
        colon_params = re.findall(r":([^/]+)", path)

        return curly_params + colon_params

    async def process_parameters(
        self, parameters: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Process all parameter types comprehensively.

        Args:
            parameters: List of parameter objects

        Returns:
            Dict[str, Any]: Organized parameter information
        """
        names = []
        descriptions = []
        types = []
        required = []
        optional = []
        path_params = []
        query_params = []
        header_params = []
        cookie_params = []

        for param in parameters:
            if not isinstance(param, dict):
                continue

            name = param.get("name", "")
            description = param.get("description", "")
            param_type = param.get("type", param.get("schema", {}).get("type", ""))
            param_in = param.get("in", "")
            is_required = param.get("required", False)

            if name:
                names.append(name)
                if description:
                    descriptions.append(f"{name}: {description}")
                if param_type:
                    types.append(param_type)

                # Categorize by requirement and location
                if is_required:
                    required.append(name)
                else:
                    optional.append(name)

                # Categorize by location
                if param_in == "path":
                    path_params.append(name)
                elif param_in == "query":
                    query_params.append(name)
                elif param_in == "header":
                    header_params.append(name)
                elif param_in == "cookie":
                    cookie_params.append(name)

        return {
            "names": names,
            "descriptions": " ".join(descriptions),
            "types": list(set(types)),
            "required": required,
            "optional": optional,
            "path_params": path_params,
            "query_params": query_params,
            "header_params": header_params,
            "cookie_params": cookie_params,
        }

    async def extract_response_info(self, responses: Dict[str, Any]) -> Dict[str, Any]:
        """Extract comprehensive response information.

        Args:
            responses: Response definitions from endpoint

        Returns:
            Dict[str, Any]: Organized response information
        """
        content_types = set()
        schema_names = []
        status_codes = []
        descriptions = []

        for status_code, response_data in responses.items():
            if not isinstance(response_data, dict):
                continue

            # Parse status code
            try:
                status_codes.append(int(status_code))
            except (ValueError, TypeError):
                pass

            # Extract description
            description = response_data.get("description", "")
            if description:
                descriptions.append(f"{status_code}: {description}")

            # Extract content types and schemas
            content = response_data.get("content", {})
            for content_type, schema_info in content.items():
                content_types.add(content_type)

                schema = schema_info.get("schema", {})
                if isinstance(schema, dict):
                    # Extract schema reference
                    ref = schema.get("$ref")
                    if ref:
                        # Extract schema name from reference
                        schema_name = ref.split("/")[-1]
                        schema_names.append(schema_name)

                    # Extract array item schema
                    items = schema.get("items", {})
                    if isinstance(items, dict) and items.get("$ref"):
                        schema_name = items["$ref"].split("/")[-1]
                        schema_names.append(schema_name)

        return {
            "content_types": list(content_types),
            "schema_names": list(set(schema_names)),
            "status_codes": sorted(status_codes),
            "descriptions": " ".join(descriptions),
        }

    async def extract_security_info(
        self, security: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Extract and organize security requirements.

        Args:
            security: Security requirements from endpoint

        Returns:
            Dict[str, Any]: Organized security information
        """
        schemes = []
        scopes = []
        scheme_types = set()

        for sec_req in security:
            if not isinstance(sec_req, dict):
                continue

            for scheme_name, scheme_scopes in sec_req.items():
                schemes.append(scheme_name)

                # Determine scheme type from name patterns
                scheme_lower = scheme_name.lower()
                if "bearer" in scheme_lower or "jwt" in scheme_lower:
                    scheme_types.add("bearer")
                elif "api" in scheme_lower and "key" in scheme_lower:
                    scheme_types.add("apiKey")
                elif "oauth" in scheme_lower:
                    scheme_types.add("oauth2")
                elif "openid" in scheme_lower:
                    scheme_types.add("openIdConnect")
                else:
                    scheme_types.add("unknown")

                # Add scopes if they exist
                if isinstance(scheme_scopes, list):
                    scopes.extend(scheme_scopes)

        return {
            "schemes": list(set(schemes)),
            "scopes": list(set(scopes)),
            "scheme_types": list(scheme_types),
        }

    def extract_operation_info(self, endpoint_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract operation-level information.

        Args:
            endpoint_data: Endpoint data

        Returns:
            Dict[str, Any]: Operation information
        """
        return {
            "summary": endpoint_data.get("summary", ""),
            "description": endpoint_data.get("description", ""),
            "operation_id": endpoint_data.get(
                "operationId", endpoint_data.get("operation_id", "")
            ),
            "external_docs": endpoint_data.get("externalDocs", {}).get("url", ""),
        }

    def extract_resource_name(self, path: str) -> str:
        """Extract the primary resource name from the path.

        Args:
            path: API endpoint path

        Returns:
            str: Primary resource name
        """
        segments = self.extract_path_segments(path)

        # Find the first meaningful segment that looks like a resource
        for segment in segments:
            if len(segment) > 2 and not segment.isdigit():
                return segment

        return segments[0] if segments else ""

    def classify_operation_type(self, method: str, path: str, summary: str) -> str:
        """Classify the operation type based on method, path, and summary.

        Args:
            method: HTTP method
            path: API endpoint path
            summary: Operation summary

        Returns:
            str: Operation type classification
        """
        method_lower = method.lower()
        summary_lower = summary.lower()
        path_lower = path.lower()

        # Check for specific patterns in summary
        if any(word in summary_lower for word in ["create", "add", "new"]):
            return "create"
        elif any(
            word in summary_lower for word in ["update", "modify", "change", "edit"]
        ):
            return "update"
        elif any(word in summary_lower for word in ["delete", "remove"]):
            return "delete"
        elif any(word in summary_lower for word in ["search", "find", "query"]):
            return "search"
        elif any(word in summary_lower for word in ["list", "get all"]):
            return "list"

        # Check path patterns
        if "{" in path_lower or ":" in path_lower:
            # Has path parameters, likely operating on specific resource
            if method_lower == "get":
                return "read"
            elif method_lower in ["put", "patch"]:
                return "update"
            elif method_lower == "delete":
                return "delete"
        else:
            # No path parameters, likely collection operation
            if method_lower == "get":
                return "list"
            elif method_lower == "post":
                return "create"

        # Fallback to method-based classification
        for operation, methods in self.OPERATION_PATTERNS.items():
            if method_lower in methods:
                return operation

        return "unknown"

    def create_composite_text(
        self,
        endpoint_data: Dict[str, Any],
        parameter_info: Dict[str, Any],
        response_info: Dict[str, Any],
        operation_info: Dict[str, Any],
    ) -> str:
        """Create comprehensive searchable text combining all endpoint aspects.

        Args:
            endpoint_data: Raw endpoint data
            parameter_info: Processed parameter information
            response_info: Processed response information
            operation_info: Operation information

        Returns:
            str: Combined searchable text
        """
        text_components = [
            operation_info.get("summary", ""),
            operation_info.get("description", ""),
            parameter_info.get("descriptions", ""),
            response_info.get("descriptions", ""),
            " ".join(endpoint_data.get("tags", [])),
            operation_info.get("operation_id", ""),
        ]

        # Add path segments as text
        path_segments = self.extract_path_segments(endpoint_data["path"])
        text_components.append(" ".join(path_segments))

        # Clean and combine
        cleaned_components = [
            comp.strip() for comp in text_components if comp and comp.strip()
        ]
        return " ".join(cleaned_components)

    def extract_keywords(
        self, searchable_text: str, endpoint_data: Dict[str, Any]
    ) -> List[str]:
        """Extract relevant keywords from searchable text and endpoint data.

        Args:
            searchable_text: Combined searchable text
            endpoint_data: Raw endpoint data

        Returns:
            List[str]: Extracted keywords
        """
        keywords = set()

        # Extract from text using simple tokenization
        words = re.findall(r"\b[a-zA-Z]{3,}\b", searchable_text.lower())
        keywords.update(word for word in words if word not in self.STOP_WORDS)

        # Add path segments if path exists
        path = endpoint_data.get("path")
        if path:
            path_segments = self.extract_path_segments(path)
            keywords.update(path_segments)

        # Add HTTP method
        method = endpoint_data.get("method", "").lower()
        if method:
            keywords.add(method)

        # Add tags
        tags = endpoint_data.get("tags", [])
        keywords.update(tag.lower() for tag in tags if isinstance(tag, str))

        # Add operation ID components
        operation_id = endpoint_data.get(
            "operationId", endpoint_data.get("operation_id", "")
        )
        if operation_id:
            # Split camelCase and snake_case
            words = re.sub(r"([a-z])([A-Z])", r"\1 \2", operation_id)
            words = words.replace("_", " ").replace("-", " ")
            keywords.update(word.lower() for word in words.split() if len(word) > 2)

        return sorted(list(keywords))

    def has_examples(self, endpoint_data: Dict[str, Any]) -> bool:
        """Check if endpoint has examples in parameters or responses.

        Args:
            endpoint_data: Endpoint data

        Returns:
            bool: True if examples are present
        """
        # Check parameter examples
        parameters = endpoint_data.get("parameters", [])
        for param in parameters:
            if isinstance(param, dict) and param.get("example"):
                return True

        # Check request body examples
        request_body = endpoint_data.get("requestBody", {})
        if isinstance(request_body, dict):
            content = request_body.get("content", {})
            for content_type, schema_info in content.items():
                if schema_info.get("example") or schema_info.get("examples"):
                    return True

        # Check response examples
        responses = endpoint_data.get("responses", {})
        for response in responses.values():
            if isinstance(response, dict):
                content = response.get("content", {})
                for content_type, schema_info in content.items():
                    if schema_info.get("example") or schema_info.get("examples"):
                        return True

        return False
