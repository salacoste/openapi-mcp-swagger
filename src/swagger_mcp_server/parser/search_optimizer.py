"""Search optimization for normalized OpenAPI data structures."""

import re
from collections import Counter
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple

from swagger_mcp_server.config.logging import get_logger
from swagger_mcp_server.parser.models import (
    NormalizedEndpoint,
    NormalizedSchema,
    NormalizedSecurityScheme,
    ParameterLocation,
)

logger = get_logger(__name__)


@dataclass
class SearchableDocument:
    """Represents a searchable document with metadata."""

    id: str
    type: str  # 'endpoint', 'schema', 'security'
    title: str
    content: str
    tags: List[str]
    metadata: Dict[str, Any]
    boost: float = 1.0


@dataclass
class SearchIndex:
    """Search index with optimized data structures."""

    documents: List[SearchableDocument]
    term_frequencies: Dict[str, Dict[str, int]]  # term -> doc_id -> frequency
    document_frequencies: Dict[str, int]  # term -> number of docs containing term
    document_lengths: Dict[str, int]  # doc_id -> total terms
    total_documents: int
    vocabulary: Set[str]


class SearchOptimizer:
    """Optimizes normalized data structures for efficient search."""

    def __init__(self):
        self.logger = get_logger(__name__)

        # Stop words for filtering
        self.stop_words = {
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
            "has",
            "he",
            "in",
            "is",
            "it",
            "its",
            "of",
            "on",
            "that",
            "the",
            "to",
            "was",
            "were",
            "will",
            "with",
            "this",
            "these",
            "they",
            "them",
            "their",
            "his",
            "her",
            "have",
            "had",
            "can",
            "could",
            "should",
            "would",
            "may",
            "might",
            "must",
            "shall",
            "do",
            "does",
            "did",
            "get",
            "set",
            "put",
            "post",
            "delete",
            "patch",
        }

        # API-specific important terms that shouldn't be filtered
        self.important_terms = {
            "api",
            "rest",
            "http",
            "https",
            "json",
            "xml",
            "oauth",
            "jwt",
            "auth",
            "token",
            "key",
            "secret",
            "bearer",
            "basic",
            "digest",
            "create",
            "read",
            "update",
            "delete",
            "list",
            "search",
            "filter",
            "sort",
            "page",
            "limit",
            "offset",
            "id",
            "uuid",
            "status",
            "error",
        }

    def optimize_for_search(
        self,
        endpoints: List[NormalizedEndpoint],
        schemas: Dict[str, NormalizedSchema],
        security_schemes: Dict[str, NormalizedSecurityScheme],
    ) -> SearchIndex:
        """Optimize normalized data for efficient search.

        Args:
            endpoints: List of normalized endpoints
            schemas: Dictionary of normalized schemas
            security_schemes: Dictionary of security schemes

        Returns:
            Optimized search index
        """
        self.logger.info(
            "Starting search optimization",
            endpoints=len(endpoints),
            schemas=len(schemas),
            security_schemes=len(security_schemes),
        )

        documents = []

        # Process endpoints
        for endpoint in endpoints:
            doc = self._create_endpoint_document(endpoint)
            documents.append(doc)

        # Process schemas
        for schema_name, schema in schemas.items():
            doc = self._create_schema_document(schema_name, schema)
            documents.append(doc)

        # Process security schemes
        for scheme_name, scheme in security_schemes.items():
            doc = self._create_security_document(scheme_name, scheme)
            documents.append(doc)

        # Build search index
        search_index = self._build_search_index(documents)

        self.logger.info(
            "Search optimization completed",
            total_documents=search_index.total_documents,
            vocabulary_size=len(search_index.vocabulary),
        )

        return search_index

    def _create_endpoint_document(
        self, endpoint: NormalizedEndpoint
    ) -> SearchableDocument:
        """Create a searchable document for an endpoint."""
        # Build comprehensive content
        content_parts = []

        # Basic info
        content_parts.append(
            f"{endpoint.method.value.upper() if hasattr(endpoint.method, 'value') else str(endpoint.method).upper()} {endpoint.path}"
        )

        if endpoint.operation_id:
            content_parts.append(endpoint.operation_id)

        if endpoint.summary:
            content_parts.append(endpoint.summary)

        if endpoint.description:
            content_parts.append(endpoint.description)

        # Parameters
        for param in endpoint.parameters:
            content_parts.append(f"parameter {param.name}")
            if param.description:
                content_parts.append(param.description)
            if param.schema_type:
                content_parts.append(param.schema_type)

        # Request body content types
        if endpoint.request_body and endpoint.request_body.content:
            for content_type in endpoint.request_body.content.keys():
                content_parts.append(content_type)

        # Response content types and status codes
        for status_code, response in endpoint.responses.items():
            content_parts.append(f"status {status_code}")
            if response.description:
                content_parts.append(response.description)
            if response.content:
                for content_type in response.content.keys():
                    content_parts.append(content_type)

        # Extensions
        if hasattr(endpoint, "searchable_text") and endpoint.searchable_text:
            content_parts.extend(endpoint.searchable_text)

        # Tags
        tags = list(endpoint.tags) if endpoint.tags else []

        # Add method and path components as tags
        tags.append(
            endpoint.method.value
            if hasattr(endpoint.method, "value")
            else str(endpoint.method)
        )
        path_parts = [
            part
            for part in endpoint.path.split("/")
            if part and not part.startswith("{")
        ]
        tags.extend(path_parts)

        # Calculate boost based on importance
        boost = 1.0
        if endpoint.deprecated:
            boost = 0.5  # Lower boost for deprecated endpoints
        elif endpoint.operation_id:
            boost = 1.2  # Higher boost for well-documented endpoints

        return SearchableDocument(
            id=f"endpoint_{endpoint.method.value if hasattr(endpoint.method, 'value') else str(endpoint.method)}_{endpoint.path.replace('/', '_').replace('{', '').replace('}', '')}",
            type="endpoint",
            title=f"{endpoint.method.value.upper() if hasattr(endpoint.method, 'value') else str(endpoint.method).upper()} {endpoint.path}",
            content=" ".join(content_parts),
            tags=tags,
            metadata={
                "method": (
                    endpoint.method.value
                    if hasattr(endpoint.method, "value")
                    else str(endpoint.method)
                ),
                "path": endpoint.path,
                "operation_id": endpoint.operation_id,
                "tags": list(endpoint.tags) if endpoint.tags else [],
                "deprecated": endpoint.deprecated,
                "parameter_count": len(endpoint.parameters),
                "response_count": len(endpoint.responses),
            },
            boost=boost,
        )

    def _create_schema_document(
        self, schema_name: str, schema: NormalizedSchema
    ) -> SearchableDocument:
        """Create a searchable document for a schema."""
        content_parts = []

        # Basic info
        content_parts.append(f"schema {schema_name}")

        if schema.title:
            content_parts.append(schema.title)

        if schema.description:
            content_parts.append(schema.description)

        # Type information
        if schema.type:
            content_parts.append(f"type {schema.type}")

        if schema.format:
            content_parts.append(f"format {schema.format}")

        # Properties
        for prop_name in schema.properties.keys():
            content_parts.append(f"property {prop_name}")

        # Required fields
        for required_field in schema.required:
            content_parts.append(f"required {required_field}")

        # Examples
        if schema.example:
            if isinstance(schema.example, str):
                content_parts.append(schema.example)

        # Extensions searchable content
        if hasattr(schema, "searchable_text") and schema.searchable_text:
            content_parts.extend(schema.searchable_text)

        # Tags
        tags = [schema_name, "schema"]
        if schema.type:
            tags.append(schema.type)

        # Add property names as tags
        tags.extend(list(schema.properties.keys())[:10])  # Limit to avoid too many tags

        # Calculate boost
        boost = 1.0
        if schema.deprecated:
            boost = 0.7
        elif len(schema.properties) > 10:
            boost = 1.3  # Boost complex schemas

        return SearchableDocument(
            id=f"schema_{schema_name}",
            type="schema",
            title=schema.title or schema_name,
            content=" ".join(content_parts),
            tags=tags,
            metadata={
                "name": schema_name,
                "type": schema.type,
                "format": schema.format,
                "deprecated": schema.deprecated,
                "property_count": len(schema.properties),
                "required_count": len(schema.required),
                "has_example": schema.example is not None,
            },
            boost=boost,
        )

    def _create_security_document(
        self, scheme_name: str, scheme: NormalizedSecurityScheme
    ) -> SearchableDocument:
        """Create a searchable document for a security scheme."""
        content_parts = []

        # Basic info
        content_parts.append(f"security {scheme_name}")
        content_parts.append(f"type {scheme.type.value}")

        if scheme.description:
            content_parts.append(scheme.description)

        # Type-specific content
        if scheme.api_key_name:
            content_parts.append(f"api key {scheme.api_key_name}")

        if scheme.http_scheme:
            content_parts.append(f"http {scheme.http_scheme}")

        if scheme.bearer_format:
            content_parts.append(f"bearer {scheme.bearer_format}")

        # OAuth2 flows and scopes
        if scheme.oauth2_flows:
            content_parts.append("oauth2")
            for flow_type, flow in scheme.oauth2_flows.items():
                content_parts.append(flow_type.value)
                if flow.scopes:
                    for scope_name, scope_desc in flow.scopes.items():
                        content_parts.append(f"scope {scope_name}")
                        if scope_desc:
                            content_parts.append(scope_desc)

        # OpenID Connect
        if scheme.openid_connect_url:
            content_parts.append("openid connect")

        # Tags
        tags = [scheme_name, "security", scheme.type.value]

        if scheme.oauth2_flows:
            tags.extend(flow.type.value for flow in scheme.oauth2_flows.values())

        return SearchableDocument(
            id=f"security_{scheme_name}",
            type="security",
            title=scheme_name,
            content=" ".join(content_parts),
            tags=tags,
            metadata={
                "name": scheme_name,
                "type": scheme.type.value,
                "api_key_name": scheme.api_key_name,
                "http_scheme": scheme.http_scheme,
                "has_oauth2": bool(scheme.oauth2_flows),
                "oauth2_flow_count": (
                    len(scheme.oauth2_flows) if scheme.oauth2_flows else 0
                ),
            },
            boost=1.0,
        )

    def _build_search_index(self, documents: List[SearchableDocument]) -> SearchIndex:
        """Build optimized search index from documents."""
        term_frequencies = {}
        document_frequencies = Counter()
        document_lengths = {}
        vocabulary = set()

        for doc in documents:
            # Tokenize and process content
            terms = self._tokenize_content(doc.content)
            term_counts = Counter(terms)

            # Store document length
            document_lengths[doc.id] = len(terms)

            # Store term frequencies for this document
            term_frequencies[doc.id] = dict(term_counts)

            # Update document frequencies and vocabulary
            for term in term_counts.keys():
                document_frequencies[term] += 1
                vocabulary.add(term)

        return SearchIndex(
            documents=documents,
            term_frequencies=term_frequencies,
            document_frequencies=dict(document_frequencies),
            document_lengths=document_lengths,
            total_documents=len(documents),
            vocabulary=vocabulary,
        )

    def _tokenize_content(self, content: str) -> List[str]:
        """Tokenize content for search indexing."""
        if not content:
            return []

        # Convert to lowercase
        content = content.lower()

        # Replace common separators with spaces
        content = re.sub(r"[/_\-\.]+", " ", content)

        # Extract words (including numbers)
        words = re.findall(r"\b[a-z0-9]+\b", content)

        # Filter and process words
        processed_words = []
        for word in words:
            # Skip very short words unless they're important
            if len(word) < 2 and word not in self.important_terms:
                continue

            # Skip stop words unless they're important
            if word in self.stop_words and word not in self.important_terms:
                continue

            # Skip very long words (likely UUIDs or encoded data)
            if len(word) > 50:
                continue

            processed_words.append(word)

            # Add word stems for compound words
            if len(word) > 6 and "_" not in word and "-" not in word:
                # Simple stemming for API-related words
                if word.endswith("s") and len(word) > 4:
                    processed_words.append(word[:-1])  # Remove plural 's'
                elif word.endswith("ed") and len(word) > 5:
                    processed_words.append(word[:-2])  # Remove 'ed'
                elif word.endswith("ing") and len(word) > 6:
                    processed_words.append(word[:-3])  # Remove 'ing'

        return processed_words

    def get_search_statistics(self, search_index: SearchIndex) -> Dict[str, Any]:
        """Generate statistics about the search index.

        Args:
            search_index: Search index to analyze

        Returns:
            Dictionary with search statistics
        """
        stats = {
            "total_documents": search_index.total_documents,
            "vocabulary_size": len(search_index.vocabulary),
            "average_document_length": 0.0,
            "document_types": Counter(),
            "most_common_terms": [],
            "document_length_distribution": {},
            "coverage_statistics": {},
        }

        # Calculate averages
        if search_index.document_lengths:
            total_length = sum(search_index.document_lengths.values())
            stats["average_document_length"] = total_length / len(
                search_index.document_lengths
            )

        # Document type distribution
        for doc in search_index.documents:
            stats["document_types"][doc.type] += 1

        # Most common terms
        term_doc_counts = []
        for term, doc_count in search_index.document_frequencies.items():
            term_doc_counts.append((term, doc_count))

        stats["most_common_terms"] = sorted(
            term_doc_counts, key=lambda x: x[1], reverse=True
        )[:20]

        # Document length distribution
        length_ranges = [
            (0, 50),
            (51, 100),
            (101, 200),
            (201, 500),
            (501, float("inf")),
        ]
        length_dist = {
            f"{start}-{end if end != float('inf') else '500+'}": 0
            for start, end in length_ranges
        }

        for length in search_index.document_lengths.values():
            for start, end in length_ranges:
                if start <= length <= end:
                    range_key = f"{start}-{end if end != float('inf') else '500+'}"
                    length_dist[range_key] += 1
                    break

        stats["document_length_distribution"] = length_dist

        # Coverage statistics
        endpoint_docs = [
            doc for doc in search_index.documents if doc.type == "endpoint"
        ]
        schema_docs = [doc for doc in search_index.documents if doc.type == "schema"]
        security_docs = [
            doc for doc in search_index.documents if doc.type == "security"
        ]

        stats["coverage_statistics"] = {
            "endpoints": len(endpoint_docs),
            "schemas": len(schema_docs),
            "security_schemes": len(security_docs),
            "endpoints_with_operation_id": sum(
                1 for doc in endpoint_docs if doc.metadata.get("operation_id")
            ),
            "endpoints_with_description": sum(
                1 for doc in endpoint_docs if "description" in doc.content
            ),
            "deprecated_items": sum(
                1
                for doc in search_index.documents
                if doc.metadata.get("deprecated", False)
            ),
        }

        # Convert Counter to dict for JSON serialization
        stats["document_types"] = dict(stats["document_types"])

        return stats

    def optimize_search_performance(self, search_index: SearchIndex) -> SearchIndex:
        """Apply performance optimizations to search index.

        Args:
            search_index: Search index to optimize

        Returns:
            Optimized search index
        """
        # Remove very rare terms that appear in only 1 document
        # and are not in important terms
        rare_terms = set()
        for term, doc_count in search_index.document_frequencies.items():
            if doc_count == 1 and term not in self.important_terms:
                rare_terms.add(term)

        if rare_terms:
            self.logger.info(f"Removing {len(rare_terms)} rare terms from index")

            # Filter rare terms from vocabulary
            search_index.vocabulary -= rare_terms

            # Remove from document frequencies
            for term in rare_terms:
                del search_index.document_frequencies[term]

            # Remove from term frequencies
            for doc_id in search_index.term_frequencies:
                for term in rare_terms:
                    search_index.term_frequencies[doc_id].pop(term, None)

        # Limit vocabulary size if it's too large
        max_vocabulary_size = 10000
        if len(search_index.vocabulary) > max_vocabulary_size:
            # Keep most frequent terms
            sorted_terms = sorted(
                search_index.document_frequencies.items(),
                key=lambda x: x[1],
                reverse=True,
            )

            kept_terms = set(term for term, _ in sorted_terms[:max_vocabulary_size])
            # Always keep important terms
            kept_terms.update(self.important_terms & search_index.vocabulary)

            removed_terms = search_index.vocabulary - kept_terms

            self.logger.info(
                f"Reducing vocabulary from {len(search_index.vocabulary)} "
                f"to {len(kept_terms)} terms"
            )

            # Update index
            search_index.vocabulary = kept_terms

            for term in removed_terms:
                search_index.document_frequencies.pop(term, None)

            for doc_id in search_index.term_frequencies:
                for term in removed_terms:
                    search_index.term_frequencies[doc_id].pop(term, None)

        return search_index
