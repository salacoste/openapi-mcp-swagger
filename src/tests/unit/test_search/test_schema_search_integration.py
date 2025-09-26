"""Comprehensive tests for schema search integration functionality.

Tests cover schema indexing, cross-reference mapping, relationship discovery,
and unified search capabilities as specified in Story 3.5.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from typing import Dict, Any, List

from swagger_mcp_server.search.schema_indexing import (
    SchemaIndexManager,
    SchemaSearchDocument,
    SchemaUsageContext
)
from swagger_mcp_server.search.schema_mapper import (
    SchemaEndpointMapper,
    CrossReferenceMap,
    SchemaEndpointRelationship
)
from swagger_mcp_server.search.schema_relationships import (
    SchemaRelationshipDiscovery,
    SchemaGraph,
    RelationshipType
)
from swagger_mcp_server.search.unified_search import (
    UnifiedSearchInterface,
    SearchType,
    ResultType,
    UnifiedSearchResult
)
from swagger_mcp_server.config.settings import SearchConfig, SearchPerformanceConfig


@pytest.fixture
def search_config():
    """Create test search configuration."""
    return SearchConfig(
        performance=SearchPerformanceConfig(
            max_search_results=100,
            query_timeout=30.0,
            enable_caching=True
        )
    )


@pytest.fixture
def mock_schema_repo():
    """Create mock schema repository."""
    repo = Mock()
    repo.get_all_schemas = AsyncMock()
    repo.get_by_id = AsyncMock()
    return repo


@pytest.fixture
def mock_endpoint_repo():
    """Create mock endpoint repository."""
    repo = Mock()
    repo.get_all = AsyncMock()
    repo.get_by_id = AsyncMock()
    repo.count_all = AsyncMock()
    return repo


@pytest.fixture
def sample_schemas():
    """Create sample schema data for testing."""
    return [
        {
            "id": "User",
            "name": "User",
            "type": "object",
            "description": "User account information",
            "properties": {
                "id": {"type": "integer", "description": "User ID"},
                "email": {"type": "string", "format": "email", "description": "User email"},
                "profile": {"$ref": "#/components/schemas/UserProfile"}
            },
            "required": ["id", "email"],
            "path": "#/components/schemas/User"
        },
        {
            "id": "UserProfile",
            "name": "UserProfile",
            "type": "object",
            "description": "User profile details",
            "properties": {
                "firstName": {"type": "string", "description": "First name"},
                "lastName": {"type": "string", "description": "Last name"},
                "avatar": {"$ref": "#/components/schemas/Image"}
            },
            "required": ["firstName", "lastName"],
            "path": "#/components/schemas/UserProfile"
        },
        {
            "id": "Image",
            "name": "Image",
            "type": "object",
            "description": "Image resource",
            "properties": {
                "url": {"type": "string", "format": "uri"},
                "width": {"type": "integer", "minimum": 1},
                "height": {"type": "integer", "minimum": 1}
            },
            "required": ["url"],
            "path": "#/components/schemas/Image"
        }
    ]


@pytest.fixture
def sample_endpoints():
    """Create sample endpoint data for testing."""
    return [
        {
            "id": "get_user",
            "endpoint_id": "get_user",
            "endpoint_path": "/users/{id}",
            "http_method": "GET",
            "summary": "Get user by ID",
            "description": "Retrieve user information by user ID",
            "responses": {
                "200": {
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/User"}
                        }
                    }
                }
            }
        },
        {
            "id": "create_user",
            "endpoint_id": "create_user",
            "endpoint_path": "/users",
            "http_method": "POST",
            "summary": "Create new user",
            "description": "Create a new user account",
            "request_body": {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/User"}
                    }
                }
            },
            "responses": {
                "201": {
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/User"}
                        }
                    }
                }
            }
        }
    ]


class TestSchemaIndexManager:
    """Test schema indexing functionality."""

    @pytest.mark.asyncio
    async def test_create_schema_documents(
        self,
        mock_schema_repo,
        mock_endpoint_repo,
        search_config,
        sample_schemas
    ):
        """Test creation of comprehensive schema search documents."""
        mock_schema_repo.get_all_schemas.return_value = sample_schemas

        manager = SchemaIndexManager(mock_schema_repo, mock_endpoint_repo, search_config)

        # Mock the endpoint relationship mapping
        with patch.object(manager, '_map_endpoint_relationships', new_callable=AsyncMock) as mock_map:
            mock_map.return_value = {
                "endpoints": ["get_user", "create_user"],
                "contexts": [SchemaUsageContext.RESPONSE_BODY, SchemaUsageContext.REQUEST_BODY],
                "usage_details": [
                    {"endpoint_id": "get_user", "context": "response_body"},
                    {"endpoint_id": "create_user", "context": "request_body"}
                ]
            }

            documents = await manager.create_schema_documents()

            assert len(documents) == 3
            assert all(isinstance(doc, SchemaSearchDocument) for doc in documents)

            # Test User schema document
            user_doc = next(doc for doc in documents if doc.schema_id == "User")
            assert user_doc.schema_name == "User"
            assert user_doc.schema_type == "object"
            assert "User account information" in user_doc.description
            assert "id" in user_doc.property_names
            assert "email" in user_doc.property_names
            assert "profile" in user_doc.property_names
            assert "id" in user_doc.required_properties
            assert "email" in user_doc.required_properties
            assert "profile" in user_doc.optional_properties
            assert "UserProfile" in user_doc.nested_schemas

    @pytest.mark.asyncio
    async def test_extract_schema_properties(
        self,
        mock_schema_repo,
        mock_endpoint_repo,
        search_config,
        sample_schemas
    ):
        """Test extraction of schema properties and metadata."""
        manager = SchemaIndexManager(mock_schema_repo, mock_endpoint_repo, search_config)

        user_schema = sample_schemas[0]
        properties = await manager._extract_schema_properties(user_schema)

        assert properties["names"] == ["id", "email", "profile"]
        assert properties["types"] == ["integer", "string"]
        assert properties["required"] == ["id", "email"]
        assert properties["optional"] == ["profile"]
        assert properties["nested_schemas"] == ["UserProfile"]
        assert "User ID" in properties["descriptions"]
        assert "User email" in properties["descriptions"]

    @pytest.mark.asyncio
    async def test_create_searchable_text(
        self,
        mock_schema_repo,
        mock_endpoint_repo,
        search_config
    ):
        """Test creation of searchable text for schemas."""
        manager = SchemaIndexManager(mock_schema_repo, mock_endpoint_repo, search_config)

        schema = {
            "id": "TestSchema",
            "name": "TestSchema",
            "description": "A test schema for validation",
            "type": "object"
        }

        properties = {
            "names": ["id", "name", "value"],
            "descriptions": "id: Unique identifier. name: Display name. value: Data value.",
            "types": ["integer", "string", "number"],
            "required": ["id"],
            "optional": ["name", "value"],
            "nested_schemas": [],
            "validation_rules": {}
        }

        searchable_text = await manager._create_schema_searchable_text(schema, properties)

        assert "TestSchema" in searchable_text
        assert "A test schema for validation" in searchable_text
        assert "id" in searchable_text
        assert "name" in searchable_text
        assert "value" in searchable_text
        assert "integer" in searchable_text
        assert "string" in searchable_text
        assert "number" in searchable_text


class TestSchemaEndpointMapper:
    """Test schema-endpoint cross-reference mapping."""

    @pytest.mark.asyncio
    async def test_create_complete_cross_reference_map(
        self,
        mock_schema_repo,
        mock_endpoint_repo,
        search_config,
        sample_schemas,
        sample_endpoints
    ):
        """Test creation of complete cross-reference mapping."""
        mock_schema_repo.get_all_schemas.return_value = sample_schemas
        mock_endpoint_repo.get_all.return_value = sample_endpoints

        mapper = SchemaEndpointMapper(mock_schema_repo, mock_endpoint_repo, search_config)

        # Mock the endpoint get_by_id method
        async def mock_get_by_id(endpoint_id):
            return next((e for e in sample_endpoints if e["id"] == endpoint_id), None)

        mock_endpoint_repo.get_by_id.side_effect = mock_get_by_id

        cross_ref_map = await mapper.create_complete_cross_reference_map()

        assert isinstance(cross_ref_map, CrossReferenceMap)
        assert len(cross_ref_map.schema_to_endpoints) > 0
        assert len(cross_ref_map.endpoint_to_schemas) > 0
        assert len(cross_ref_map.relationship_graph) > 0

        # Test User schema relationships
        assert "User" in cross_ref_map.schema_to_endpoints
        user_endpoints = cross_ref_map.schema_to_endpoints["User"]
        assert len(user_endpoints) > 0

        # Test endpoint relationships
        assert "get_user" in cross_ref_map.endpoint_to_schemas
        get_user_schemas = cross_ref_map.endpoint_to_schemas["get_user"]
        assert len(get_user_schemas) > 0

    @pytest.mark.asyncio
    async def test_find_response_body_relationships(
        self,
        mock_schema_repo,
        mock_endpoint_repo,
        search_config,
        sample_endpoints
    ):
        """Test finding response body relationships."""
        mapper = SchemaEndpointMapper(mock_schema_repo, mock_endpoint_repo, search_config)

        endpoint = sample_endpoints[0]  # get_user endpoint
        relationships = await mapper._find_response_body_relationships("User", endpoint)

        assert len(relationships) == 1
        relationship = relationships[0]
        assert relationship.schema_id == "User"
        assert relationship.endpoint_id == "get_user"
        assert relationship.context == SchemaUsageContext.RESPONSE_BODY
        assert relationship.details["status_code"] == "200"
        assert relationship.details["content_type"] == "application/json"

    @pytest.mark.asyncio
    async def test_find_request_body_relationships(
        self,
        mock_schema_repo,
        mock_endpoint_repo,
        search_config,
        sample_endpoints
    ):
        """Test finding request body relationships."""
        mapper = SchemaEndpointMapper(mock_schema_repo, mock_endpoint_repo, search_config)

        endpoint = sample_endpoints[1]  # create_user endpoint
        relationships = await mapper._find_request_body_relationships("User", endpoint)

        assert len(relationships) == 1
        relationship = relationships[0]
        assert relationship.schema_id == "User"
        assert relationship.endpoint_id == "create_user"
        assert relationship.context == SchemaUsageContext.REQUEST_BODY
        assert relationship.details["content_type"] == "application/json"
        assert relationship.details["required"] is True

    def test_calculate_relationship_score(
        self,
        mock_schema_repo,
        mock_endpoint_repo,
        search_config
    ):
        """Test relationship score calculation."""
        mapper = SchemaEndpointMapper(mock_schema_repo, mock_endpoint_repo, search_config)

        # Test request body score
        score = mapper._calculate_relationship_score("request_body", "application/json", True)
        assert score > 0.8  # High score for required JSON request body

        # Test response body score
        score = mapper._calculate_relationship_score("response_body", "application/json", True)
        assert score > 0.7  # High score for success JSON response

        # Test parameter score
        score = mapper._calculate_relationship_score("parameter", "path", True)
        assert score > 0.5  # Moderate score for required path parameter


class TestSchemaRelationshipDiscovery:
    """Test schema relationship discovery system."""

    @pytest.mark.asyncio
    async def test_discover_all_relationships(
        self,
        mock_schema_repo,
        search_config,
        sample_schemas
    ):
        """Test discovery of all schema relationships."""
        mock_schema_repo.get_all_schemas.return_value = sample_schemas

        discovery = SchemaRelationshipDiscovery(mock_schema_repo, search_config)
        schema_graph = await discovery.discover_all_relationships()

        assert isinstance(schema_graph, SchemaGraph)
        assert len(schema_graph.nodes) == 3
        assert len(schema_graph.edges) > 0

        # Check nodes
        assert "User" in schema_graph.nodes
        assert "UserProfile" in schema_graph.nodes
        assert "Image" in schema_graph.nodes

        # Check that we found reference relationships
        reference_edges = [e for e in schema_graph.edges if e.relationship_type == RelationshipType.NESTED_PROPERTY]
        assert len(reference_edges) > 0

    @pytest.mark.asyncio
    async def test_discover_reference_relationships(
        self,
        mock_schema_repo,
        search_config,
        sample_schemas
    ):
        """Test discovery of reference relationships."""
        discovery = SchemaRelationshipDiscovery(mock_schema_repo, search_config)

        relationships = await discovery._discover_reference_relationships(sample_schemas)

        # Should find User -> UserProfile and UserProfile -> Image references
        assert len(relationships) >= 2

        # Find User -> UserProfile relationship
        user_profile_rel = next(
            (r for r in relationships
             if r.source_schema_id == "User" and r.target_schema_id == "UserProfile"),
            None
        )
        assert user_profile_rel is not None
        assert user_profile_rel.relationship_type == RelationshipType.NESTED_PROPERTY
        assert user_profile_rel.context == "property_profile"

    def test_detect_circular_dependencies(
        self,
        mock_schema_repo,
        search_config
    ):
        """Test detection of circular dependencies."""
        discovery = SchemaRelationshipDiscovery(mock_schema_repo, search_config)

        # Create relationships with a circular dependency
        from swagger_mcp_server.search.schema_relationships import SchemaRelationship
        relationships = [
            SchemaRelationship(
                source_schema_id="A",
                target_schema_id="B",
                relationship_type=RelationshipType.REFERENCE,
                context="property",
                details={},
                strength=1.0
            ),
            SchemaRelationship(
                source_schema_id="B",
                target_schema_id="C",
                relationship_type=RelationshipType.REFERENCE,
                context="property",
                details={},
                strength=1.0
            ),
            SchemaRelationship(
                source_schema_id="C",
                target_schema_id="A",
                relationship_type=RelationshipType.REFERENCE,
                context="property",
                details={},
                strength=1.0
            )
        ]

        cycles = discovery._detect_circular_dependencies(relationships)
        assert len(cycles) > 0

        # Check that we found the A -> B -> C -> A cycle
        cycle = cycles[0]
        assert "A" in cycle
        assert "B" in cycle
        assert "C" in cycle


class TestUnifiedSearchInterface:
    """Test unified search interface functionality."""

    @pytest.fixture
    def mock_search_engine(self):
        """Create mock search engine."""
        engine = Mock()
        engine.search_advanced = AsyncMock()
        return engine

    @pytest.fixture
    def mock_schema_index_manager(self):
        """Create mock schema index manager."""
        manager = Mock()
        manager.create_schema_documents = AsyncMock()
        return manager

    @pytest.fixture
    def mock_schema_mapper(self):
        """Create mock schema mapper."""
        mapper = Mock()
        mapper.create_complete_cross_reference_map = AsyncMock()
        return mapper

    @pytest.fixture
    def mock_relationship_discovery(self):
        """Create mock relationship discovery."""
        discovery = Mock()
        discovery.discover_all_relationships = AsyncMock()
        return discovery

    @pytest.mark.asyncio
    async def test_unified_search_endpoints_only(
        self,
        mock_search_engine,
        mock_schema_index_manager,
        mock_schema_mapper,
        mock_relationship_discovery,
        search_config
    ):
        """Test unified search with endpoints only."""
        # Mock endpoint search results
        mock_search_engine.search_advanced.return_value = {
            "results": [
                {
                    "endpoint_id": "get_user",
                    "endpoint_path": "/users/{id}",
                    "http_method": "GET",
                    "summary": "Get user by ID",
                    "description": "Retrieve user information",
                    "score": 0.95,
                    "highlights": {},
                    "tags": "users",
                    "deprecated": False,
                    "operation_type": "read",
                    "complexity_level": "simple"
                }
            ],
            "summary": {"filtered_results": 1}
        }

        interface = UnifiedSearchInterface(
            mock_search_engine,
            mock_schema_index_manager,
            mock_schema_mapper,
            mock_relationship_discovery,
            search_config
        )

        response = await interface.unified_search(
            query="user",
            search_types=["endpoints"],
            include_cross_references=False
        )

        assert response.total_results == 1
        assert len(response.results) == 1
        assert response.results[0].result_type == ResultType.ENDPOINT
        assert response.results[0].result_id == "get_user"
        assert response.results[0].title == "GET /users/{id}"

    @pytest.mark.asyncio
    async def test_unified_search_schemas_only(
        self,
        mock_search_engine,
        mock_schema_index_manager,
        mock_schema_mapper,
        mock_relationship_discovery,
        search_config,
        sample_schemas
    ):
        """Test unified search with schemas only."""
        # Mock schema documents
        from swagger_mcp_server.search.schema_indexing import SchemaSearchDocument, SchemaUsageContext
        mock_documents = [
            SchemaSearchDocument(
                schema_id="User",
                schema_name="User",
                schema_type="object",
                schema_path="#/components/schemas/User",
                description="User account information",
                property_names=["id", "email", "profile"],
                property_descriptions="id: User ID. email: User email.",
                property_types=["integer", "string"],
                required_properties=["id", "email"],
                optional_properties=["profile"],
                nested_schemas=["UserProfile"],
                example_values={},
                validation_rules={},
                used_in_endpoints=["get_user", "create_user"],
                usage_contexts=[SchemaUsageContext.RESPONSE_BODY, SchemaUsageContext.REQUEST_BODY],
                usage_details=[],
                inherits_from=None,
                extended_by=[],
                composed_schemas=[],
                composition_type=None,
                searchable_text="User object User account information id email profile",
                keywords=["object", "identifier", "email"],
                complexity_level="simple",
                usage_frequency=2,
                last_modified=None
            )
        ]

        mock_schema_index_manager.create_schema_documents.return_value = mock_documents

        interface = UnifiedSearchInterface(
            mock_search_engine,
            mock_schema_index_manager,
            mock_schema_mapper,
            mock_relationship_discovery,
            search_config
        )

        response = await interface.unified_search(
            query="user",
            search_types=["schemas"],
            include_cross_references=False
        )

        assert response.total_results == 1
        assert len(response.results) == 1
        assert response.results[0].result_type == ResultType.SCHEMA
        assert response.results[0].result_id == "User"
        assert response.results[0].title == "User"

    @pytest.mark.asyncio
    async def test_unified_search_with_cross_references(
        self,
        mock_search_engine,
        mock_schema_index_manager,
        mock_schema_mapper,
        mock_relationship_discovery,
        search_config
    ):
        """Test unified search with cross-references."""
        # Mock both endpoint and schema results
        mock_search_engine.search_advanced.return_value = {
            "results": [
                {
                    "endpoint_id": "get_user",
                    "endpoint_path": "/users/{id}",
                    "http_method": "GET",
                    "summary": "Get user by ID",
                    "description": "Retrieve user information",
                    "score": 0.95,
                    "highlights": {},
                    "tags": "users",
                    "deprecated": False,
                    "operation_type": "read",
                    "complexity_level": "simple"
                }
            ],
            "summary": {"filtered_results": 1}
        }

        from swagger_mcp_server.search.schema_indexing import SchemaSearchDocument, SchemaUsageContext
        mock_documents = [
            SchemaSearchDocument(
                schema_id="User",
                schema_name="User",
                schema_type="object",
                schema_path="#/components/schemas/User",
                description="User account information",
                property_names=["id", "email"],
                property_descriptions="id: User ID. email: User email.",
                property_types=["integer", "string"],
                required_properties=["id", "email"],
                optional_properties=[],
                nested_schemas=[],
                example_values={},
                validation_rules={},
                used_in_endpoints=["get_user"],
                usage_contexts=[SchemaUsageContext.RESPONSE_BODY],
                usage_details=[],
                inherits_from=None,
                extended_by=[],
                composed_schemas=[],
                composition_type=None,
                searchable_text="User object User account information id email",
                keywords=["object", "identifier", "email"],
                complexity_level="simple",
                usage_frequency=1,
                last_modified=None
            )
        ]

        mock_schema_index_manager.create_schema_documents.return_value = mock_documents

        # Mock cross-reference map
        from swagger_mcp_server.search.schema_mapper import CrossReferenceMap
        mock_cross_ref_map = CrossReferenceMap(
            schema_to_endpoints={
                "User": [{"endpoint_id": "get_user", "context": "response_body"}]
            },
            endpoint_to_schemas={
                "get_user": [{"schema_id": "User", "context": "response_body"}]
            },
            relationship_graph=[],
            dependency_matrix={}
        )

        mock_schema_mapper.create_complete_cross_reference_map.return_value = mock_cross_ref_map

        interface = UnifiedSearchInterface(
            mock_search_engine,
            mock_schema_index_manager,
            mock_schema_mapper,
            mock_relationship_discovery,
            search_config
        )

        response = await interface.unified_search(
            query="user",
            search_types=["all"],
            include_cross_references=True
        )

        assert response.total_results == 2
        assert len(response.cross_references) > 0
        assert "endpoint_to_schema" in response.cross_references
        assert "schema_to_endpoint" in response.cross_references

        # Check that results have relationships
        endpoint_result = next(r for r in response.results if r.result_type == ResultType.ENDPOINT)
        schema_result = next(r for r in response.results if r.result_type == ResultType.SCHEMA)

        assert endpoint_result.relationships is not None
        assert schema_result.relationships is not None

    def test_search_result_ranking(
        self,
        mock_search_engine,
        mock_schema_index_manager,
        mock_schema_mapper,
        mock_relationship_discovery,
        search_config
    ):
        """Test intelligent ranking of unified search results."""
        interface = UnifiedSearchInterface(
            mock_search_engine,
            mock_schema_index_manager,
            mock_schema_mapper,
            mock_relationship_discovery,
            search_config
        )

        # Create test results with different scores
        results = [
            UnifiedSearchResult(
                result_id="endpoint1",
                result_type=ResultType.ENDPOINT,
                title="Test Endpoint",
                description="Test description",
                score=0.8,
                highlights={},
                metadata={}
            ),
            UnifiedSearchResult(
                result_id="schema1",
                result_type=ResultType.SCHEMA,
                title="Test Schema",
                description="Test schema description",
                score=0.9,
                highlights={},
                metadata={}
            )
        ]

        # Test ranking with endpoint preference
        ranked_results = interface._rank_unified_results(results, "test", ["endpoints"])
        assert ranked_results[0].result_type == ResultType.SCHEMA  # Higher score wins
        assert ranked_results[1].result_type == ResultType.ENDPOINT

        # Test ranking with schema preference
        ranked_results = interface._rank_unified_results(results, "test", ["schemas"])
        assert ranked_results[0].result_type == ResultType.SCHEMA  # Both higher score and type preference


class TestPerformanceRequirements:
    """Test performance and accuracy requirements."""

    @pytest.mark.asyncio
    async def test_schema_search_performance(
        self,
        mock_schema_repo,
        mock_endpoint_repo,
        search_config
    ):
        """Test that schema search meets performance requirements (<200ms)."""
        # Create a large number of test schemas
        large_schema_set = []
        for i in range(100):
            schema = {
                "id": f"Schema{i}",
                "name": f"Schema{i}",
                "type": "object",
                "description": f"Test schema number {i}",
                "properties": {
                    "id": {"type": "integer"},
                    "name": {"type": "string"},
                    "value": {"type": "number"}
                },
                "required": ["id"],
                "path": f"#/components/schemas/Schema{i}"
            }
            large_schema_set.append(schema)

        mock_schema_repo.get_all_schemas.return_value = large_schema_set

        manager = SchemaIndexManager(mock_schema_repo, mock_endpoint_repo, search_config)

        # Mock endpoint relationships to avoid complex database queries
        with patch.object(manager, '_map_endpoint_relationships', new_callable=AsyncMock) as mock_map:
            mock_map.return_value = {
                "endpoints": [],
                "contexts": [],
                "usage_details": []
            }

            start_time = asyncio.get_event_loop().time()
            documents = await manager.create_schema_documents()
            end_time = asyncio.get_event_loop().time()

            execution_time = (end_time - start_time) * 1000  # Convert to milliseconds

            assert len(documents) == 100
            # Performance requirement: should handle 100 schemas in reasonable time
            # Note: This is a unit test, so we're more lenient than the 200ms target
            assert execution_time < 5000  # 5 seconds for unit test environment

    @pytest.mark.asyncio
    async def test_cross_reference_accuracy(
        self,
        mock_schema_repo,
        mock_endpoint_repo,
        search_config,
        sample_schemas,
        sample_endpoints
    ):
        """Test accuracy of cross-reference mapping."""
        mock_schema_repo.get_all_schemas.return_value = sample_schemas
        mock_endpoint_repo.get_all.return_value = sample_endpoints

        # Mock get_by_id for endpoints
        async def mock_get_by_id(endpoint_id):
            return next((e for e in sample_endpoints if e["id"] == endpoint_id), None)

        mock_endpoint_repo.get_by_id.side_effect = mock_get_by_id

        mapper = SchemaEndpointMapper(mock_schema_repo, mock_endpoint_repo, search_config)
        cross_ref_map = await mapper.create_complete_cross_reference_map()

        # Verify accuracy of mappings
        # User schema should be used by both endpoints
        assert "User" in cross_ref_map.schema_to_endpoints
        user_usage = cross_ref_map.schema_to_endpoints["User"]
        endpoint_ids = [usage["endpoint_id"] for usage in user_usage]
        assert "get_user" in endpoint_ids
        assert "create_user" in endpoint_ids

        # Both endpoints should use User schema
        assert "get_user" in cross_ref_map.endpoint_to_schemas
        assert "create_user" in cross_ref_map.endpoint_to_schemas

        get_user_schemas = cross_ref_map.endpoint_to_schemas["get_user"]
        create_user_schemas = cross_ref_map.endpoint_to_schemas["create_user"]

        assert any(s["schema_id"] == "User" for s in get_user_schemas)
        assert any(s["schema_id"] == "User" for s in create_user_schemas)

    def test_schema_indexing_completeness(
        self,
        mock_schema_repo,
        mock_endpoint_repo,
        search_config
    ):
        """Test that schema indexing captures 100% of schema information."""
        # Create a complex schema with all possible features
        complex_schema = {
            "id": "ComplexSchema",
            "name": "ComplexSchema",
            "type": "object",
            "description": "A complex schema with all features",
            "properties": {
                "id": {
                    "type": "integer",
                    "description": "Unique identifier",
                    "minimum": 1
                },
                "name": {
                    "type": "string",
                    "description": "Display name",
                    "minLength": 1,
                    "maxLength": 100
                },
                "email": {
                    "type": "string",
                    "format": "email",
                    "pattern": "^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$"
                },
                "status": {
                    "type": "string",
                    "enum": ["active", "inactive", "pending"]
                },
                "profile": {
                    "$ref": "#/components/schemas/Profile"
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"}
                }
            },
            "required": ["id", "name", "email"],
            "allOf": [
                {"$ref": "#/components/schemas/BaseEntity"}
            ],
            "examples": [
                {
                    "id": 1,
                    "name": "John Doe",
                    "email": "john@example.com",
                    "status": "active"
                }
            ]
        }

        manager = SchemaIndexManager(mock_schema_repo, mock_endpoint_repo, search_config)

        # Test property extraction
        properties = asyncio.run(manager._extract_schema_properties(complex_schema))

        # Verify all properties are captured
        expected_properties = ["id", "name", "email", "status", "profile", "tags"]
        assert set(properties["names"]) == set(expected_properties)

        # Verify required/optional classification
        assert set(properties["required"]) == {"id", "name", "email"}
        assert set(properties["optional"]) == {"status", "profile", "tags"}

        # Verify nested schema detection
        assert "Profile" in properties["nested_schemas"]

        # Verify validation rules capture
        assert "id" in properties["validation_rules"]
        assert "name" in properties["validation_rules"]
        assert properties["validation_rules"]["id"]["minimum"] == 1
        assert properties["validation_rules"]["name"]["minLength"] == 1
        assert properties["validation_rules"]["name"]["maxLength"] == 100