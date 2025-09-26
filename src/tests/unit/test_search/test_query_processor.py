"""Unit tests for the query processor module.

Tests cover all aspects of advanced query processing including:
- Query preprocessing and normalization
- Boolean query parsing
- Field-specific query handling
- Fuzzy matching capabilities
- Query suggestions and auto-completion
"""

import pytest
import asyncio
from unittest.mock import Mock, patch
from typing import Set, List

from swagger_mcp_server.search.query_processor import (
    QueryProcessor,
    ProcessedQuery,
    QuerySuggestion
)
from swagger_mcp_server.config.settings import SearchConfig, SearchPerformanceConfig


@pytest.fixture
def search_config():
    """Create test search configuration."""
    return SearchConfig(
        performance=SearchPerformanceConfig(
            max_search_results=100,
            search_timeout=5.0,
            index_batch_size=1000
        )
    )


@pytest.fixture
def query_processor(search_config):
    """Create query processor instance for testing."""
    return QueryProcessor(search_config)


@pytest.fixture
def sample_available_terms():
    """Sample terms available in search index."""
    return {
        'user', 'customer', 'authentication', 'auth', 'bearer',
        'endpoint', 'users', 'create', 'update', 'delete',
        'get', 'post', 'put', 'patch', 'json', 'xml',
        'parameter', 'response', 'request', 'api', 'rest'
    }


class TestQueryPreprocessing:
    """Test query preprocessing and normalization."""

    @pytest.mark.asyncio
    async def test_basic_query_processing(self, query_processor):
        """Test basic query processing and normalization."""
        query = "user authentication"
        processed = await query_processor.process_query(query)

        assert processed.original_query == query
        assert processed.query_type == 'simple'
        assert len(processed.normalized_terms) >= 2
        assert any('user' in term for term in processed.normalized_terms)
        assert any('auth' in term for term in processed.normalized_terms)

    @pytest.mark.asyncio
    async def test_query_normalization_stemming(self, query_processor):
        """Test query normalization with stemming."""
        query = "users authentication endpoints"
        processed = await query_processor.process_query(query)

        # Check that stemming is applied (assuming NLTK is available)
        normalized = processed.normalized_terms
        assert len(normalized) > 0
        # Should handle plural forms
        if hasattr(query_processor, 'stemmer') and query_processor.stemmer:
            assert any('user' in term for term in normalized)

    @pytest.mark.asyncio
    async def test_empty_query_handling(self, query_processor):
        """Test handling of empty queries."""
        with pytest.raises(ValueError, match="Query cannot be empty"):
            await query_processor.process_query("")

        with pytest.raises(ValueError, match="Query cannot be empty"):
            await query_processor.process_query("   ")

    @pytest.mark.asyncio
    async def test_special_character_handling(self, query_processor):
        """Test handling of special characters in queries."""
        query = "user@example.com authentication!"
        processed = await query_processor.process_query(query)

        assert processed.original_query == query
        assert len(processed.normalized_terms) > 0

    @pytest.mark.asyncio
    async def test_case_insensitive_processing(self, query_processor):
        """Test case insensitive query processing."""
        queries = ["USER AUTH", "user auth", "User Auth"]
        results = []

        for query in queries:
            processed = await query_processor.process_query(query)
            results.append(processed.normalized_terms)

        # All should produce similar normalized terms
        assert len(set(str(r) for r in results)) <= 2  # Allow for minor variations


class TestBooleanQueryProcessing:
    """Test boolean query parsing and handling."""

    @pytest.mark.asyncio
    async def test_and_query_parsing(self, query_processor):
        """Test AND query parsing."""
        query = "user AND authentication"
        processed = await query_processor.process_query(query)

        assert processed.query_type == 'boolean'
        assert 'and' in processed.boolean_operators
        assert len(processed.boolean_operators['and']) == 2

    @pytest.mark.asyncio
    async def test_or_query_parsing(self, query_processor):
        """Test OR query parsing."""
        query = "user OR customer"
        processed = await query_processor.process_query(query)

        assert processed.query_type == 'boolean'
        assert 'or' in processed.boolean_operators
        assert len(processed.boolean_operators['or']) == 2

    @pytest.mark.asyncio
    async def test_not_query_parsing(self, query_processor):
        """Test NOT query parsing."""
        query = "authentication NOT oauth"
        processed = await query_processor.process_query(query)

        assert processed.query_type == 'boolean'
        assert 'not' in processed.boolean_operators
        assert 'oauth' in processed.boolean_operators['not']
        assert 'oauth' in processed.excluded_terms

    @pytest.mark.asyncio
    async def test_complex_boolean_query(self, query_processor):
        """Test complex boolean query with multiple operators."""
        query = "user AND authentication OR bearer NOT oauth"
        processed = await query_processor.process_query(query)

        assert processed.query_type == 'boolean'
        assert 'and' in processed.boolean_operators
        assert 'or' in processed.boolean_operators
        assert 'not' in processed.boolean_operators

    @pytest.mark.asyncio
    async def test_case_insensitive_boolean_operators(self, query_processor):
        """Test case insensitive boolean operator parsing."""
        queries = [
            "user AND auth",
            "user and auth",
            "user And auth"
        ]

        for query in queries:
            processed = await query_processor.process_query(query)
            assert processed.query_type == 'boolean'
            assert 'and' in processed.boolean_operators


class TestFieldSpecificQueries:
    """Test field-specific query parsing."""

    @pytest.mark.asyncio
    async def test_path_filter_parsing(self, query_processor):
        """Test path filter parsing."""
        query = "path:/users authentication"
        processed = await query_processor.process_query(query)

        assert processed.query_type == 'field_specific'
        assert 'path' in processed.field_filters
        assert processed.field_filters['path'] == '/users'

    @pytest.mark.asyncio
    async def test_method_filter_parsing(self, query_processor):
        """Test HTTP method filter parsing."""
        query = "method:GET user endpoints"
        processed = await query_processor.process_query(query)

        assert processed.query_type == 'field_specific'
        assert 'method' in processed.field_filters
        assert processed.field_filters['method'] == 'GET'

    @pytest.mark.asyncio
    async def test_multiple_field_filters(self, query_processor):
        """Test multiple field filters in one query."""
        query = "path:/users method:POST auth:bearer create user"
        processed = await query_processor.process_query(query)

        assert processed.query_type == 'field_specific'
        assert 'path' in processed.field_filters
        assert 'method' in processed.field_filters
        assert 'auth' in processed.field_filters
        assert processed.field_filters['path'] == '/users'
        assert processed.field_filters['method'] == 'POST'
        assert processed.field_filters['auth'] == 'bearer'

    @pytest.mark.asyncio
    async def test_param_filter_parsing(self, query_processor):
        """Test parameter filter parsing."""
        query = "param:user_id status:200"
        processed = await query_processor.process_query(query)

        assert 'param' in processed.field_filters
        assert 'status' in processed.field_filters
        assert processed.field_filters['param'] == 'user_id'
        assert processed.field_filters['status'] == '200'

    @pytest.mark.asyncio
    async def test_response_filter_parsing(self, query_processor):
        """Test response filter parsing."""
        query = "response:json type:object"
        processed = await query_processor.process_query(query)

        assert 'response' in processed.field_filters
        assert 'type' in processed.field_filters
        assert processed.field_filters['response'] == 'json'
        assert processed.field_filters['type'] == 'object'


class TestQueryEnhancement:
    """Test query enhancement with synonyms and variations."""

    @pytest.mark.asyncio
    async def test_synonym_expansion(self, query_processor):
        """Test synonym expansion for API terms."""
        query = "auth user"
        processed = await query_processor.process_query(query)

        # Should include synonyms in enhanced terms
        enhanced = processed.enhanced_terms
        assert len(enhanced) > len(processed.normalized_terms)
        # Check for auth synonyms
        auth_synonyms = ['authentication', 'authorization', 'login']
        assert any(syn in enhanced for syn in auth_synonyms)

    @pytest.mark.asyncio
    async def test_api_variations(self, query_processor):
        """Test API-specific term variations."""
        query = "user"
        processed = await query_processor.process_query(query)

        enhanced = processed.enhanced_terms
        # Should include variations like user_id, users
        assert 'users' in enhanced or any('user' in term for term in enhanced)

    @pytest.mark.asyncio
    async def test_duplicate_removal(self, query_processor):
        """Test that duplicate terms are removed from enhancement."""
        query = "user user authentication auth"
        processed = await query_processor.process_query(query)

        # Enhanced terms should not have duplicates
        enhanced = processed.enhanced_terms
        assert len(enhanced) == len(set(enhanced))


class TestFuzzyMatching:
    """Test fuzzy matching and typo tolerance."""

    @pytest.mark.asyncio
    async def test_fuzzy_term_preparation(self, query_processor):
        """Test preparation of terms for fuzzy matching."""
        query = "authentication endpoint parameter"
        processed = await query_processor.process_query(query)

        # Only longer terms should be in fuzzy terms
        fuzzy = processed.fuzzy_terms
        assert all(len(term) > 3 for term in fuzzy)

    @pytest.mark.asyncio
    async def test_short_term_exclusion(self, query_processor):
        """Test that short terms are excluded from fuzzy matching."""
        query = "get put api"
        processed = await query_processor.process_query(query)

        # Short terms should not be in fuzzy terms
        fuzzy = processed.fuzzy_terms
        short_terms = ['get', 'put', 'api']
        assert not any(term in fuzzy for term in short_terms)


class TestWhooshQueryGeneration:
    """Test Whoosh query generation from processed queries."""

    def test_simple_query_generation(self, query_processor):
        """Test simple Whoosh query generation."""
        processed_query = ProcessedQuery(
            original_query="user auth",
            normalized_terms=['user', 'auth'],
            field_filters={},
            boolean_operators={},
            fuzzy_terms=[],
            excluded_terms=[],
            query_type='simple',
            enhanced_terms=['user', 'auth', 'authentication', 'users'],
            suggestions=[]
        )

        schema_fields = ['endpoint_path', 'summary', 'description', 'parameters', 'tags']
        query = query_processor.generate_whoosh_query(processed_query, schema_fields)

        assert query is not None
        # Should be a compound query for enhanced terms

    def test_field_specific_query_generation(self, query_processor):
        """Test field-specific Whoosh query generation."""
        processed_query = ProcessedQuery(
            original_query="path:/users method:GET",
            normalized_terms=[],
            field_filters={'path': '/users', 'method': 'GET'},
            boolean_operators={},
            fuzzy_terms=[],
            excluded_terms=[],
            query_type='field_specific',
            enhanced_terms=[],
            suggestions=[]
        )

        schema_fields = ['endpoint_path', 'http_method', 'summary', 'description']
        query = query_processor.generate_whoosh_query(processed_query, schema_fields)

        assert query is not None

    def test_boolean_query_generation(self, query_processor):
        """Test boolean Whoosh query generation."""
        processed_query = ProcessedQuery(
            original_query="user AND auth",
            normalized_terms=['user', 'auth'],
            field_filters={},
            boolean_operators={'and': ['user', 'auth'], 'or': [], 'not': []},
            fuzzy_terms=[],
            excluded_terms=[],
            query_type='boolean',
            enhanced_terms=['user', 'auth'],
            suggestions=[]
        )

        schema_fields = ['endpoint_path', 'summary', 'description']
        query = query_processor.generate_whoosh_query(processed_query, schema_fields)

        assert query is not None

    def test_excluded_terms_handling(self, query_processor):
        """Test excluded terms in Whoosh query generation."""
        processed_query = ProcessedQuery(
            original_query="auth NOT oauth",
            normalized_terms=['auth'],
            field_filters={},
            boolean_operators={'and': [], 'or': [], 'not': ['oauth']},
            fuzzy_terms=[],
            excluded_terms=['oauth'],
            query_type='boolean',
            enhanced_terms=['auth', 'authentication'],
            suggestions=[]
        )

        schema_fields = ['endpoint_path', 'summary', 'description']
        query = query_processor.generate_whoosh_query(processed_query, schema_fields)

        assert query is not None


class TestQuerySuggestions:
    """Test query suggestion generation."""

    @pytest.mark.asyncio
    async def test_typo_fix_suggestions(self, query_processor, sample_available_terms):
        """Test typo fix suggestions."""
        query = "autentication"  # Typo in "authentication"
        suggestions = await query_processor.generate_query_suggestions(
            query, 0, sample_available_terms
        )

        assert len(suggestions) > 0
        # Should suggest "authentication"
        typo_fixes = [s for s in suggestions if s.category == 'typo_fix']
        assert any('authentication' in s.query for s in typo_fixes)

    @pytest.mark.asyncio
    async def test_broader_query_suggestions(self, query_processor):
        """Test broader query suggestions for zero results."""
        query = "very specific complex query terms"
        suggestions = await query_processor.generate_query_suggestions(query, 0)

        assert len(suggestions) > 0
        # Should suggest broader alternatives
        broader = [s for s in suggestions if s.category == 'expansion']
        assert len(broader) > 0

    @pytest.mark.asyncio
    async def test_refinement_suggestions(self, query_processor):
        """Test refinement suggestions for few results."""
        query = "user"
        suggestions = await query_processor.generate_query_suggestions(query, 3)

        assert len(suggestions) > 0
        # Should suggest refinements
        refinements = [s for s in suggestions if s.category == 'refinement']
        assert len(refinements) > 0

    @pytest.mark.asyncio
    async def test_api_pattern_suggestions(self, query_processor):
        """Test API pattern suggestions."""
        query = "user create"
        suggestions = await query_processor.generate_query_suggestions(query, 3)

        # Should include API pattern suggestions
        assert len(suggestions) > 0
        # May include method:POST, path:users, etc.

    @pytest.mark.asyncio
    async def test_suggestion_limit(self, query_processor):
        """Test that suggestions are limited to reasonable number."""
        query = "user authentication api endpoint"
        suggestions = await query_processor.generate_query_suggestions(query, 0)

        # Should not exceed 5 suggestions
        assert len(suggestions) <= 5

    @pytest.mark.asyncio
    async def test_suggestion_scoring(self, query_processor):
        """Test that suggestions are scored and sorted."""
        query = "user"
        suggestions = await query_processor.generate_query_suggestions(query, 0)

        if len(suggestions) > 1:
            # Should be sorted by score (descending)
            scores = [s.score for s in suggestions]
            assert scores == sorted(scores, reverse=True)


class TestPerformanceAndEdgeCases:
    """Test performance and edge case handling."""

    @pytest.mark.asyncio
    async def test_very_long_query_handling(self, query_processor):
        """Test handling of very long queries."""
        long_query = " ".join(["term"] * 100)
        processed = await query_processor.process_query(long_query)

        assert processed.original_query == long_query
        assert processed.query_type in ['simple', 'natural_language']

    @pytest.mark.asyncio
    async def test_special_characters_query(self, query_processor):
        """Test handling of queries with special characters."""
        query = "user@domain.com /api/v1/users?param=value"
        processed = await query_processor.process_query(query)

        assert processed.original_query == query
        assert len(processed.normalized_terms) > 0

    @pytest.mark.asyncio
    async def test_unicode_query_handling(self, query_processor):
        """Test handling of unicode characters in queries."""
        query = "用户 authentication ñoño"
        processed = await query_processor.process_query(query)

        assert processed.original_query == query
        assert len(processed.normalized_terms) > 0

    @pytest.mark.asyncio
    async def test_malformed_field_queries(self, query_processor):
        """Test handling of malformed field queries."""
        query = "path: method:GET:extra auth:"
        processed = await query_processor.process_query(query)

        # Should handle gracefully without crashing
        assert processed.original_query == query

    @pytest.mark.asyncio
    async def test_only_stopwords_query(self, query_processor):
        """Test handling of queries with only stopwords."""
        query = "the and or but"
        processed = await query_processor.process_query(query)

        # Should handle gracefully, may result in empty normalized terms
        assert processed.original_query == query

    @pytest.mark.asyncio
    async def test_processing_performance(self, query_processor):
        """Test that query processing completes within reasonable time."""
        import time

        query = "user authentication endpoint parameter response"
        start_time = time.time()

        processed = await query_processor.process_query(query)

        end_time = time.time()
        processing_time = end_time - start_time

        # Should complete within 50ms for simple queries
        assert processing_time < 0.05
        assert processed is not None


class TestNLTKIntegration:
    """Test NLTK integration and fallback behavior."""

    def test_nltk_availability_handling(self, search_config):
        """Test handling when NLTK is not available."""
        with patch('swagger_mcp_server.search.query_processor.NLTK_AVAILABLE', False):
            processor = QueryProcessor(search_config)
            assert processor.stemmer is None
            assert processor.stop_words == set()

    @pytest.mark.asyncio
    async def test_fallback_processing_without_nltk(self, search_config):
        """Test query processing fallback when NLTK is unavailable."""
        with patch('swagger_mcp_server.search.query_processor.NLTK_AVAILABLE', False):
            processor = QueryProcessor(search_config)
            query = "users authentication endpoints"
            processed = await processor.process_query(query)

            assert processed.original_query == query
            assert len(processed.normalized_terms) > 0
            # Should still work without stemming

    @pytest.mark.asyncio
    async def test_nltk_error_handling(self, query_processor):
        """Test handling of NLTK processing errors."""
        # Mock NLTK components to raise errors
        if hasattr(query_processor, 'stemmer') and query_processor.stemmer:
            with patch.object(query_processor.stemmer, 'stem', side_effect=Exception("NLTK error")):
                query = "users authentication"
                processed = await query_processor.process_query(query)

                # Should handle errors gracefully
                assert processed.original_query == query
                assert len(processed.normalized_terms) > 0


@pytest.mark.integration
class TestQueryProcessorIntegration:
    """Integration tests for query processor with other components."""

    def test_config_integration(self, search_config):
        """Test integration with search configuration."""
        processor = QueryProcessor(search_config)
        assert processor.config == search_config

    @pytest.mark.asyncio
    async def test_full_query_pipeline(self, query_processor):
        """Test complete query processing pipeline."""
        query = "path:/users method:POST auth:bearer NOT oauth"
        processed = await query_processor.process_query(query)

        # Verify all components are processed
        assert processed.original_query == query
        assert processed.field_filters
        assert processed.boolean_operators
        assert processed.excluded_terms
        assert processed.enhanced_terms
        assert processed.query_type == 'field_specific'

        # Test Whoosh query generation
        schema_fields = ['endpoint_path', 'http_method', 'auth_type', 'summary', 'description']
        whoosh_query = query_processor.generate_whoosh_query(processed, schema_fields)
        assert whoosh_query is not None

    @pytest.mark.asyncio
    async def test_suggestion_generation_pipeline(self, query_processor, sample_available_terms):
        """Test complete suggestion generation pipeline."""
        query = "authen user"  # Partial/typo query
        suggestions = await query_processor.generate_query_suggestions(
            query, 0, sample_available_terms
        )

        assert len(suggestions) > 0
        assert all(isinstance(s, QuerySuggestion) for s in suggestions)
        assert all(hasattr(s, 'query') and hasattr(s, 'score') for s in suggestions)