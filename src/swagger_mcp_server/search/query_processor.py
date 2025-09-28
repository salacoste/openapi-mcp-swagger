"""Advanced search query processing for the Swagger MCP Server.

This module provides sophisticated query processing capabilities including:
- Query preprocessing with stemming and normalization
- Multi-term boolean query support (AND, OR, NOT)
- Fuzzy matching for typo tolerance
- Field-specific search capabilities
- Query suggestions and auto-completion

Integrates with the existing Whoosh-based search infrastructure.
"""

import asyncio
import logging
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Dict, List, Optional, Set, Tuple, Union

# NLP libraries for query processing
try:
    import nltk
    from nltk.corpus import stopwords
    from nltk.stem import PorterStemmer
    from nltk.tokenize import word_tokenize

    NLTK_AVAILABLE = True
except ImportError:
    NLTK_AVAILABLE = False
    logging.warning(
        "NLTK not available. Advanced query processing will use basic processing."
    )

from whoosh.qparser import MultifieldParser, QueryParser
from whoosh.query import And, FuzzyTerm, Not, Or, Query, Term, Wildcard

from ..config.settings import SearchConfig


@dataclass
class ProcessedQuery:
    """Processed search query with extracted components."""

    original_query: str
    normalized_terms: List[str]
    field_filters: Dict[str, str]  # field:value pairs
    boolean_operators: Dict[str, List[str]]  # operator: terms
    fuzzy_terms: List[str]
    excluded_terms: List[str]
    query_type: str  # 'simple', 'boolean', 'field_specific', 'natural_language'
    enhanced_terms: List[str]  # Terms with synonyms and variations
    suggestions: List[str]  # Query suggestions for low-result scenarios


@dataclass
class QuerySuggestion:
    """Query suggestion with relevance score."""

    query: str
    description: str
    score: float
    category: str  # 'typo_fix', 'expansion', 'refinement', 'alternative'


class QueryProcessor:
    """Advanced query processing and normalization for search operations."""

    def __init__(self, config: SearchConfig):
        """Initialize the query processor.

        Args:
            config: Search configuration settings
        """
        self.config = config
        self.logger = logging.getLogger(__name__)

        # Initialize NLP components if available
        if NLTK_AVAILABLE:
            try:
                self.stemmer = PorterStemmer()
                self.stop_words = set(stopwords.words("english"))
            except Exception as e:
                self.logger.warning(f"Failed to initialize NLTK components: {e}")
                self.stemmer = None
                self.stop_words = set()
        else:
            self.stemmer = None
            self.stop_words = set()

        # Load API-specific terminology and synonyms
        self.api_terms = self._load_api_terminology()
        self.synonym_map = self._load_synonym_map()

        # Field-specific query patterns
        self.field_patterns = {
            "path": r"path:([^\s]+)",
            "method": r"method:([^\s]+)",
            "auth": r"auth:([^\s]+)",
            "param": r"param:([^\s]+)",
            "response": r"response:([^\s]+)",
            "status": r"status:([^\s]+)",
            "tag": r"tag:([^\s]+)",
            "type": r"type:([^\s]+)",
            "format": r"format:([^\s]+)",
        }

        # Boolean operator patterns
        self.boolean_patterns = {
            "and": r"\b(\w+)\s+AND\s+(\w+)\b",
            "or": r"\b(\w+)\s+OR\s+(\w+)\b",
            "not": r"\bNOT\s+(\w+)\b",
        }

    async def process_query(self, query: str) -> ProcessedQuery:
        """Process and enhance search query with advanced capabilities.

        Args:
            query: Raw search query string

        Returns:
            ProcessedQuery: Enhanced query with processed components

        Raises:
            ValueError: If query is empty or invalid
        """
        if not query or not query.strip():
            raise ValueError("Query cannot be empty")

        original_query = query.strip()

        try:
            # Step 1: Parse query structure and extract components
            field_filters = self._parse_field_queries(original_query)
            boolean_ops = self._parse_boolean_query(original_query)

            # Step 2: Clean and normalize the main query text
            clean_query = self._remove_special_syntax(original_query)
            normalized_terms = self._normalize_query_terms(clean_query)

            # Step 3: Determine query type
            query_type = self._determine_query_type(
                original_query, field_filters, boolean_ops
            )

            # Step 4: Apply fuzzy matching preparation
            fuzzy_terms = self._prepare_fuzzy_terms(normalized_terms)

            # Step 5: Generate query variations and expansions
            enhanced_terms = self._enhance_query_terms(normalized_terms)

            # Step 6: Extract excluded terms
            excluded_terms = boolean_ops.get("not", [])

            # Step 7: Generate initial suggestions (refined based on results later)
            suggestions = self._generate_base_suggestions(original_query)

            return ProcessedQuery(
                original_query=original_query,
                normalized_terms=normalized_terms,
                field_filters=field_filters,
                boolean_operators=boolean_ops,
                fuzzy_terms=fuzzy_terms,
                excluded_terms=excluded_terms,
                query_type=query_type,
                enhanced_terms=enhanced_terms,
                suggestions=suggestions,
            )

        except Exception as e:
            self.logger.error(f"Query processing failed for '{query}': {e}")
            # Return basic processed query on failure
            return ProcessedQuery(
                original_query=original_query,
                normalized_terms=[query.lower()],
                field_filters={},
                boolean_operators={},
                fuzzy_terms=[],
                excluded_terms=[],
                query_type="simple",
                enhanced_terms=[query.lower()],
                suggestions=[],
            )

    def generate_whoosh_query(
        self, processed_query: ProcessedQuery, schema_fields: List[str]
    ) -> Query:
        """Generate Whoosh Query object from processed query.

        Args:
            processed_query: Processed query components
            schema_fields: Available schema fields for search

        Returns:
            Query: Whoosh query object ready for execution
        """
        try:
            queries = []

            # Handle field-specific queries
            for field, value in processed_query.field_filters.items():
                if field in schema_fields:
                    queries.append(Term(field, value))

            # Handle boolean operations
            if processed_query.boolean_operators:
                bool_query = self._build_boolean_query(
                    processed_query.boolean_operators, schema_fields
                )
                if bool_query:
                    queries.append(bool_query)

            # Handle main search terms
            if processed_query.enhanced_terms:
                main_query = self._build_main_query(
                    processed_query.enhanced_terms, schema_fields
                )
                if main_query:
                    queries.append(main_query)

            # Handle fuzzy terms if no exact matches expected
            if processed_query.fuzzy_terms and not queries:
                fuzzy_query = self._build_fuzzy_query(
                    processed_query.fuzzy_terms, schema_fields
                )
                if fuzzy_query:
                    queries.append(fuzzy_query)

            # Handle excluded terms
            if processed_query.excluded_terms:
                for term in processed_query.excluded_terms:
                    exclusion = Or(
                        [
                            Term(field, term)
                            for field in schema_fields
                            if field in ["endpoint_path", "summary", "description"]
                        ]
                    )
                    if exclusion:
                        queries.append(Not(exclusion))

            # Combine all queries
            if len(queries) == 1:
                return queries[0]
            elif len(queries) > 1:
                return And(queries)
            else:
                # Fallback to simple term search
                return Term("description", processed_query.original_query.lower())

        except Exception as e:
            self.logger.error(f"Whoosh query generation failed: {e}")
            # Fallback to simple search
            return Term("description", processed_query.original_query.lower())

    async def generate_query_suggestions(
        self,
        query: str,
        result_count: int,
        available_terms: Optional[Set[str]] = None,
    ) -> List[QuerySuggestion]:
        """Generate query suggestions based on search context.

        Args:
            query: Original search query
            result_count: Number of results returned
            available_terms: Set of available terms from index

        Returns:
            List[QuerySuggestion]: Ordered list of query suggestions
        """
        suggestions = []

        try:
            if result_count == 0:
                # No results - suggest alternatives
                suggestions.extend(self._suggest_typo_fixes(query, available_terms))
                suggestions.extend(self._suggest_broader_queries(query))
                suggestions.extend(self._suggest_similar_terms(query, available_terms))

            elif result_count < 5:
                # Few results - suggest refinements
                suggestions.extend(self._suggest_query_refinements(query))
                suggestions.extend(self._suggest_field_specific_queries(query))

            elif result_count > 50:
                # Too many results - suggest narrowing
                suggestions.extend(self._suggest_narrowing_queries(query))

            # Add general API pattern suggestions
            suggestions.extend(self._suggest_api_patterns(query))

            # Sort by score and return top suggestions
            suggestions.sort(key=lambda x: x.score, reverse=True)
            return suggestions[:5]

        except Exception as e:
            self.logger.error(f"Query suggestion generation failed: {e}")
            return []

    # Private methods for query processing

    def _parse_field_queries(self, query: str) -> Dict[str, str]:
        """Parse field-specific query components."""
        field_filters = {}

        for field, pattern in self.field_patterns.items():
            matches = re.findall(pattern, query, re.IGNORECASE)
            if matches:
                field_filters[field] = matches[0]

        return field_filters

    def _parse_boolean_query(self, query: str) -> Dict[str, List[str]]:
        """Parse boolean operators and extract associated terms."""
        boolean_ops = {"and": [], "or": [], "not": []}

        # Handle NOT operations
        not_matches = re.findall(r"\bNOT\s+(\w+)", query, re.IGNORECASE)
        boolean_ops["not"] = not_matches

        # Handle AND operations
        and_matches = re.findall(r"(\w+)\s+AND\s+(\w+)", query, re.IGNORECASE)
        for match in and_matches:
            boolean_ops["and"].extend(match)

        # Handle OR operations
        or_matches = re.findall(r"(\w+)\s+OR\s+(\w+)", query, re.IGNORECASE)
        for match in or_matches:
            boolean_ops["or"].extend(match)

        return boolean_ops

    def _remove_special_syntax(self, query: str) -> str:
        """Remove field-specific and boolean syntax from query."""
        clean_query = query

        # Remove field-specific syntax
        for pattern in self.field_patterns.values():
            clean_query = re.sub(pattern, "", clean_query, flags=re.IGNORECASE)

        # Remove boolean operators
        clean_query = re.sub(r"\b(AND|OR|NOT)\b", " ", clean_query, flags=re.IGNORECASE)

        # Clean up whitespace
        clean_query = re.sub(r"\s+", " ", clean_query).strip()

        return clean_query

    def _normalize_query_terms(self, query: str) -> List[str]:
        """Normalize and tokenize query terms."""
        if not query:
            return []

        # Tokenize
        if NLTK_AVAILABLE and hasattr(self, "stemmer"):
            try:
                tokens = word_tokenize(query.lower())
            except:
                tokens = query.lower().split()
        else:
            tokens = query.lower().split()

        # Remove stopwords and apply stemming
        normalized = []
        for token in tokens:
            # Skip stopwords
            if token in self.stop_words:
                continue

            # Apply stemming if available
            if self.stemmer:
                try:
                    stemmed = self.stemmer.stem(token)
                    normalized.append(stemmed)
                except:
                    normalized.append(token)
            else:
                normalized.append(token)

        return normalized

    def _determine_query_type(
        self,
        query: str,
        field_filters: Dict[str, str],
        boolean_ops: Dict[str, List[str]],
    ) -> str:
        """Determine the type of query for processing optimization."""
        if field_filters:
            return "field_specific"
        elif any(boolean_ops.values()):
            return "boolean"
        elif len(query.split()) > 3:
            return "natural_language"
        else:
            return "simple"

    def _prepare_fuzzy_terms(self, terms: List[str]) -> List[str]:
        """Prepare terms for fuzzy matching."""
        # Only apply fuzzy matching to terms longer than 3 characters
        return [term for term in terms if len(term) > 3]

    def _enhance_query_terms(self, terms: List[str]) -> List[str]:
        """Enhance query terms with synonyms and variations."""
        enhanced_terms = []

        for term in terms:
            # Add original term
            enhanced_terms.append(term)

            # Add synonyms
            synonyms = self.synonym_map.get(term, [])
            enhanced_terms.extend(synonyms)

            # Add API-specific variations
            api_variants = self._get_api_variations(term)
            enhanced_terms.extend(api_variants)

        return list(set(enhanced_terms))  # Remove duplicates

    def _load_api_terminology(self) -> Set[str]:
        """Load API-specific terminology and common patterns."""
        return {
            "endpoint",
            "api",
            "rest",
            "http",
            "json",
            "xml",
            "authentication",
            "authorization",
            "bearer",
            "oauth",
            "get",
            "post",
            "put",
            "delete",
            "patch",
            "head",
            "options",
            "user",
            "customer",
            "account",
            "profile",
            "session",
            "create",
            "read",
            "update",
            "delete",
            "crud",
            "list",
            "fetch",
            "retrieve",
            "search",
            "filter",
            "pagination",
            "limit",
            "offset",
            "page",
            "size",
            "error",
            "exception",
            "validation",
            "response",
            "request",
            "header",
            "parameter",
            "body",
            "payload",
        }

    def _load_synonym_map(self) -> Dict[str, List[str]]:
        """Load synonym mappings for API terminology."""
        return {
            "user": ["customer", "account", "profile", "member"],
            "auth": ["authentication", "authorization", "login", "signin"],
            "get": ["retrieve", "fetch", "read", "find"],
            "post": ["create", "add", "insert", "new"],
            "put": ["update", "modify", "edit", "change"],
            "delete": ["remove", "destroy", "drop"],
            "list": ["index", "all", "collection"],
            "search": ["find", "query", "filter", "lookup"],
            "error": ["exception", "failure", "issue"],
            "param": ["parameter", "argument", "field"],
            "response": ["result", "output", "return"],
            "request": ["input", "call", "invoke"],
        }

    def _get_api_variations(self, term: str) -> List[str]:
        """Get API-specific variations of a term."""
        variations = []

        # Handle plural/singular
        if term.endswith("s") and len(term) > 3:
            variations.append(term[:-1])  # Remove 's'
        else:
            variations.append(term + "s")  # Add 's'

        # Handle common API suffixes
        if term.endswith("_id"):
            variations.append(term[:-3])
        elif not term.endswith("_id") and term in self.api_terms:
            variations.append(term + "_id")

        return variations

    def _build_boolean_query(
        self, boolean_ops: Dict[str, List[str]], schema_fields: List[str]
    ) -> Optional[Query]:
        """Build Whoosh boolean query from parsed operators."""
        queries = []

        # Handle AND operations (all terms must be present)
        if boolean_ops.get("and"):
            and_queries = []
            for term in boolean_ops["and"]:
                term_queries = [
                    Term(field, term)
                    for field in schema_fields
                    if field in ["endpoint_path", "summary", "description"]
                ]
                if term_queries:
                    and_queries.append(Or(term_queries))
            if and_queries:
                queries.append(And(and_queries))

        # Handle OR operations (any term can be present)
        if boolean_ops.get("or"):
            or_queries = []
            for term in boolean_ops["or"]:
                term_queries = [
                    Term(field, term)
                    for field in schema_fields
                    if field in ["endpoint_path", "summary", "description"]
                ]
                or_queries.extend(term_queries)
            if or_queries:
                queries.append(Or(or_queries))

        return And(queries) if len(queries) > 1 else (queries[0] if queries else None)

    def _build_main_query(
        self, terms: List[str], schema_fields: List[str]
    ) -> Optional[Query]:
        """Build main content query from enhanced terms."""
        if not terms:
            return None

        # Create multifield search across main content fields
        content_fields = [
            field
            for field in schema_fields
            if field
            in [
                "endpoint_path",
                "summary",
                "description",
                "parameters",
                "tags",
            ]
        ]

        term_queries = []
        for term in terms:
            field_queries = [Term(field, term) for field in content_fields]
            if field_queries:
                term_queries.append(Or(field_queries))

        return (
            And(term_queries)
            if len(term_queries) > 1
            else (term_queries[0] if term_queries else None)
        )

    def _build_fuzzy_query(
        self, fuzzy_terms: List[str], schema_fields: List[str]
    ) -> Optional[Query]:
        """Build fuzzy query for typo tolerance."""
        if not fuzzy_terms:
            return None

        fuzzy_queries = []
        content_fields = ["endpoint_path", "summary", "description"]

        for term in fuzzy_terms:
            for field in content_fields:
                if field in schema_fields:
                    # Use FuzzyTerm with edit distance of 1-2
                    fuzzy_queries.append(FuzzyTerm(field, term, maxdist=2))

        return Or(fuzzy_queries) if fuzzy_queries else None

    def _generate_base_suggestions(self, query: str) -> List[str]:
        """Generate base query suggestions."""
        suggestions = []

        # Add common API patterns
        api_patterns = [
            "path:users",
            "method:GET",
            "auth:bearer",
            "param:id",
            "response:json",
            "status:200",
        ]

        for pattern in api_patterns:
            if pattern.split(":")[1] in query.lower():
                suggestions.append(pattern)

        return suggestions[:3]

    # Suggestion generation methods

    def _suggest_typo_fixes(
        self, query: str, available_terms: Optional[Set[str]]
    ) -> List[QuerySuggestion]:
        """Suggest typo fixes based on available terms."""
        suggestions = []

        if not available_terms:
            return suggestions

        query_terms = query.lower().split()

        for term in query_terms:
            if len(term) > 3:  # Only check longer terms
                for available_term in available_terms:
                    similarity = SequenceMatcher(None, term, available_term).ratio()
                    if 0.7 <= similarity < 1.0:  # Potential typo fix
                        fixed_query = query.replace(term, available_term)
                        suggestions.append(
                            QuerySuggestion(
                                query=fixed_query,
                                description=f"Did you mean '{available_term}'?",
                                score=similarity,
                                category="typo_fix",
                            )
                        )

        return suggestions[:2]

    def _suggest_broader_queries(self, query: str) -> List[QuerySuggestion]:
        """Suggest broader query alternatives."""
        suggestions = []

        # Remove specific terms to broaden search
        terms = query.split()
        if len(terms) > 1:
            for i, term in enumerate(terms):
                broader_terms = terms[:i] + terms[i + 1 :]
                broader_query = " ".join(broader_terms)
                suggestions.append(
                    QuerySuggestion(
                        query=broader_query,
                        description=f"Try searching for '{broader_query}'",
                        score=0.6,
                        category="expansion",
                    )
                )

        return suggestions[:2]

    def _suggest_similar_terms(
        self, query: str, available_terms: Optional[Set[str]]
    ) -> List[QuerySuggestion]:
        """Suggest similar terms from the index."""
        suggestions = []

        if not available_terms:
            return suggestions

        # Find terms that contain query as substring
        query_lower = query.lower()
        for term in available_terms:
            if query_lower in term and query_lower != term:
                suggestions.append(
                    QuerySuggestion(
                        query=term,
                        description=f"Try '{term}'",
                        score=0.5,
                        category="alternative",
                    )
                )

        return suggestions[:2]

    def _suggest_query_refinements(self, query: str) -> List[QuerySuggestion]:
        """Suggest query refinements for better results."""
        suggestions = []

        # Suggest adding field-specific filters
        field_suggestions = [
            ("method:GET", "Search only GET endpoints"),
            ("method:POST", "Search only POST endpoints"),
            ("auth:bearer", "Search only authenticated endpoints"),
            ("response:json", "Search only JSON responses"),
        ]

        for field_query, description in field_suggestions:
            combined_query = f"{query} {field_query}"
            suggestions.append(
                QuerySuggestion(
                    query=combined_query,
                    description=description,
                    score=0.4,
                    category="refinement",
                )
            )

        return suggestions[:2]

    def _suggest_field_specific_queries(self, query: str) -> List[QuerySuggestion]:
        """Suggest field-specific query alternatives."""
        suggestions = []

        # Check if query might be a path
        if "/" in query or query.startswith("/"):
            suggestions.append(
                QuerySuggestion(
                    query=f"path:{query}",
                    description="Search in endpoint paths specifically",
                    score=0.7,
                    category="refinement",
                )
            )

        # Check if query might be an HTTP method
        if query.upper() in ["GET", "POST", "PUT", "DELETE", "PATCH"]:
            suggestions.append(
                QuerySuggestion(
                    query=f"method:{query.upper()}",
                    description=f"Search only {query.upper()} endpoints",
                    score=0.8,
                    category="refinement",
                )
            )

        return suggestions

    def _suggest_narrowing_queries(self, query: str) -> List[QuerySuggestion]:
        """Suggest ways to narrow down broad queries."""
        suggestions = []

        # Suggest adding specific requirements
        narrowing_filters = [
            ("method:GET", "Show only GET endpoints"),
            ("auth:required", "Show only authenticated endpoints"),
            ("deprecated:false", "Hide deprecated endpoints"),
        ]

        for filter_query, description in narrowing_filters:
            combined_query = f"{query} {filter_query}"
            suggestions.append(
                QuerySuggestion(
                    query=combined_query,
                    description=description,
                    score=0.5,
                    category="refinement",
                )
            )

        return suggestions[:2]

    def _suggest_api_patterns(self, query: str) -> List[QuerySuggestion]:
        """Suggest common API pattern queries."""
        suggestions = []

        patterns = {
            "user": ["path:users", "param:user_id", "tag:user"],
            "auth": ["auth:bearer", "tag:authentication", "path:auth"],
            "list": ["method:GET", "param:limit", "param:offset"],
            "create": ["method:POST", "response:201"],
            "update": ["method:PUT", "method:PATCH"],
            "delete": ["method:DELETE", "response:204"],
        }

        query_lower = query.lower()
        for keyword, pattern_list in patterns.items():
            if keyword in query_lower:
                for pattern in pattern_list[:1]:  # Only suggest one pattern per keyword
                    suggestions.append(
                        QuerySuggestion(
                            query=f"{query} {pattern}",
                            description=f"Refine search with {pattern}",
                            score=0.3,
                            category="refinement",
                        )
                    )

        return suggestions[:1]
