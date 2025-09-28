"""Relevance ranking and search optimization for the Swagger MCP Server.

This module provides enhanced relevance ranking using BM25 and custom
scoring algorithms to improve search result quality.
"""

import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from rank_bm25 import BM25L, BM25Okapi, BM25Plus

from ..config.settings import SearchConfig


@dataclass
class RelevanceScore:
    """Represents a relevance score with breakdown."""

    total_score: float
    bm25_score: float
    field_scores: Dict[str, float]
    boost_factors: Dict[str, float]
    metadata: Dict[str, Any]


class RelevanceRanker:
    """Advanced relevance ranking using multiple algorithms."""

    def __init__(self, config: SearchConfig):
        """Initialize the relevance ranker.

        Args:
            config: Search configuration with ranking parameters
        """
        self.config = config
        self.bm25_instances: Dict[str, Any] = {}

    def train_bm25_models(self, corpus: Dict[str, List[str]]) -> None:
        """Train BM25 models for different document fields.

        Args:
            corpus: Dictionary mapping field names to lists of documents
        """
        for field_name, documents in corpus.items():
            if documents:
                # Tokenize documents for BM25
                tokenized_docs = [doc.lower().split() for doc in documents]

                # Use BM25Plus for better handling of long documents
                self.bm25_instances[field_name] = BM25Plus(
                    tokenized_docs,
                    k1=1.2,  # Controls term frequency saturation
                    b=0.75,  # Controls length normalization
                    delta=1.0,  # BM25Plus delta parameter
                )

    def calculate_relevance_score(
        self,
        query_terms: List[str],
        document: Dict[str, Any],
        document_collection_stats: Optional[Dict[str, Any]] = None,
    ) -> RelevanceScore:
        """Calculate comprehensive relevance score for a document.

        Args:
            query_terms: List of query terms
            document: Document to score
            document_collection_stats: Optional collection statistics

        Returns:
            RelevanceScore: Detailed relevance score breakdown
        """
        field_scores = {}
        boost_factors = {}
        total_score = 0.0

        # Base field weights from configuration
        field_weights = {
            "endpoint_path": 1.5,
            "summary": 1.2,
            "description": 1.0,
            "parameters": 0.8,
            "tags": 0.6,
            "operation_id": 0.9,
        }

        # Calculate BM25 scores for each field
        for field_name, weight in field_weights.items():
            if field_name in document and document[field_name]:
                field_content = str(document[field_name]).lower()
                field_tokens = field_content.split()

                # Use trained BM25 model if available
                if field_name in self.bm25_instances:
                    bm25_score = self._calculate_bm25_score(
                        query_terms, field_tokens, field_name
                    )
                else:
                    # Fallback to simple TF-IDF-like scoring
                    bm25_score = self._calculate_simple_score(query_terms, field_tokens)

                field_scores[field_name] = bm25_score
                total_score += bm25_score * weight

        # Apply boost factors
        boost_factors = self._calculate_boost_factors(document)
        for factor_name, boost_value in boost_factors.items():
            total_score *= boost_value

        # Apply penalties for certain conditions
        penalties = self._calculate_penalties(document)
        for penalty_name, penalty_value in penalties.items():
            total_score *= penalty_value
            boost_factors[f"penalty_{penalty_name}"] = penalty_value

        # Normalize score to 0-1 range
        normalized_score = self._normalize_score(total_score)

        return RelevanceScore(
            total_score=normalized_score,
            bm25_score=sum(field_scores.values()),
            field_scores=field_scores,
            boost_factors=boost_factors,
            metadata={
                "query_term_count": len(query_terms),
                "matched_fields": list(field_scores.keys()),
                "document_length": sum(
                    len(str(document.get(field, "")).split())
                    for field in field_weights.keys()
                ),
            },
        )

    def rank_results(
        self,
        query_terms: List[str],
        documents: List[Dict[str, Any]],
        max_results: Optional[int] = None,
    ) -> List[Tuple[Dict[str, Any], RelevanceScore]]:
        """Rank a list of documents by relevance to the query.

        Args:
            query_terms: List of query terms
            documents: List of documents to rank
            max_results: Maximum number of results to return

        Returns:
            List of (document, relevance_score) tuples sorted by relevance
        """
        scored_documents = []

        for document in documents:
            relevance_score = self.calculate_relevance_score(query_terms, document)
            scored_documents.append((document, relevance_score))

        # Sort by total score in descending order
        scored_documents.sort(key=lambda x: x[1].total_score, reverse=True)

        if max_results:
            scored_documents = scored_documents[:max_results]

        return scored_documents

    def explain_score(
        self,
        query_terms: List[str],
        document: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Provide a detailed explanation of how a relevance score was calculated.

        Args:
            query_terms: List of query terms
            document: Document to explain

        Returns:
            Dict[str, Any]: Detailed score explanation
        """
        relevance_score = self.calculate_relevance_score(query_terms, document)

        explanation = {
            "final_score": relevance_score.total_score,
            "query_terms": query_terms,
            "field_contributions": {},
            "boost_factors": relevance_score.boost_factors,
            "calculation_steps": [],
        }

        # Explain field contributions
        field_weights = {
            "endpoint_path": 1.5,
            "summary": 1.2,
            "description": 1.0,
            "parameters": 0.8,
            "tags": 0.6,
            "operation_id": 0.9,
        }

        for field_name, weight in field_weights.items():
            if field_name in relevance_score.field_scores:
                field_score = relevance_score.field_scores[field_name]
                weighted_score = field_score * weight

                explanation["field_contributions"][field_name] = {
                    "raw_score": field_score,
                    "weight": weight,
                    "weighted_score": weighted_score,
                    "content": str(document.get(field_name, ""))[:100] + "...",
                }

                explanation["calculation_steps"].append(
                    f"{field_name}: {field_score:.3f} × {weight} = {weighted_score:.3f}"
                )

        # Explain boost factors
        for factor_name, boost_value in relevance_score.boost_factors.items():
            explanation["calculation_steps"].append(
                f"Boost ({factor_name}): × {boost_value:.3f}"
            )

        return explanation

    # Private methods

    def _calculate_bm25_score(
        self, query_terms: List[str], field_tokens: List[str], field_name: str
    ) -> float:
        """Calculate BM25 score for a specific field.

        Args:
            query_terms: Query terms
            field_tokens: Tokenized field content
            field_name: Name of the field

        Returns:
            float: BM25 score
        """
        if field_name not in self.bm25_instances:
            return 0.0

        bm25 = self.bm25_instances[field_name]

        try:
            # Calculate BM25 score for the document
            scores = bm25.get_scores(query_terms)
            # Since we're scoring a single document, take the mean score
            return float(scores.mean()) if len(scores) > 0 else 0.0
        except Exception:
            return 0.0

    def _calculate_simple_score(
        self, query_terms: List[str], field_tokens: List[str]
    ) -> float:
        """Calculate simple TF-IDF-like score when BM25 model is not available.

        Args:
            query_terms: Query terms
            field_tokens: Tokenized field content

        Returns:
            float: Simple relevance score
        """
        if not field_tokens:
            return 0.0

        score = 0.0
        field_length = len(field_tokens)

        for term in query_terms:
            term = term.lower()
            # Term frequency
            tf = field_tokens.count(term)
            if tf > 0:
                # Simple TF score with length normalization
                tf_score = tf / (tf + 1.0)  # Saturated TF
                length_norm = 1.0 / math.sqrt(field_length)
                score += tf_score * length_norm

        return score

    def _calculate_boost_factors(self, document: Dict[str, Any]) -> Dict[str, float]:
        """Calculate boost factors based on document characteristics.

        Args:
            document: Document to analyze

        Returns:
            Dict[str, float]: Boost factors
        """
        boost_factors = {}

        # Boost for exact path matches (detected by path structure)
        endpoint_path = document.get("endpoint_path", "")
        if endpoint_path:
            # Boost shorter, more specific paths
            path_segments = endpoint_path.strip("/").split("/")
            if len(path_segments) <= 3:
                boost_factors["short_path"] = 1.1
            elif len(path_segments) >= 6:
                boost_factors["long_path"] = 0.95

        # Boost for common HTTP methods
        http_method = document.get("http_method", "").upper()
        if http_method in ["GET", "POST"]:
            boost_factors["common_method"] = 1.05
        elif http_method in ["DELETE", "PATCH"]:
            boost_factors["less_common_method"] = 0.98

        # Boost for well-documented endpoints
        summary = document.get("summary", "")
        description = document.get("description", "")
        if len(summary) > 10 and len(description) > 50:
            boost_factors["well_documented"] = 1.1
        elif not summary and not description:
            boost_factors["poor_documentation"] = 0.9

        # Boost for endpoints with parameters (more functional)
        parameters = document.get("parameters", "")
        if parameters:
            boost_factors["has_parameters"] = 1.05

        return boost_factors

    def _calculate_penalties(self, document: Dict[str, Any]) -> Dict[str, float]:
        """Calculate penalty factors for document characteristics.

        Args:
            document: Document to analyze

        Returns:
            Dict[str, float]: Penalty factors (< 1.0)
        """
        penalties = {}

        # Penalty for deprecated endpoints
        if document.get("deprecated", False):
            penalties["deprecated"] = 0.7

        # Penalty for endpoints without proper documentation
        summary = document.get("summary", "")
        description = document.get("description", "")
        if not summary and not description:
            penalties["no_documentation"] = 0.8

        return penalties

    def _normalize_score(self, raw_score: float) -> float:
        """Normalize score to 0-1 range using sigmoid function.

        Args:
            raw_score: Raw relevance score

        Returns:
            float: Normalized score between 0 and 1
        """
        # Use sigmoid function to normalize scores
        return 1.0 / (1.0 + math.exp(-raw_score))

    def get_ranking_statistics(self) -> Dict[str, Any]:
        """Get statistics about the ranking models.

        Returns:
            Dict[str, Any]: Ranking model statistics
        """
        stats = {
            "bm25_models_trained": len(self.bm25_instances),
            "available_fields": list(self.bm25_instances.keys()),
        }

        for field_name, bm25 in self.bm25_instances.items():
            if hasattr(bm25, "corpus_size"):
                stats[f"{field_name}_corpus_size"] = bm25.corpus_size
            if hasattr(bm25, "avgdl"):
                stats[f"{field_name}_avg_doc_length"] = bm25.avgdl

        return stats
