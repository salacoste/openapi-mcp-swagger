"""Tests for the OpenAPI Schema Normalization Engine components."""

import pytest
from unittest.mock import Mock, patch
from typing import Dict, Any, List

from swagger_mcp_server.parser.models import (
    NormalizedEndpoint, NormalizedSchema, NormalizedSecurityScheme,
    HttpMethod, ParameterLocation, SecuritySchemeType
)
from swagger_mcp_server.parser.endpoint_normalizer import EndpointNormalizer
from swagger_mcp_server.parser.schema_processor import SchemaProcessor
from swagger_mcp_server.parser.security_mapper import SecurityMapper
from swagger_mcp_server.parser.extension_handler import ExtensionHandler
from swagger_mcp_server.parser.consistency_validator import ConsistencyValidator
from swagger_mcp_server.parser.search_optimizer import SearchOptimizer, SearchableDocument


class TestEndpointNormalizer:
    """Tests for EndpointNormalizer class."""

    def setup_method(self):
        self.normalizer = EndpointNormalizer()

    def test_normalize_simple_endpoint(self):
        """Test normalization of a simple GET endpoint."""
        paths_data = {
            '/users': {
                'get': {
                    'operationId': 'getUsers',
                    'summary': 'Get all users',
                    'description': 'Retrieve a list of all users',
                    'tags': ['users'],
                    'parameters': [
                        {
                            'name': 'limit',
                            'in': 'query',
                            'schema': {'type': 'integer'},
                            'required': False
                        }
                    ],
                    'responses': {
                        '200': {
                            'description': 'Successful response',
                            'content': {
                                'application/json': {
                                    'schema': {'type': 'array'}
                                }
                            }
                        }
                    }
                }
            }
        }

        endpoints, errors, warnings = self.normalizer.normalize_endpoints(paths_data)

        assert len(endpoints) == 1
        assert len(errors) == 0
        assert len(warnings) == 0

        endpoint = endpoints[0]
        assert endpoint.path == '/users'
        assert endpoint.method == HttpMethod.GET
        assert endpoint.operation_id == 'getUsers'
        assert endpoint.summary == 'Get all users'
        assert endpoint.description == 'Retrieve a list of all users'
        assert endpoint.tags == ['users']
        assert len(endpoint.parameters) == 1
        assert len(endpoint.responses) == 1

    def test_normalize_endpoint_with_path_parameters(self):
        """Test normalization of endpoint with path parameters."""
        paths_data = {
            '/users/{userId}': {
                'parameters': [
                    {
                        'name': 'userId',
                        'in': 'path',
                        'required': True,
                        'schema': {'type': 'string'}
                    }
                ],
                'get': {
                    'operationId': 'getUserById',
                    'responses': {'200': {'description': 'User found'}}
                }
            }
        }

        endpoints, errors, warnings = self.normalizer.normalize_endpoints(paths_data)

        assert len(endpoints) == 1
        assert len(errors) == 0

        endpoint = endpoints[0]
        assert len(endpoint.parameters) == 1
        param = endpoint.parameters[0]
        assert param.name == 'userId'
        assert param.location == ParameterLocation.PATH
        assert param.required is True

    def test_normalize_endpoint_with_request_body(self):
        """Test normalization of POST endpoint with request body."""
        paths_data = {
            '/users': {
                'post': {
                    'operationId': 'createUser',
                    'requestBody': {
                        'required': True,
                        'content': {
                            'application/json': {
                                'schema': {'$ref': '#/components/schemas/User'}
                            }
                        }
                    },
                    'responses': {
                        '201': {'description': 'User created'}
                    }
                }
            }
        }

        endpoints, errors, warnings = self.normalizer.normalize_endpoints(paths_data)

        assert len(endpoints) == 1
        endpoint = endpoints[0]
        assert endpoint.request_body is not None
        assert endpoint.request_body.required is True
        assert 'application/json' in endpoint.request_body.content

    def test_validate_path_parameters(self):
        """Test path parameter validation."""
        # Valid case
        errors = self.normalizer.validate_path_parameters(
            '/users/{userId}/posts/{postId}',
            [
                Mock(name='userId', location=ParameterLocation.PATH, required=True),
                Mock(name='postId', location=ParameterLocation.PATH, required=True)
            ]
        )
        assert len(errors) == 0

        # Missing parameter
        errors = self.normalizer.validate_path_parameters(
            '/users/{userId}/posts/{postId}',
            [Mock(name='userId', location=ParameterLocation.PATH, required=True)]
        )
        assert len(errors) == 1
        assert 'Missing path parameters' in errors[0]

    def test_get_endpoint_statistics(self):
        """Test endpoint statistics generation."""
        endpoints = [
            Mock(
                method=HttpMethod.GET, tags=['users'], parameters=[], deprecated=False,
                request_body=None, security=[], responses={'200': Mock()},
                schema_dependencies=set(['User']), security_dependencies=set()
            ),
            Mock(
                method=HttpMethod.POST, tags=['users'], parameters=[Mock()], deprecated=True,
                request_body=Mock(), security=[Mock()], responses={'201': Mock()},
                schema_dependencies=set(['User', 'CreateUser']), security_dependencies=set(['bearerAuth'])
            )
        ]

        stats = self.normalizer.get_endpoint_statistics(endpoints)

        assert stats['total_endpoints'] == 2
        assert stats['methods']['get'] == 1
        assert stats['methods']['post'] == 1
        assert stats['deprecated_count'] == 1
        assert stats['with_request_body'] == 1
        assert stats['with_security'] == 1


class TestSchemaProcessor:
    """Tests for SchemaProcessor class."""

    def setup_method(self):
        self.processor = SchemaProcessor()

    def test_process_simple_schema(self):
        """Test processing of simple schema definition."""
        components_data = {
            'schemas': {
                'User': {
                    'type': 'object',
                    'required': ['id', 'name'],
                    'properties': {
                        'id': {'type': 'string'},
                        'name': {'type': 'string'},
                        'email': {'type': 'string', 'format': 'email'}
                    }
                }
            }
        }

        schemas, errors, warnings = self.processor.process_schemas(components_data)

        assert len(schemas) == 1
        assert len(errors) == 0
        assert 'User' in schemas

        user_schema = schemas['User']
        assert user_schema.type == 'object'
        assert user_schema.required == ['id', 'name']
        assert len(user_schema.properties) == 3

    def test_process_schema_with_references(self):
        """Test processing of schema with $ref references."""
        components_data = {
            'schemas': {
                'User': {
                    'type': 'object',
                    'properties': {
                        'id': {'type': 'string'},
                        'address': {'$ref': '#/components/schemas/Address'}
                    }
                },
                'Address': {
                    'type': 'object',
                    'properties': {
                        'street': {'type': 'string'},
                        'city': {'type': 'string'}
                    }
                }
            }
        }

        schemas, errors, warnings = self.processor.process_schemas(components_data)

        assert len(schemas) == 2
        assert len(errors) == 0

        user_schema = schemas['User']
        assert 'Address' in user_schema.schema_dependencies

    def test_detect_circular_dependencies(self):
        """Test detection of circular schema dependencies."""
        components_data = {
            'schemas': {
                'Node': {
                    'type': 'object',
                    'properties': {
                        'value': {'type': 'string'},
                        'children': {
                            'type': 'array',
                            'items': {'$ref': '#/components/schemas/Node'}
                        }
                    }
                }
            }
        }

        schemas, errors, warnings = self.processor.process_schemas(components_data)

        # Should handle self-reference without error
        assert len(schemas) == 1
        assert 'Node' in schemas
        node_schema = schemas['Node']
        assert 'Node' in node_schema.schema_dependencies

    def test_resolve_all_references(self):
        """Test comprehensive reference resolution."""
        full_document = {
            'components': {
                'schemas': {
                    'User': {'type': 'object'},
                    'Post': {'type': 'object'}
                }
            }
        }

        # Test various reference formats
        test_cases = [
            ('#/components/schemas/User', 'User'),
            ('User', 'User'),
            ('#/components/schemas/NonExistent', None),
        ]

        for ref, expected in test_cases:
            result = self.processor.resolve_reference(ref, full_document)
            if expected:
                assert result is not None
            else:
                assert result is None


class TestSecurityMapper:
    """Tests for SecurityMapper class."""

    def setup_method(self):
        self.mapper = SecurityMapper()

    def test_normalize_api_key_scheme(self):
        """Test normalization of API key security scheme."""
        components_data = {
            'securitySchemes': {
                'apiKey': {
                    'type': 'apiKey',
                    'name': 'X-API-Key',
                    'in': 'header',
                    'description': 'API key authentication'
                }
            }
        }

        schemes, errors, warnings = self.mapper.normalize_security_schemes(components_data)

        assert len(schemes) == 1
        assert len(errors) == 0
        assert 'apiKey' in schemes

        scheme = schemes['apiKey']
        assert scheme.type == SecuritySchemeType.API_KEY
        assert scheme.api_key_name == 'X-API-Key'

    def test_normalize_oauth2_scheme(self):
        """Test normalization of OAuth2 security scheme."""
        components_data = {
            'securitySchemes': {
                'oauth2': {
                    'type': 'oauth2',
                    'flows': {
                        'authorizationCode': {
                            'authorizationUrl': 'https://example.com/oauth/authorize',
                            'tokenUrl': 'https://example.com/oauth/token',
                            'scopes': {
                                'read': 'Read access',
                                'write': 'Write access'
                            }
                        }
                    }
                }
            }
        }

        schemes, errors, warnings = self.mapper.normalize_security_schemes(components_data)

        assert len(schemes) == 1
        scheme = schemes['oauth2']
        assert scheme.type == SecuritySchemeType.OAUTH2
        assert scheme.oauth2_flows is not None
        assert len(scheme.oauth2_flows) == 1

    def test_validate_security_consistency(self):
        """Test security consistency validation."""
        schemes = {
            'bearerAuth': Mock(type=SecuritySchemeType.HTTP, oauth2_flows=None),
            'oauth2': Mock(
                type=SecuritySchemeType.OAUTH2,
                oauth2_flows={'authorization_code': Mock(scopes={'read': 'Read access'})}
            )
        }

        requirements = [
            [Mock(scheme_id='bearerAuth', scopes=[])],
            [Mock(scheme_id='nonexistent', scopes=[])]  # Invalid reference
        ]

        errors = self.mapper.validate_security_consistency(schemes, requirements)
        assert len(errors) == 1
        assert 'nonexistent' in errors[0]


class TestExtensionHandler:
    """Tests for ExtensionHandler class."""

    def setup_method(self):
        self.handler = ExtensionHandler()

    def test_extract_extensions(self):
        """Test extension extraction."""
        obj = {
            'name': 'test',
            'x-custom': 'value',
            'x-vendor-specific': {'key': 'value'},
            'regular': 'property'
        }

        extensions = self.handler.extract_extensions(obj)

        assert len(extensions) == 2
        assert 'x-custom' in extensions
        assert 'x-vendor-specific' in extensions
        assert 'regular' not in extensions

    def test_categorize_extensions(self):
        """Test extension categorization."""
        extensions = {
            'x-code-samples': [],
            'x-amazon-apigateway-integration': {},
            'x-go-type': 'string',
            'x-custom': 'value'
        }

        categorized = self.handler.categorize_extensions(extensions)

        assert 'documentation' in categorized
        assert 'vendor' in categorized
        assert 'language' in categorized
        assert 'custom' in categorized

    def test_validate_extensions(self):
        """Test extension validation."""
        extensions = {
            'x-valid': 'good',
            'invalid-name': 'bad',  # Should start with x-
            'x-': 'too-short',  # Invalid name
            'x-null': None,  # Null value
        }

        warnings = self.handler.validate_extensions(extensions)
        assert len(warnings) >= 3  # Should have warnings for invalid cases

    def test_normalize_aws_extensions(self):
        """Test AWS extension normalization."""
        extensions = {
            'x-amazon-apigateway-integration': {
                'type': 'aws',
                'uri': 'arn:aws:lambda:region:account:function:name'
            }
        }

        normalized = self.handler.normalize_vendor_extensions(extensions)
        assert 'x-amazon-apigateway-integration' in normalized
        integration = normalized['x-amazon-apigateway-integration']
        assert integration['type'] == 'aws'
        assert 'httpMethod' in integration  # Should add default


class TestConsistencyValidator:
    """Tests for ConsistencyValidator class."""

    def setup_method(self):
        self.validator = ConsistencyValidator()

    def test_validate_reference_consistency(self):
        """Test reference consistency validation."""
        endpoints = [
            Mock(
                method=HttpMethod.GET, path='/users',
                schema_dependencies={'User', 'NonExistent'},
                security_dependencies={'bearerAuth'},
                parameters=[]
            )
        ]

        schemas = {'User': Mock()}
        security_schemes = {'bearerAuth': Mock()}

        errors, warnings = self.validator.validate_reference_consistency(
            endpoints, schemas, security_schemes
        )

        assert len(errors) == 1
        assert 'NonExistent' in errors[0]

    def test_validate_path_parameter_consistency(self):
        """Test path parameter consistency validation."""
        endpoints = [
            Mock(
                method=HttpMethod.GET, path='/users/{userId}',
                parameters=[
                    Mock(name='userId', location=ParameterLocation.PATH, required=True)
                ]
            ),
            Mock(
                method=HttpMethod.POST, path='/users/{userId}',
                parameters=[]  # Missing path parameter
            )
        ]

        errors, warnings = self.validator.validate_path_parameter_consistency(endpoints)
        assert len(errors) >= 1

    def test_generate_consistency_report(self):
        """Test consistency report generation."""
        endpoints = [Mock(
            method=HttpMethod.GET, path='/users',
            schema_dependencies=set(), security_dependencies=set(),
            parameters=[], security=[], responses={}
        )]
        schemas = {}
        security_schemes = {}

        report = self.validator.generate_consistency_report(
            endpoints, schemas, security_schemes
        )

        assert 'summary' in report
        assert 'errors' in report
        assert 'warnings' in report
        assert 'statistics' in report
        assert 'recommendations' in report
        assert report['summary']['endpoints_analyzed'] == 1


class TestSearchOptimizer:
    """Tests for SearchOptimizer class."""

    def setup_method(self):
        self.optimizer = SearchOptimizer()

    def test_create_endpoint_document(self):
        """Test creation of searchable endpoint document."""
        endpoint = Mock(
            method=HttpMethod.POST, path='/users',
            operation_id='createUser',
            summary='Create user',
            description='Create a new user',
            tags=['users'],
            parameters=[
                Mock(name='limit', description='Limit results', schema_type='integer')
            ],
            request_body=Mock(content={'application/json': {}}),
            responses={
                '201': Mock(description='Created', content={'application/json': {}})
            },
            deprecated=False
        )

        doc = self.optimizer._create_endpoint_document(endpoint)

        assert doc.type == 'endpoint'
        assert doc.title == 'POST /users'
        assert 'createUser' in doc.content
        assert 'Create user' in doc.content
        assert 'post' in doc.tags
        assert 'users' in doc.tags
        assert doc.boost == 1.2  # Higher boost for endpoints with operation_id

    def test_create_schema_document(self):
        """Test creation of searchable schema document."""
        schema = Mock(
            title='User Schema',
            description='User object definition',
            type='object',
            format=None,
            properties={'id': {}, 'name': {}, 'email': {}},
            required=['id', 'name'],
            example={'id': '1', 'name': 'John'},
            deprecated=False
        )

        doc = self.optimizer._create_schema_document('User', schema)

        assert doc.type == 'schema'
        assert doc.title == 'User Schema'
        assert 'User' in doc.content
        assert 'object' in doc.content
        assert 'property id' in doc.content
        assert len(doc.metadata['required_count']) == 2

    def test_tokenize_content(self):
        """Test content tokenization."""
        content = "Create a new user with email@example.com and user-id_123"
        tokens = self.optimizer._tokenize_content(content)

        assert 'create' in tokens
        assert 'new' not in tokens  # Stop word
        assert 'user' in tokens
        assert 'email' in tokens
        assert 'example' in tokens
        assert 'com' in tokens
        assert 'user' in tokens
        assert 'id' in tokens
        assert '123' in tokens

    def test_optimize_for_search(self):
        """Test full search optimization."""
        endpoints = [
            Mock(
                method=HttpMethod.GET, path='/users',
                operation_id='getUsers', summary='Get users',
                description='Get all users', tags=['users'],
                parameters=[], request_body=None, responses={},
                deprecated=False
            )
        ]

        schemas = {
            'User': Mock(
                title='User', description='User object',
                type='object', format=None, properties={'id': {}},
                required=['id'], example=None, deprecated=False
            )
        }

        security_schemes = {
            'bearerAuth': Mock(
                type=Mock(value='http'), description='Bearer token',
                api_key_name=None, http_scheme='bearer',
                bearer_format='JWT', oauth2_flows=None,
                openid_connect_url=None
            )
        }

        search_index = self.optimizer.optimize_for_search(
            endpoints, schemas, security_schemes
        )

        assert search_index.total_documents == 3
        assert len(search_index.vocabulary) > 0
        assert len(search_index.documents) == 3

    def test_get_search_statistics(self):
        """Test search statistics generation."""
        documents = [
            SearchableDocument('1', 'endpoint', 'GET /users', 'get users endpoint', ['get'], {}, 1.0),
            SearchableDocument('2', 'schema', 'User', 'user schema object', ['user'], {}, 1.0)
        ]

        # Mock search index
        search_index = Mock(
            documents=documents,
            total_documents=2,
            vocabulary={'get', 'users', 'endpoint', 'user', 'schema', 'object'},
            document_frequencies={'users': 2, 'endpoint': 1, 'schema': 1},
            document_lengths={'1': 10, '2': 8}
        )

        stats = self.optimizer.get_search_statistics(search_index)

        assert stats['total_documents'] == 2
        assert stats['vocabulary_size'] == 6
        assert stats['document_types']['endpoint'] == 1
        assert stats['document_types']['schema'] == 1


class TestIntegrationTests:
    """Integration tests for the complete normalization pipeline."""

    def setup_method(self):
        self.endpoint_normalizer = EndpointNormalizer()
        self.schema_processor = SchemaProcessor()
        self.security_mapper = SecurityMapper()
        self.extension_handler = ExtensionHandler()
        self.consistency_validator = ConsistencyValidator()
        self.search_optimizer = SearchOptimizer()

    def test_complete_normalization_pipeline(self):
        """Test the complete normalization pipeline with sample OpenAPI data."""
        # Sample OpenAPI document
        openapi_data = {
            'openapi': '3.0.0',
            'info': {'title': 'Test API', 'version': '1.0.0'},
            'paths': {
                '/users': {
                    'get': {
                        'operationId': 'getUsers',
                        'summary': 'Get users',
                        'tags': ['users'],
                        'parameters': [
                            {
                                'name': 'limit',
                                'in': 'query',
                                'schema': {'type': 'integer'}
                            }
                        ],
                        'responses': {
                            '200': {
                                'description': 'Success',
                                'content': {
                                    'application/json': {
                                        'schema': {
                                            'type': 'array',
                                            'items': {'$ref': '#/components/schemas/User'}
                                        }
                                    }
                                }
                            }
                        },
                        'security': [{'bearerAuth': []}]
                    }
                },
                '/users/{userId}': {
                    'parameters': [
                        {
                            'name': 'userId',
                            'in': 'path',
                            'required': True,
                            'schema': {'type': 'string'}
                        }
                    ],
                    'get': {
                        'operationId': 'getUserById',
                        'summary': 'Get user by ID',
                        'tags': ['users'],
                        'responses': {
                            '200': {
                                'description': 'Success',
                                'content': {
                                    'application/json': {
                                        'schema': {'$ref': '#/components/schemas/User'}
                                    }
                                }
                            },
                            '404': {'description': 'Not found'}
                        }
                    }
                }
            },
            'components': {
                'schemas': {
                    'User': {
                        'type': 'object',
                        'required': ['id', 'name'],
                        'properties': {
                            'id': {'type': 'string'},
                            'name': {'type': 'string'},
                            'email': {'type': 'string', 'format': 'email'},
                            'x-internal': True
                        },
                        'x-table': 'users'
                    }
                },
                'securitySchemes': {
                    'bearerAuth': {
                        'type': 'http',
                        'scheme': 'bearer',
                        'bearerFormat': 'JWT'
                    }
                }
            }
        }

        # Step 1: Normalize endpoints
        endpoints, endpoint_errors, endpoint_warnings = self.endpoint_normalizer.normalize_endpoints(
            openapi_data['paths']
        )

        assert len(endpoints) == 2
        assert len(endpoint_errors) == 0

        # Step 2: Process schemas
        schemas, schema_errors, schema_warnings = self.schema_processor.process_schemas(
            openapi_data['components'], openapi_data
        )

        assert len(schemas) == 1
        assert len(schema_errors) == 0
        assert 'User' in schemas

        # Step 3: Map security schemes
        security_schemes, security_errors, security_warnings = self.security_mapper.normalize_security_schemes(
            openapi_data['components']
        )

        assert len(security_schemes) == 1
        assert len(security_errors) == 0
        assert 'bearerAuth' in security_schemes

        # Step 4: Validate consistency
        consistency_errors, consistency_warnings = self.consistency_validator.validate_full_consistency(
            endpoints, schemas, security_schemes
        )

        # Should have minimal consistency issues with well-formed data
        assert len(consistency_errors) == 0

        # Step 5: Optimize for search
        search_index = self.search_optimizer.optimize_for_search(
            endpoints, schemas, security_schemes
        )

        assert search_index.total_documents == 3  # 2 endpoints + 1 schema + 1 security scheme
        assert len(search_index.vocabulary) > 0

        # Step 6: Generate statistics
        endpoint_stats = self.endpoint_normalizer.get_endpoint_statistics(endpoints)
        search_stats = self.search_optimizer.get_search_statistics(search_index)

        assert endpoint_stats['total_endpoints'] == 2
        assert endpoint_stats['methods']['get'] == 2
        assert search_stats['total_documents'] == 3

    @pytest.mark.performance
    def test_performance_with_large_dataset(self):
        """Test performance with a larger dataset."""
        # Generate larger dataset
        paths_data = {}
        for i in range(100):
            paths_data[f'/resource{i}'] = {
                'get': {
                    'operationId': f'getResource{i}',
                    'summary': f'Get resource {i}',
                    'responses': {'200': {'description': 'Success'}}
                }
            }

        # Measure normalization performance
        import time
        start_time = time.time()

        endpoints, errors, warnings = self.endpoint_normalizer.normalize_endpoints(paths_data)

        end_time = time.time()
        normalization_time = end_time - start_time

        # Should process 100 endpoints quickly
        assert len(endpoints) == 100
        assert normalization_time < 1.0  # Should take less than 1 second

        # Test search optimization performance
        start_time = time.time()
        search_index = self.search_optimizer.optimize_for_search(endpoints, {}, {})
        end_time = time.time()
        optimization_time = end_time - start_time

        assert search_index.total_documents == 100
        assert optimization_time < 2.0  # Should take less than 2 seconds