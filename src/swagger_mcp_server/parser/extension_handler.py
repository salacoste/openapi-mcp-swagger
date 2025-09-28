"""Extension and vendor property handling for OpenAPI documents."""

import re
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from swagger_mcp_server.config.logging import get_logger

logger = get_logger(__name__)


class ExtensionHandler:
    """Handles OpenAPI extensions and vendor-specific properties."""

    def __init__(self):
        self.logger = get_logger(__name__)

        # Known extension patterns
        self.known_extensions = {
            "x-amazon-apigateway-",
            "x-aws-",
            "x-azure-",
            "x-google-",
            "x-swagger-",
            "x-redoc-",
            "x-code-samples",
            "x-examples",
            "x-internal",
            "x-deprecated",
            "x-rate-limit",
            "x-throttling-",
            "x-auth-",
            "x-security-",
            "x-pagination-",
            "x-response-",
            "x-nullable",
            "x-omitempty",
            "x-go-",
            "x-java-",
            "x-python-",
            "x-javascript-",
        }

        # Extension categories
        self.extension_categories = {
            "documentation": [
                "x-code-samples",
                "x-examples",
                "x-summary",
                "x-description",
                "x-redoc-",
                "x-swagger-",
            ],
            "vendor": [
                "x-amazon-",
                "x-aws-",
                "x-azure-",
                "x-google-",
                "x-microsoft-",
            ],
            "language": [
                "x-go-",
                "x-java-",
                "x-python-",
                "x-javascript-",
                "x-csharp-",
            ],
            "behavior": [
                "x-nullable",
                "x-omitempty",
                "x-internal",
                "x-deprecated",
            ],
            "security": [
                "x-auth-",
                "x-security-",
                "x-rate-limit",
                "x-throttling-",
            ],
            "pagination": [
                "x-pagination-",
                "x-limit-",
                "x-offset-",
                "x-cursor-",
            ],
        }

    def extract_extensions(self, obj: Dict[str, Any]) -> Dict[str, Any]:
        """Extract all extension properties from an object.

        Args:
            obj: Object to extract extensions from

        Returns:
            Dictionary of extension properties
        """
        extensions = {}

        if not isinstance(obj, dict):
            return extensions

        for key, value in obj.items():
            if isinstance(key, str) and key.startswith("x-"):
                extensions[key] = value

        return extensions

    def categorize_extensions(
        self, extensions: Dict[str, Any]
    ) -> Dict[str, Dict[str, Any]]:
        """Categorize extensions by their purpose.

        Args:
            extensions: Dictionary of extension properties

        Returns:
            Dictionary with extensions grouped by category
        """
        categorized = defaultdict(dict)

        for ext_key, ext_value in extensions.items():
            category = self._determine_extension_category(ext_key)
            categorized[category][ext_key] = ext_value

        return dict(categorized)

    def _determine_extension_category(self, extension_key: str) -> str:
        """Determine the category of an extension.

        Args:
            extension_key: Extension property name

        Returns:
            Category name
        """
        ext_lower = extension_key.lower()

        for category, patterns in self.extension_categories.items():
            for pattern in patterns:
                if ext_lower.startswith(pattern.lower()):
                    return category

        return "custom"

    def validate_extensions(self, extensions: Dict[str, Any]) -> List[str]:
        """Validate extension properties for common issues.

        Args:
            extensions: Dictionary of extension properties

        Returns:
            List of validation warnings
        """
        warnings = []

        for ext_key, ext_value in extensions.items():
            # Check extension naming
            if not ext_key.startswith("x-"):
                warnings.append(f"Extension property should start with 'x-': {ext_key}")
                continue

            # Check for invalid characters in extension names
            if not re.match(r"^x-[a-zA-Z0-9\-_\.]+$", ext_key):
                warnings.append(
                    f"Extension name contains invalid characters: {ext_key}"
                )

            # Check for excessively long extension names
            if len(ext_key) > 64:
                warnings.append(f"Extension name is too long (>64 chars): {ext_key}")

            # Check for null values
            if ext_value is None:
                warnings.append(f"Extension has null value: {ext_key}")

            # Check for very large extension values
            if isinstance(ext_value, str) and len(ext_value) > 10000:
                warnings.append(f"Extension value is very large (>10KB): {ext_key}")

        return warnings

    def normalize_vendor_extensions(
        self, extensions: Dict[str, Any], vendor_context: Optional[str] = None
    ) -> Dict[str, Any]:
        """Normalize vendor-specific extensions.

        Args:
            extensions: Raw extension properties
            vendor_context: Optional vendor context for normalization

        Returns:
            Normalized extension properties
        """
        normalized = {}

        for ext_key, ext_value in extensions.items():
            # Normalize AWS API Gateway extensions
            if ext_key.startswith("x-amazon-apigateway-"):
                normalized_value = self._normalize_aws_extension(ext_key, ext_value)
                normalized[ext_key] = normalized_value

            # Normalize Azure extensions
            elif ext_key.startswith("x-azure-"):
                normalized_value = self._normalize_azure_extension(ext_key, ext_value)
                normalized[ext_key] = normalized_value

            # Normalize Google Cloud extensions
            elif ext_key.startswith("x-google-"):
                normalized_value = self._normalize_google_extension(ext_key, ext_value)
                normalized[ext_key] = normalized_value

            # Normalize documentation extensions
            elif ext_key in ["x-code-samples", "x-examples"]:
                normalized_value = self._normalize_documentation_extension(
                    ext_key, ext_value
                )
                normalized[ext_key] = normalized_value

            # Keep other extensions as-is
            else:
                normalized[ext_key] = ext_value

        return normalized

    def _normalize_aws_extension(self, key: str, value: Any) -> Any:
        """Normalize AWS API Gateway extension."""
        if key == "x-amazon-apigateway-integration":
            if isinstance(value, dict):
                # Ensure required fields are present
                normalized = {
                    "type": value.get("type", "aws_proxy"),
                    "httpMethod": value.get("httpMethod", "POST"),
                    "uri": value.get("uri", ""),
                }
                # Copy other fields
                for k, v in value.items():
                    if k not in normalized:
                        normalized[k] = v
                return normalized

        elif key == "x-amazon-apigateway-auth":
            if isinstance(value, dict):
                return {
                    "type": value.get("type", "AWS_IAM"),
                    **{k: v for k, v in value.items() if k != "type"},
                }

        return value

    def _normalize_azure_extension(self, key: str, value: Any) -> Any:
        """Normalize Azure-specific extension."""
        if key == "x-azure-api-management":
            if isinstance(value, dict):
                return {
                    "policy": value.get("policy", ""),
                    "subscription": value.get("subscription", True),
                    **{
                        k: v
                        for k, v in value.items()
                        if k not in ["policy", "subscription"]
                    },
                }

        return value

    def _normalize_google_extension(self, key: str, value: Any) -> Any:
        """Normalize Google Cloud extension."""
        if key == "x-google-backend":
            if isinstance(value, dict):
                return {
                    "address": value.get("address", ""),
                    "deadline": value.get("deadline", 30.0),
                    **{
                        k: v
                        for k, v in value.items()
                        if k not in ["address", "deadline"]
                    },
                }

        return value

    def _normalize_documentation_extension(self, key: str, value: Any) -> Any:
        """Normalize documentation extension."""
        if key == "x-code-samples":
            if isinstance(value, list):
                normalized_samples = []
                for sample in value:
                    if isinstance(sample, dict):
                        normalized_sample = {
                            "lang": sample.get("lang", "shell"),
                            "source": sample.get("source", ""),
                            "label": sample.get("label", sample.get("lang", "Example")),
                        }
                        normalized_samples.append(normalized_sample)
                return normalized_samples

        elif key == "x-examples":
            if isinstance(value, dict):
                # Ensure examples have proper structure
                normalized_examples = {}
                for example_name, example_data in value.items():
                    if isinstance(example_data, dict):
                        normalized_examples[example_name] = {
                            "summary": example_data.get("summary", example_name),
                            "value": example_data.get("value"),
                            "description": example_data.get("description", ""),
                        }
                    else:
                        # Simple value example
                        normalized_examples[example_name] = {
                            "summary": example_name,
                            "value": example_data,
                            "description": "",
                        }
                return normalized_examples

        return value

    def merge_extensions(
        self,
        base_extensions: Dict[str, Any],
        override_extensions: Dict[str, Any],
        strategy: str = "override",
    ) -> Dict[str, Any]:
        """Merge extension dictionaries.

        Args:
            base_extensions: Base extension properties
            override_extensions: Override extension properties
            strategy: Merge strategy ('override', 'merge', 'combine')

        Returns:
            Merged extension properties
        """
        if strategy == "override":
            # Override strategy: override values take precedence
            merged = base_extensions.copy()
            merged.update(override_extensions)
            return merged

        elif strategy == "merge":
            # Merge strategy: recursively merge objects
            merged = base_extensions.copy()
            for key, value in override_extensions.items():
                if (
                    key in merged
                    and isinstance(merged[key], dict)
                    and isinstance(value, dict)
                ):
                    merged[key] = self._deep_merge_dict(merged[key], value)
                else:
                    merged[key] = value
            return merged

        elif strategy == "combine":
            # Combine strategy: combine lists, merge objects
            merged = base_extensions.copy()
            for key, value in override_extensions.items():
                if key in merged:
                    if isinstance(merged[key], list) and isinstance(value, list):
                        merged[key] = merged[key] + value
                    elif isinstance(merged[key], dict) and isinstance(value, dict):
                        merged[key] = self._deep_merge_dict(merged[key], value)
                    else:
                        merged[key] = value
                else:
                    merged[key] = value
            return merged

        else:
            raise ValueError(f"Unknown merge strategy: {strategy}")

    def _deep_merge_dict(
        self, base: Dict[str, Any], override: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Recursively merge two dictionaries."""
        merged = base.copy()
        for key, value in override.items():
            if (
                key in merged
                and isinstance(merged[key], dict)
                and isinstance(value, dict)
            ):
                merged[key] = self._deep_merge_dict(merged[key], value)
            else:
                merged[key] = value
        return merged

    def extract_searchable_content(self, extensions: Dict[str, Any]) -> List[str]:
        """Extract searchable text content from extensions.

        Args:
            extensions: Extension properties

        Returns:
            List of searchable text strings
        """
        searchable_content = []

        for ext_key, ext_value in extensions.items():
            # Extract text from documentation extensions
            if ext_key in ["x-summary", "x-description"]:
                if isinstance(ext_value, str):
                    searchable_content.append(ext_value)

            elif ext_key == "x-code-samples":
                if isinstance(ext_value, list):
                    for sample in ext_value:
                        if isinstance(sample, dict):
                            # Add language and label
                            lang = sample.get("lang", "")
                            label = sample.get("label", "")
                            if lang:
                                searchable_content.append(lang)
                            if label:
                                searchable_content.append(label)

            elif ext_key == "x-examples":
                if isinstance(ext_value, dict):
                    for example_name, example_data in ext_value.items():
                        searchable_content.append(example_name)
                        if isinstance(example_data, dict):
                            summary = example_data.get("summary", "")
                            description = example_data.get("description", "")
                            if summary:
                                searchable_content.append(summary)
                            if description:
                                searchable_content.append(description)

            # Extract vendor-specific searchable content
            elif ext_key.startswith("x-") and isinstance(ext_value, str):
                # Include string extension values in search
                searchable_content.append(ext_value)

        return [content.strip() for content in searchable_content if content.strip()]

    def get_extension_statistics(
        self, all_extensions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Generate statistics about extension usage.

        Args:
            all_extensions: List of extension dictionaries

        Returns:
            Dictionary with extension statistics
        """
        stats = {
            "total_objects_with_extensions": 0,
            "unique_extensions": set(),
            "extension_frequency": defaultdict(int),
            "categories": defaultdict(int),
            "vendor_distribution": defaultdict(int),
            "average_extensions_per_object": 0.0,
            "most_common_extensions": [],
            "total_extension_properties": 0,
        }

        total_extension_count = 0

        for extensions in all_extensions:
            if extensions:
                stats["total_objects_with_extensions"] += 1
                extension_count = len(extensions)
                total_extension_count += extension_count

                for ext_key in extensions.keys():
                    stats["unique_extensions"].add(ext_key)
                    stats["extension_frequency"][ext_key] += 1

                    # Categorize
                    category = self._determine_extension_category(ext_key)
                    stats["categories"][category] += 1

                    # Vendor distribution
                    vendor = self._determine_vendor(ext_key)
                    if vendor:
                        stats["vendor_distribution"][vendor] += 1

        # Calculate averages and convert sets
        if stats["total_objects_with_extensions"] > 0:
            stats["average_extensions_per_object"] = (
                total_extension_count / stats["total_objects_with_extensions"]
            )

        stats["total_extension_properties"] = total_extension_count
        stats["unique_extensions"] = len(stats["unique_extensions"])

        # Most common extensions
        stats["most_common_extensions"] = sorted(
            stats["extension_frequency"].items(),
            key=lambda x: x[1],
            reverse=True,
        )[:10]

        # Convert defaultdicts to regular dicts
        stats["extension_frequency"] = dict(stats["extension_frequency"])
        stats["categories"] = dict(stats["categories"])
        stats["vendor_distribution"] = dict(stats["vendor_distribution"])

        return stats

    def _determine_vendor(self, extension_key: str) -> Optional[str]:
        """Determine the vendor from an extension key."""
        ext_lower = extension_key.lower()

        vendor_prefixes = {
            "x-amazon-": "Amazon",
            "x-aws-": "AWS",
            "x-azure-": "Microsoft Azure",
            "x-google-": "Google",
            "x-microsoft-": "Microsoft",
            "x-swagger-": "Swagger",
            "x-redoc-": "Redoc",
        }

        for prefix, vendor in vendor_prefixes.items():
            if ext_lower.startswith(prefix):
                return vendor

        return None
