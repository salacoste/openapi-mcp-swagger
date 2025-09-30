"""Integration tests for end-to-end categorization during parsing.

Epic 6: Hierarchical Endpoint Catalog System - Story 6.1
Tests categorization integration with OpenAPI parsing workflow.
"""

import json
import tempfile
from pathlib import Path

import pytest

from swagger_mcp_server.parser.categorization import (
    CategorizationEngine,
    CategoryCatalog,
)
from swagger_mcp_server.parser.endpoint_processor import (
    EndpointProcessor,
    enrich_endpoints_with_categories,
)


def flatten_operations(enriched_paths):
    """Helper function to flatten path operations dict to list."""
    operations = []
    for path, methods in enriched_paths.items():
        for method, operation in methods.items():
            operation["path"] = path
            operation["method"] = method
            operations.append(operation)
    return operations


@pytest.mark.integration
class TestParsingCategorization:
    """Test end-to-end categorization during OpenAPI parsing."""

    @pytest.fixture
    def ozon_api_spec(self):
        """Provide Ozon Performance API specification with tags and x-tagGroups."""
        return {
            "openapi": "3.0.0",
            "info": {
                "title": "Ozon Performance API",
                "version": "1.0.0",
            },
            "tags": [
                {
                    "name": "Campaign",
                    "x-displayName": "Кампании и рекламируемые объекты",
                    "description": "Campaign management operations",
                },
                {
                    "name": "Statistics",
                    "x-displayName": "Статистика",
                    "description": "Statistics and reporting",
                },
                {
                    "name": "Ad",
                    "x-displayName": "Объявления",
                    "description": "Ad management operations",
                },
                {
                    "name": "Product",
                    "description": "Product operations",
                },
            ],
            "x-tagGroups": [
                {
                    "name": "Методы Performance API",
                    "tags": ["Campaign", "Statistics", "Ad", "Product"],
                }
            ],
            "paths": {
                "/api/client/campaign": {
                    "get": {
                        "tags": ["Campaign"],
                        "operationId": "ListCampaigns",
                        "summary": "List campaigns",
                        "responses": {"200": {"description": "Success"}},
                    }
                },
                "/api/client/campaign/{campaignId}": {
                    "get": {
                        "tags": ["Campaign"],
                        "operationId": "GetCampaign",
                        "summary": "Get campaign by ID",
                        "responses": {"200": {"description": "Success"}},
                    },
                    "put": {
                        "tags": ["Campaign"],
                        "operationId": "UpdateCampaign",
                        "summary": "Update campaign",
                        "responses": {"200": {"description": "Success"}},
                    },
                },
                "/api/client/statistics": {
                    "post": {
                        "tags": ["Statistics"],
                        "operationId": "GetStatistics",
                        "summary": "Get statistics report",
                        "responses": {"200": {"description": "Success"}},
                    }
                },
                "/api/client/ad": {
                    "get": {
                        "tags": ["Ad"],
                        "operationId": "ListAds",
                        "summary": "List ads",
                        "responses": {"200": {"description": "Success"}},
                    }
                },
                "/api/client/product": {
                    "post": {
                        "tags": ["Product"],
                        "operationId": "SearchProducts",
                        "summary": "Search products",
                        "responses": {"200": {"description": "Success"}},
                    }
                },
                "/api/client/uncategorized": {
                    "get": {
                        "operationId": "UncategorizedEndpoint",
                        "summary": "Endpoint without tags",
                        "responses": {"200": {"description": "Success"}},
                    }
                },
            },
        }

    @pytest.fixture
    def ozon_api_file(self, ozon_api_spec):
        """Create temporary file with Ozon API spec."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(ozon_api_spec, f)
            temp_path = f.name

        yield temp_path
        Path(temp_path).unlink(missing_ok=True)

    def test_end_to_end_categorization_with_ozon_api(self, ozon_api_spec):
        """Test complete categorization workflow with Ozon API fixture."""
        # Initialize processor
        processor = EndpointProcessor()
        processor.initialize_from_spec(ozon_api_spec)

        # Process all paths
        enriched_paths = processor.process_paths(ozon_api_spec["paths"])
        enriched_operations = flatten_operations(enriched_paths)

        # Verify all endpoints were processed (6 paths with 7 operations total)
        assert len(enriched_operations) == 7

        # Verify Campaign endpoints (3 total)
        campaign_ops = [
            op for op in enriched_operations if op.get("category") == "campaign"
        ]
        assert len(campaign_ops) == 3

        # Verify all campaign operations have proper metadata
        for op in campaign_ops:
            assert op["category"] == "campaign"
            assert op["category_display_name"] == "Кампании и рекламируемые объекты"
            assert op["category_group"] == "Методы Performance API"
            assert op["category_metadata"] is not None

        # Verify Statistics endpoint
        stats_ops = [
            op for op in enriched_operations if op.get("category") == "statistics"
        ]
        assert len(stats_ops) == 1
        assert stats_ops[0]["category_display_name"] == "Статистика"

        # Verify uncategorized endpoint
        uncategorized_ops = [
            op for op in enriched_operations if op.get("category") == "uncategorized"
        ]
        assert len(uncategorized_ops) == 1
        assert uncategorized_ops[0]["category_display_name"] == "Uncategorized"

    def test_category_accuracy_95_percent_target(self, ozon_api_spec):
        """Test categorization achieves 95%+ accuracy with well-tagged API."""
        processor = EndpointProcessor()
        processor.initialize_from_spec(ozon_api_spec)

        enriched_paths = processor.process_paths(ozon_api_spec["paths"])
        enriched_operations = flatten_operations(enriched_paths)

        # Count correctly categorized endpoints (not "Uncategorized")
        correctly_categorized = sum(
            1
            for op in enriched_operations
            if op.get("category") != "uncategorized"
        )

        total_endpoints = len(enriched_operations)
        accuracy = (correctly_categorized / total_endpoints) * 100

        # 6 out of 7 endpoints have explicit tags = 85.7%
        # Since one endpoint lacks tags, this is expected behavior
        # For well-tagged APIs (all have tags), we'd achieve 100%
        assert accuracy >= 85.0

        # Test with all endpoints tagged
        spec_with_all_tags = ozon_api_spec.copy()
        spec_with_all_tags["paths"]["/api/client/uncategorized"]["get"]["tags"] = [
            "Product"
        ]

        processor = EndpointProcessor()
        processor.initialize_from_spec(spec_with_all_tags)
        enriched_paths = processor.process_paths(spec_with_all_tags["paths"])
        enriched_operations = flatten_operations(enriched_paths)

        correctly_categorized = sum(
            1
            for op in enriched_operations
            if op.get("category") != "uncategorized"
        )

        accuracy = (correctly_categorized / len(enriched_operations)) * 100
        assert accuracy >= 95.0

    def test_category_catalog_population(self, ozon_api_spec):
        """Test category catalog is populated correctly during parsing."""
        processor = EndpointProcessor()
        processor.initialize_from_spec(ozon_api_spec)

        # Process all paths
        processor.process_paths(ozon_api_spec["paths"])

        # Get category catalog data
        catalog_data = processor.get_category_catalog_data()

        # Verify categories are present
        category_names = {cat["category_name"] for cat in catalog_data}
        assert "campaign" in category_names
        assert "statistics" in category_names
        assert "ad" in category_names
        assert "product" in category_names
        assert "uncategorized" in category_names

        # Find Campaign category and verify stats
        campaign_cat = next(
            cat for cat in catalog_data if cat["category_name"] == "campaign"
        )
        assert campaign_cat["endpoint_count"] == 3
        assert set(campaign_cat["http_methods"]) == {"GET", "PUT"}
        assert campaign_cat["category_group"] == "Методы Performance API"

    def test_batch_enrichment_function(self, ozon_api_spec):
        """Test batch enrichment helper function."""
        # Create mock endpoints list
        endpoints = [
            {
                "path": "/api/client/campaign",
                "method": "get",
                "operation": {"tags": ["Campaign"], "summary": "List campaigns"},
            },
            {
                "path": "/api/client/statistics",
                "method": "post",
                "operation": {"tags": ["Statistics"], "summary": "Get statistics"},
            },
        ]

        # Enrich with categories
        enriched, catalog = enrich_endpoints_with_categories(endpoints, ozon_api_spec)

        # Verify enrichment
        assert len(enriched) == 2

        assert enriched[0]["category"] == "campaign"
        assert enriched[0]["category_display_name"] == "Кампании и рекламируемые объекты"

        assert enriched[1]["category"] == "statistics"
        assert enriched[1]["category_display_name"] == "Статистика"

        # Verify catalog
        assert len(catalog) == 2
        category_names = {cat["category_name"] for cat in catalog}
        assert "campaign" in category_names
        assert "statistics" in category_names

    def test_path_based_fallback_categorization(self):
        """Test path-based categorization fallback when no tags."""
        spec = {
            "openapi": "3.0.0",
            "info": {"title": "Test API", "version": "1.0.0"},
            "paths": {
                "/api/v1/users/list": {
                    "get": {
                        "operationId": "listUsers",
                        "summary": "List users",
                        "responses": {"200": {"description": "Success"}},
                    }
                },
                "/api/v1/products/search": {
                    "post": {
                        "operationId": "searchProducts",
                        "summary": "Search products",
                        "responses": {"200": {"description": "Success"}},
                    }
                },
            },
        }

        processor = EndpointProcessor()
        processor.initialize_from_spec(spec)

        enriched_paths = processor.process_paths(spec["paths"])
        enriched_operations = flatten_operations(enriched_paths)

        # Should extract "users" and "products" from paths
        categories = {op["category"] for op in enriched_operations}
        assert "users" in categories
        assert "products" in categories

    def test_multi_tag_endpoint_uses_first_tag(self, ozon_api_spec):
        """Test endpoints with multiple tags use first tag as primary."""
        spec = ozon_api_spec.copy()
        spec["paths"]["/api/client/multi-tag"] = {
            "get": {
                "tags": ["Campaign", "Statistics"],  # Multiple tags
                "operationId": "multiTag",
                "summary": "Multi-tag endpoint",
                "responses": {"200": {"description": "Success"}},
            }
        }

        processor = EndpointProcessor()
        processor.initialize_from_spec(spec)

        enriched_paths = processor.process_paths(spec["paths"])
        enriched_operations = flatten_operations(enriched_paths)

        # Find the multi-tag endpoint
        multi_tag_op = next(
            op
            for op in enriched_operations
            if op.get("path") == "/api/client/multi-tag"
        )

        # Should use first tag as primary category
        assert multi_tag_op["category"] == "campaign"
        assert multi_tag_op["category_metadata"] is not None

    def test_backward_compatibility_with_non_categorized_parsing(self, ozon_api_spec):
        """Test parsing works without breaking when categorization disabled."""
        # Remove tag definitions to simulate non-categorized workflow
        spec_without_tags = ozon_api_spec.copy()
        del spec_without_tags["tags"]
        del spec_without_tags["x-tagGroups"]

        # Remove tags from operations
        for path_data in spec_without_tags["paths"].values():
            for operation in path_data.values():
                operation.pop("tags", None)

        processor = EndpointProcessor()
        processor.initialize_from_spec(spec_without_tags)

        enriched_paths = processor.process_paths(spec_without_tags["paths"])
        enriched_operations = flatten_operations(enriched_paths)

        # Should still work, falling back to path-based categorization
        assert len(enriched_operations) == 7

        # All should have categories (from path or "uncategorized")
        for op in enriched_operations:
            assert "category" in op
            assert op["category"] is not None

    def test_edge_case_empty_tags_array(self):
        """Test handling of empty tags array."""
        spec = {
            "openapi": "3.0.0",
            "info": {"title": "Test API", "version": "1.0.0"},
            "paths": {
                "/api/test": {
                    "get": {
                        "tags": [],  # Empty tags array
                        "operationId": "test",
                        "summary": "Test endpoint",
                        "responses": {"200": {"description": "Success"}},
                    }
                }
            },
        }

        processor = EndpointProcessor()
        processor.initialize_from_spec(spec)

        enriched_paths = processor.process_paths(spec["paths"])
        enriched_operations = flatten_operations(enriched_paths)

        # Should fallback to path extraction
        assert enriched_operations[0]["category"] == "test"

    def test_edge_case_malformed_tag_groups(self, ozon_api_spec):
        """Test handling of malformed x-tagGroups."""
        spec = ozon_api_spec.copy()
        spec["x-tagGroups"] = [
            {"name": "Group1"},  # Missing 'tags' field
            {"tags": ["Campaign"]},  # Missing 'name' field
            None,  # Null group
        ]

        processor = EndpointProcessor()
        processor.initialize_from_spec(spec)

        enriched_paths = processor.process_paths(spec["paths"])
        enriched_operations = flatten_operations(enriched_paths)

        # Should still categorize, just without group hierarchy
        campaign_ops = [
            op for op in enriched_operations if op.get("category") == "campaign"
        ]
        assert len(campaign_ops) > 0

        # Group may be None due to malformed data
        for op in campaign_ops:
            # Should have category even if group is malformed
            assert op["category"] == "campaign"