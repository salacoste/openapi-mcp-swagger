"""Tests for relevance ranking functionality."""

from unittest.mock import Mock, patch

import pytest

from swagger_mcp_server.config.settings import SearchConfig
from swagger_mcp_server.search.relevance import RelevanceRanker, RelevanceScore


@pytest.fixture
def search_config():
    """Create test search configuration."""
    return SearchConfig()


@pytest.fixture
def relevance_ranker(search_config):
    """Create RelevanceRanker instance for testing."""
    return RelevanceRanker(search_config)


class TestRelevanceRanker:
    """Test cases for RelevanceRanker class."""

    def test_initialization(self, relevance_ranker, search_config):
        """Test RelevanceRanker initialization."""
        assert relevance_ranker.config == search_config
        assert isinstance(relevance_ranker.bm25_instances, dict)
        assert len(relevance_ranker.bm25_instances) == 0

    def test_train_bm25_models(self, relevance_ranker):
        """Test training BM25 models with corpus data."""
        corpus = {
            "endpoint_path": ["/api/users", "/api/users/{id}", "/api/posts"],
            "description": [
                "Get all users from the system",
                "Get a specific user by ID",
                "Retrieve all blog posts",
            ],
        }

        relevance_ranker.train_bm25_models(corpus)

        assert "endpoint_path" in relevance_ranker.bm25_instances
        assert "description" in relevance_ranker.bm25_instances

    def test_train_bm25_models_with_empty_corpus(self, relevance_ranker):
        """Test training with empty corpus."""
        corpus = {"endpoint_path": [], "description": ["Some content"]}

        relevance_ranker.train_bm25_models(corpus)

        # Should only create model for non-empty fields
        assert "endpoint_path" not in relevance_ranker.bm25_instances
        assert "description" in relevance_ranker.bm25_instances

    def test_calculate_relevance_score_basic(self, relevance_ranker):
        """Test basic relevance score calculation."""
        query_terms = ["user", "api"]
        document = {
            "endpoint_path": "/api/users",
            "summary": "Get user data",
            "description": "Retrieve user information from the API",
            "parameters": "user_id (string): The user identifier",
            "tags": "users api",
            "operation_id": "getUser",
        }

        score = relevance_ranker.calculate_relevance_score(query_terms, document)

        assert isinstance(score, RelevanceScore)
        assert score.total_score >= 0
        assert score.total_score <= 1  # Should be normalized
        assert isinstance(score.field_scores, dict)
        assert isinstance(score.boost_factors, dict)
        assert isinstance(score.metadata, dict)

    def test_calculate_relevance_score_with_trained_models(self, relevance_ranker):
        """Test relevance calculation with trained BM25 models."""
        # Train models first
        corpus = {
            "endpoint_path": ["/api/users", "/api/posts", "/api/comments"],
            "description": ["Get users", "Get posts", "Get comments"],
        }
        relevance_ranker.train_bm25_models(corpus)

        query_terms = ["users"]
        document = {
            "endpoint_path": "/api/users",
            "description": "Get all users",
            "summary": "User endpoint",
            "parameters": "",
            "tags": "users",
            "operation_id": "getUsers",
        }

        score = relevance_ranker.calculate_relevance_score(query_terms, document)

        assert score.total_score > 0
        assert "endpoint_path" in score.field_scores
        assert "description" in score.field_scores

    def test_rank_results(self, relevance_ranker):
        """Test ranking multiple documents."""
        query_terms = ["user"]
        documents = [
            {
                "endpoint_path": "/api/users",
                "summary": "Get users",
                "description": "Retrieve all users",
                "parameters": "",
                "tags": "users",
                "operation_id": "getUsers",
            },
            {
                "endpoint_path": "/api/posts",
                "summary": "Get posts",
                "description": "Retrieve user posts",
                "parameters": "user_id",
                "tags": "posts",
                "operation_id": "getPosts",
            },
            {
                "endpoint_path": "/api/comments",
                "summary": "Get comments",
                "description": "Retrieve comments",
                "parameters": "",
                "tags": "comments",
                "operation_id": "getComments",
            },
        ]

        ranked_results = relevance_ranker.rank_results(query_terms, documents)

        assert len(ranked_results) == 3
        assert all(isinstance(item, tuple) for item in ranked_results)
        assert all(len(item) == 2 for item in ranked_results)

        # Results should be sorted by relevance (highest first)
        scores = [item[1].total_score for item in ranked_results]
        assert scores == sorted(scores, reverse=True)

        # First result should be most relevant (contains "user" prominently)
        first_doc, first_score = ranked_results[0]
        assert "users" in first_doc["endpoint_path"].lower()

    def test_rank_results_with_limit(self, relevance_ranker):
        """Test ranking with maximum results limit."""
        query_terms = ["test"]
        documents = [
            {"endpoint_path": f"/api/test{i}", "description": "test"} for i in range(10)
        ]

        ranked_results = relevance_ranker.rank_results(
            query_terms, documents, max_results=5
        )

        assert len(ranked_results) == 5

    def test_explain_score(self, relevance_ranker):
        """Test score explanation functionality."""
        query_terms = ["user", "api"]
        document = {
            "endpoint_path": "/api/users",
            "summary": "User API",
            "description": "Get user data from API",
            "parameters": "user_id (string): User identifier",
            "tags": "users api",
            "operation_id": "getUser",
        }

        explanation = relevance_ranker.explain_score(query_terms, document)

        assert isinstance(explanation, dict)
        assert "final_score" in explanation
        assert "query_terms" in explanation
        assert "field_contributions" in explanation
        assert "boost_factors" in explanation
        assert "calculation_steps" in explanation

        assert explanation["query_terms"] == query_terms
        assert isinstance(explanation["field_contributions"], dict)
        assert isinstance(explanation["calculation_steps"], list)

    def test_get_ranking_statistics(self, relevance_ranker):
        """Test getting ranking model statistics."""
        # Initially no models
        stats = relevance_ranker.get_ranking_statistics()
        assert stats["bm25_models_trained"] == 0
        assert stats["available_fields"] == []

        # Train some models
        corpus = {
            "endpoint_path": ["/api/test"],
            "description": ["test description"],
        }
        relevance_ranker.train_bm25_models(corpus)

        stats = relevance_ranker.get_ranking_statistics()
        assert stats["bm25_models_trained"] == 2
        assert "endpoint_path" in stats["available_fields"]
        assert "description" in stats["available_fields"]


class TestRelevanceScore:
    """Test RelevanceScore dataclass."""

    def test_relevance_score_creation(self):
        """Test creating a RelevanceScore instance."""
        score = RelevanceScore(
            total_score=0.85,
            bm25_score=0.75,
            field_scores={"endpoint_path": 0.9, "description": 0.6},
            boost_factors={"short_path": 1.1},
            metadata={"query_term_count": 2},
        )

        assert score.total_score == 0.85
        assert score.bm25_score == 0.75
        assert score.field_scores["endpoint_path"] == 0.9
        assert score.boost_factors["short_path"] == 1.1
        assert score.metadata["query_term_count"] == 2


class TestBoostFactors:
    """Test boost factor calculation."""

    def test_calculate_boost_factors_short_path(self, relevance_ranker):
        """Test boost for short API paths."""
        document = {"endpoint_path": "/api/users"}

        boost_factors = relevance_ranker._calculate_boost_factors(document)

        assert "short_path" in boost_factors
        assert boost_factors["short_path"] > 1.0

    def test_calculate_boost_factors_long_path(self, relevance_ranker):
        """Test penalty for long API paths."""
        document = {
            "endpoint_path": "/api/v1/organizations/users/profiles/settings/preferences"
        }

        boost_factors = relevance_ranker._calculate_boost_factors(document)

        assert "long_path" in boost_factors
        assert boost_factors["long_path"] < 1.0

    def test_calculate_boost_factors_common_methods(self, relevance_ranker):
        """Test boost for common HTTP methods."""
        get_document = {"http_method": "GET"}
        post_document = {"http_method": "POST"}

        get_boosts = relevance_ranker._calculate_boost_factors(get_document)
        post_boosts = relevance_ranker._calculate_boost_factors(post_document)

        assert "common_method" in get_boosts
        assert "common_method" in post_boosts
        assert get_boosts["common_method"] > 1.0
        assert post_boosts["common_method"] > 1.0

    def test_calculate_boost_factors_less_common_methods(self, relevance_ranker):
        """Test slight penalty for less common HTTP methods."""
        delete_document = {"http_method": "DELETE"}
        patch_document = {"http_method": "PATCH"}

        delete_boosts = relevance_ranker._calculate_boost_factors(delete_document)
        patch_boosts = relevance_ranker._calculate_boost_factors(patch_document)

        assert "less_common_method" in delete_boosts
        assert "less_common_method" in patch_boosts
        assert delete_boosts["less_common_method"] < 1.0
        assert patch_boosts["less_common_method"] < 1.0

    def test_calculate_boost_factors_well_documented(self, relevance_ranker):
        """Test boost for well-documented endpoints."""
        document = {
            "summary": "Get user profile data",
            "description": "Retrieve detailed user profile information including personal data, preferences, and settings",
        }

        boost_factors = relevance_ranker._calculate_boost_factors(document)

        assert "well_documented" in boost_factors
        assert boost_factors["well_documented"] > 1.0

    def test_calculate_boost_factors_poor_documentation(self, relevance_ranker):
        """Test penalty for poorly documented endpoints."""
        document = {"summary": "", "description": ""}

        boost_factors = relevance_ranker._calculate_boost_factors(document)

        assert "poor_documentation" in boost_factors
        assert boost_factors["poor_documentation"] < 1.0

    def test_calculate_boost_factors_has_parameters(self, relevance_ranker):
        """Test boost for endpoints with parameters."""
        document = {"parameters": "user_id (string): User identifier"}

        boost_factors = relevance_ranker._calculate_boost_factors(document)

        assert "has_parameters" in boost_factors
        assert boost_factors["has_parameters"] > 1.0


class TestPenalties:
    """Test penalty calculation."""

    def test_calculate_penalties_deprecated(self, relevance_ranker):
        """Test penalty for deprecated endpoints."""
        document = {"deprecated": True}

        penalties = relevance_ranker._calculate_penalties(document)

        assert "deprecated" in penalties
        assert penalties["deprecated"] < 1.0

    def test_calculate_penalties_no_documentation(self, relevance_ranker):
        """Test penalty for endpoints without documentation."""
        document = {"summary": "", "description": ""}

        penalties = relevance_ranker._calculate_penalties(document)

        assert "no_documentation" in penalties
        assert penalties["no_documentation"] < 1.0

    def test_calculate_penalties_no_penalties(self, relevance_ranker):
        """Test that no penalties are applied for good endpoints."""
        document = {
            "deprecated": False,
            "summary": "Good endpoint",
            "description": "Well documented endpoint",
        }

        penalties = relevance_ranker._calculate_penalties(document)

        # Should have no penalties
        assert len(penalties) == 0


class TestScoreNormalization:
    """Test score normalization."""

    def test_normalize_score_range(self, relevance_ranker):
        """Test that normalized scores are in 0-1 range."""
        test_scores = [-10, -1, 0, 0.5, 1, 2, 10]

        for raw_score in test_scores:
            normalized = relevance_ranker._normalize_score(raw_score)
            assert 0 <= normalized <= 1

    def test_normalize_score_sigmoid_behavior(self, relevance_ranker):
        """Test sigmoid normalization behavior."""
        # Negative scores should be < 0.5
        assert relevance_ranker._normalize_score(-1) < 0.5

        # Zero should be 0.5
        assert abs(relevance_ranker._normalize_score(0) - 0.5) < 0.01

        # Positive scores should be > 0.5
        assert relevance_ranker._normalize_score(1) > 0.5

        # Higher scores should give higher normalized values
        score1 = relevance_ranker._normalize_score(1)
        score2 = relevance_ranker._normalize_score(2)
        assert score2 > score1


class TestBM25Scoring:
    """Test BM25 scoring functionality."""

    def test_calculate_bm25_score_no_model(self, relevance_ranker):
        """Test BM25 scoring when no model is trained."""
        query_terms = ["test"]
        field_tokens = ["test", "endpoint"]

        score = relevance_ranker._calculate_bm25_score(
            query_terms, field_tokens, "unknown_field"
        )

        assert score == 0.0

    def test_calculate_simple_score(self, relevance_ranker):
        """Test simple TF-IDF-like scoring fallback."""
        query_terms = ["test", "user"]
        field_tokens = ["test", "endpoint", "for", "user", "management"]

        score = relevance_ranker._calculate_simple_score(query_terms, field_tokens)

        assert score > 0
        assert isinstance(score, float)

    def test_calculate_simple_score_no_matches(self, relevance_ranker):
        """Test simple scoring with no matching terms."""
        query_terms = ["nonexistent"]
        field_tokens = ["test", "endpoint"]

        score = relevance_ranker._calculate_simple_score(query_terms, field_tokens)

        assert score == 0.0

    def test_calculate_simple_score_empty_field(self, relevance_ranker):
        """Test simple scoring with empty field."""
        query_terms = ["test"]
        field_tokens = []

        score = relevance_ranker._calculate_simple_score(query_terms, field_tokens)

        assert score == 0.0
