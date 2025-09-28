"""Search usage analytics and pattern recognition for the Swagger MCP Server.

This module provides advanced analytics for search usage patterns, user behavior,
and search effectiveness optimization as specified in Story 3.6.
"""

import asyncio
import json
import re
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

from .performance_monitor import SearchAnalytics


class QueryPatternType(Enum):
    """Types of query patterns identified in search analytics."""

    EXACT_MATCH = "exact_match"
    PARTIAL_MATCH = "partial_match"
    WILDCARD = "wildcard"
    BOOLEAN = "boolean"
    FILTER_HEAVY = "filter_heavy"
    COMPLEX_QUERY = "complex_query"
    SIMPLE_QUERY = "simple_query"


class UserBehaviorPattern(Enum):
    """User behavior patterns identified from search analytics."""

    EXPLORER = "explorer"  # Diverse queries, many filters
    SEARCHER = "searcher"  # Specific searches, few results clicked
    BROWSER = "browser"  # General queries, many results viewed
    FOCUSED = "focused"  # Specific domain, repeated patterns
    ITERATIVE = "iterative"  # Query refinement patterns


@dataclass
class QueryPattern:
    """Represents an identified query pattern."""

    pattern_type: QueryPatternType
    pattern_text: str
    frequency: int
    avg_response_time: float
    success_rate: float
    common_variations: List[str] = field(default_factory=list)
    associated_filters: Dict[str, int] = field(default_factory=dict)
    optimization_potential: str = "low"  # low, medium, high


@dataclass
class UserSession:
    """Represents a user search session."""

    session_id: str
    start_time: datetime
    end_time: Optional[datetime]
    queries: List[SearchAnalytics] = field(default_factory=list)
    behavior_pattern: Optional[UserBehaviorPattern] = None
    satisfaction_score: Optional[float] = None
    conversion_achieved: bool = False  # Whether user found what they needed


@dataclass
class SearchEffectivenessMetrics:
    """Metrics for measuring search effectiveness."""

    relevance_score: float
    user_engagement: float
    query_success_rate: float
    time_to_success: Optional[float]
    abandonment_rate: float
    refinement_rate: float


class SearchAnalyticsEngine:
    """Advanced analytics engine for search usage patterns and optimization."""

    def __init__(self):
        """Initialize the search analytics engine."""
        self.query_patterns: Dict[str, QueryPattern] = {}
        self.user_sessions: Dict[str, UserSession] = {}
        self.effectiveness_metrics: Dict[str, SearchEffectivenessMetrics] = {}

        # Pattern recognition settings
        self.min_pattern_frequency = 3
        self.session_timeout = timedelta(minutes=30)
        self.common_stop_words = {
            "the",
            "a",
            "an",
            "and",
            "or",
            "but",
            "in",
            "on",
            "at",
            "to",
            "for",
            "of",
            "with",
            "by",
            "from",
            "up",
            "about",
            "into",
            "through",
            "during",
        }

    async def analyze_search_patterns(
        self, analytics_data: List[SearchAnalytics]
    ) -> Dict[str, Any]:
        """Analyze search patterns from analytics data.

        Args:
            analytics_data: List of search analytics records

        Returns:
            Dict containing pattern analysis results
        """
        if not analytics_data:
            return {"patterns": [], "insights": {}, "recommendations": []}

        # Identify query patterns
        query_patterns = await self._identify_query_patterns(analytics_data)

        # Analyze user sessions
        user_sessions = await self._analyze_user_sessions(analytics_data)

        # Calculate search effectiveness
        effectiveness = await self._calculate_search_effectiveness(analytics_data)

        # Generate insights
        insights = await self._generate_pattern_insights(
            query_patterns, user_sessions, effectiveness
        )

        # Generate optimization recommendations
        recommendations = await self._generate_pattern_recommendations(insights)

        return {
            "query_patterns": [self._pattern_to_dict(p) for p in query_patterns],
            "user_behavior": self._sessions_to_summary(user_sessions),
            "effectiveness_metrics": self._effectiveness_to_dict(effectiveness),
            "insights": insights,
            "recommendations": recommendations,
            "analysis_timestamp": datetime.now().isoformat(),
        }

    async def _identify_query_patterns(
        self, analytics_data: List[SearchAnalytics]
    ) -> List[QueryPattern]:
        """Identify common query patterns from search data."""
        patterns = []

        # Group queries by normalized text
        query_groups = defaultdict(list)
        for analytics in analytics_data:
            normalized_query = self._normalize_query_text(analytics.query_text)
            query_groups[normalized_query].append(analytics)

        # Analyze each query group
        for query_text, query_analytics in query_groups.items():
            if len(query_analytics) >= self.min_pattern_frequency:
                pattern = await self._analyze_query_group(query_text, query_analytics)
                if pattern:
                    patterns.append(pattern)

        # Sort by frequency and success rate
        patterns.sort(key=lambda p: (p.frequency, p.success_rate), reverse=True)

        return patterns

    async def _analyze_query_group(
        self, query_text: str, analytics_list: List[SearchAnalytics]
    ) -> Optional[QueryPattern]:
        """Analyze a group of similar queries to identify patterns."""
        if not analytics_list:
            return None

        # Calculate metrics
        frequency = len(analytics_list)
        avg_response_time = statistics.mean(
            [a.total_response_time for a in analytics_list]
        )
        success_rate = (
            len([a for a in analytics_list if a.result_count > 0]) / frequency
        )

        # Classify pattern type
        pattern_type = self._classify_query_pattern(query_text, analytics_list)

        # Find common variations
        variations = self._find_query_variations(analytics_list)

        # Analyze associated filters
        filter_usage = defaultdict(int)
        for analytics in analytics_list:
            for filter_key in analytics.filters_applied.keys():
                filter_usage[filter_key] += 1

        # Determine optimization potential
        optimization_potential = self._assess_optimization_potential(
            pattern_type, avg_response_time, success_rate, frequency
        )

        return QueryPattern(
            pattern_type=pattern_type,
            pattern_text=query_text,
            frequency=frequency,
            avg_response_time=avg_response_time,
            success_rate=success_rate,
            common_variations=variations,
            associated_filters=dict(filter_usage),
            optimization_potential=optimization_potential,
        )

    def _classify_query_pattern(
        self, query_text: str, analytics_list: List[SearchAnalytics]
    ) -> QueryPatternType:
        """Classify the type of query pattern."""
        # Analyze query characteristics
        has_wildcards = "*" in query_text or "?" in query_text
        has_boolean = any(op in query_text.lower() for op in ["and", "or", "not"])
        word_count = len(query_text.split())

        # Analyze filter usage
        avg_filters = statistics.mean([len(a.filters_applied) for a in analytics_list])

        # Classify based on characteristics
        if has_wildcards:
            return QueryPatternType.WILDCARD
        elif has_boolean:
            return QueryPatternType.BOOLEAN
        elif avg_filters > 2:
            return QueryPatternType.FILTER_HEAVY
        elif word_count > 5:
            return QueryPatternType.COMPLEX_QUERY
        elif word_count == 1:
            return QueryPatternType.SIMPLE_QUERY
        else:
            # Check for exact vs partial matching based on results
            avg_results = statistics.mean([a.result_count for a in analytics_list])
            if avg_results < 5:
                return QueryPatternType.EXACT_MATCH
            else:
                return QueryPatternType.PARTIAL_MATCH

    def _find_query_variations(
        self, analytics_list: List[SearchAnalytics]
    ) -> List[str]:
        """Find common variations of the query."""
        query_texts = [a.query_text for a in analytics_list]
        unique_queries = list(set(query_texts))

        # If all queries are identical, no variations
        if len(unique_queries) <= 1:
            return []

        # Return most common variations (up to 5)
        query_counter = Counter(query_texts)
        common_variations = [
            query for query, count in query_counter.most_common(5) if count > 1
        ]

        return common_variations

    def _assess_optimization_potential(
        self,
        pattern_type: QueryPatternType,
        avg_response_time: float,
        success_rate: float,
        frequency: int,
    ) -> str:
        """Assess optimization potential for a query pattern."""
        # High potential: frequent queries with poor performance or low success
        if frequency > 10 and (avg_response_time > 200 or success_rate < 0.5):
            return "high"

        # Medium potential: moderately frequent with some issues
        if frequency > 5 and (avg_response_time > 150 or success_rate < 0.7):
            return "medium"

        # High potential for specific pattern types
        if pattern_type in [
            QueryPatternType.COMPLEX_QUERY,
            QueryPatternType.FILTER_HEAVY,
        ]:
            return "medium"

        return "low"

    async def _analyze_user_sessions(
        self, analytics_data: List[SearchAnalytics]
    ) -> List[UserSession]:
        """Analyze user sessions from search analytics."""
        sessions = {}

        # Group analytics by session
        for analytics in analytics_data:
            session_id = (
                analytics.user_session or f"anonymous_{analytics.correlation_id[:8]}"
            )

            if session_id not in sessions:
                sessions[session_id] = UserSession(
                    session_id=session_id,
                    start_time=analytics.timestamp,
                    end_time=analytics.timestamp,
                )

            session = sessions[session_id]
            session.queries.append(analytics)

            # Update session time bounds
            if analytics.timestamp < session.start_time:
                session.start_time = analytics.timestamp
            if analytics.timestamp > session.end_time:
                session.end_time = analytics.timestamp

        # Analyze each session
        analyzed_sessions = []
        for session in sessions.values():
            if len(session.queries) > 0:  # Only include sessions with queries
                session.behavior_pattern = self._classify_user_behavior(session)
                session.satisfaction_score = self._calculate_session_satisfaction(
                    session
                )
                session.conversion_achieved = self._assess_session_conversion(session)
                analyzed_sessions.append(session)

        return analyzed_sessions

    def _classify_user_behavior(self, session: UserSession) -> UserBehaviorPattern:
        """Classify user behavior pattern from session data."""
        queries = session.queries

        if not queries:
            return UserBehaviorPattern.BROWSER

        # Calculate behavior metrics
        query_diversity = len(set(q.query_text for q in queries)) / len(queries)
        avg_filters = statistics.mean([len(q.filters_applied) for q in queries])
        avg_results_clicked = statistics.mean([len(q.results_clicked) for q in queries])

        # Query refinement pattern (similar queries with variations)
        refinement_count = 0
        for i in range(1, len(queries)):
            if self._are_queries_similar(
                queries[i - 1].query_text, queries[i].query_text
            ):
                refinement_count += 1
        refinement_rate = refinement_count / max(len(queries) - 1, 1)

        # Classify based on metrics
        if refinement_rate > 0.5:
            return UserBehaviorPattern.ITERATIVE
        elif query_diversity < 0.3:  # Similar queries
            return UserBehaviorPattern.FOCUSED
        elif avg_filters > 2:
            return UserBehaviorPattern.EXPLORER
        elif avg_results_clicked < 1:
            return UserBehaviorPattern.SEARCHER
        else:
            return UserBehaviorPattern.BROWSER

    def _are_queries_similar(self, query1: str, query2: str) -> bool:
        """Check if two queries are similar (potential refinement)."""
        words1 = set(self._normalize_query_text(query1).split())
        words2 = set(self._normalize_query_text(query2).split())

        # Remove stop words
        words1 = words1 - self.common_stop_words
        words2 = words2 - self.common_stop_words

        if not words1 or not words2:
            return False

        # Calculate Jaccard similarity
        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))

        return intersection / union > 0.5

    def _calculate_session_satisfaction(self, session: UserSession) -> float:
        """Calculate estimated satisfaction score for a session."""
        queries = session.queries

        if not queries:
            return 0.0

        satisfaction_factors = []

        # Factor 1: Search success rate
        successful_queries = len([q for q in queries if q.result_count > 0])
        success_rate = successful_queries / len(queries)
        satisfaction_factors.append(success_rate * 0.4)  # 40% weight

        # Factor 2: Result interaction
        avg_clicks = statistics.mean([len(q.results_clicked) for q in queries])
        click_factor = min(avg_clicks / 2, 1.0)  # Normalize to 0-1
        satisfaction_factors.append(click_factor * 0.3)  # 30% weight

        # Factor 3: Query abandonment (inverse)
        abandonment_rate = len([q for q in queries if q.query_abandoned]) / len(queries)
        abandonment_factor = 1.0 - abandonment_rate
        satisfaction_factors.append(abandonment_factor * 0.2)  # 20% weight

        # Factor 4: Response time satisfaction
        avg_response_time = statistics.mean([q.total_response_time for q in queries])
        time_factor = max(
            0, 1.0 - (avg_response_time - 100) / 300
        )  # Good < 100ms, Poor > 400ms
        satisfaction_factors.append(time_factor * 0.1)  # 10% weight

        return sum(satisfaction_factors)

    def _assess_session_conversion(self, session: UserSession) -> bool:
        """Assess whether user achieved their goal in the session."""
        queries = session.queries

        if not queries:
            return False

        # Indicators of successful conversion
        indicators = []

        # 1. Final query had results and user clicked on them
        final_query = queries[-1]
        if final_query.result_count > 0 and len(final_query.results_clicked) > 0:
            indicators.append(True)
        else:
            indicators.append(False)

        # 2. User didn't abandon their final search
        indicators.append(not final_query.query_abandoned)

        # 3. Session showed progression (iterative refinement leading to success)
        if len(queries) > 1:
            progression_score = 0
            for i in range(1, len(queries)):
                if queries[i].result_count > queries[i - 1].result_count:
                    progression_score += 1
            progression_indicator = progression_score > 0
            indicators.append(progression_indicator)

        # Conversion achieved if majority of indicators are positive
        return sum(indicators) > len(indicators) / 2

    async def _calculate_search_effectiveness(
        self, analytics_data: List[SearchAnalytics]
    ) -> SearchEffectivenessMetrics:
        """Calculate overall search effectiveness metrics."""
        if not analytics_data:
            return SearchEffectivenessMetrics(
                relevance_score=0,
                user_engagement=0,
                query_success_rate=0,
                time_to_success=None,
                abandonment_rate=0,
                refinement_rate=0,
            )

        # Relevance score (based on result interaction)
        total_clicks = sum(len(a.results_clicked) for a in analytics_data)
        total_results = sum(a.result_count for a in analytics_data)
        relevance_score = total_clicks / max(total_results, 1)

        # User engagement (average clicks per query)
        user_engagement = total_clicks / len(analytics_data)

        # Query success rate
        successful_queries = len([a for a in analytics_data if a.result_count > 0])
        query_success_rate = successful_queries / len(analytics_data)

        # Time to success (average time for successful queries)
        successful_times = [
            a.total_response_time for a in analytics_data if a.result_count > 0
        ]
        time_to_success = (
            statistics.mean(successful_times) if successful_times else None
        )

        # Abandonment rate
        abandoned_queries = len([a for a in analytics_data if a.query_abandoned])
        abandonment_rate = abandoned_queries / len(analytics_data)

        # Refinement rate (estimated from query patterns)
        refinement_rate = self._calculate_refinement_rate(analytics_data)

        return SearchEffectivenessMetrics(
            relevance_score=relevance_score,
            user_engagement=user_engagement,
            query_success_rate=query_success_rate,
            time_to_success=time_to_success,
            abandonment_rate=abandonment_rate,
            refinement_rate=refinement_rate,
        )

    def _calculate_refinement_rate(
        self, analytics_data: List[SearchAnalytics]
    ) -> float:
        """Calculate the rate at which users refine their queries."""
        # Group by session and look for query refinements
        session_groups = defaultdict(list)
        for analytics in analytics_data:
            session_id = (
                analytics.user_session or f"anonymous_{analytics.correlation_id[:8]}"
            )
            session_groups[session_id].append(analytics)

        refinement_sessions = 0
        total_sessions = 0

        for session_queries in session_groups.values():
            if len(session_queries) > 1:
                total_sessions += 1
                # Sort by timestamp
                sorted_queries = sorted(session_queries, key=lambda x: x.timestamp)

                # Check for refinements
                for i in range(1, len(sorted_queries)):
                    if self._are_queries_similar(
                        sorted_queries[i - 1].query_text,
                        sorted_queries[i].query_text,
                    ):
                        refinement_sessions += 1
                        break

        return refinement_sessions / max(total_sessions, 1)

    async def _generate_pattern_insights(
        self,
        query_patterns: List[QueryPattern],
        user_sessions: List[UserSession],
        effectiveness: SearchEffectivenessMetrics,
    ) -> Dict[str, Any]:
        """Generate insights from pattern analysis."""
        insights = {
            "top_patterns": [],
            "user_behavior_distribution": {},
            "effectiveness_assessment": "",
            "key_findings": [],
            "improvement_opportunities": [],
        }

        # Top patterns by frequency and optimization potential
        high_value_patterns = [
            p
            for p in query_patterns
            if p.optimization_potential in ["high", "medium"] or p.frequency > 10
        ]
        insights["top_patterns"] = [
            self._pattern_to_dict(p) for p in high_value_patterns[:10]
        ]

        # User behavior distribution
        behavior_counts = Counter(
            s.behavior_pattern.value for s in user_sessions if s.behavior_pattern
        )
        insights["user_behavior_distribution"] = dict(behavior_counts)

        # Effectiveness assessment
        if effectiveness.query_success_rate > 0.8:
            insights["effectiveness_assessment"] = "excellent"
        elif effectiveness.query_success_rate > 0.6:
            insights["effectiveness_assessment"] = "good"
        elif effectiveness.query_success_rate > 0.4:
            insights["effectiveness_assessment"] = "fair"
        else:
            insights["effectiveness_assessment"] = "poor"

        # Key findings
        findings = []

        if effectiveness.abandonment_rate > 0.3:
            findings.append(
                f"High abandonment rate ({effectiveness.abandonment_rate:.1%}) indicates search frustration"
            )

        if effectiveness.refinement_rate > 0.4:
            findings.append(
                f"High refinement rate ({effectiveness.refinement_rate:.1%}) suggests initial queries are not effective"
            )

        if (
            len([p for p in query_patterns if p.success_rate < 0.5])
            > len(query_patterns) * 0.2
        ):
            findings.append(
                "Multiple query patterns have low success rates, indicating relevance issues"
            )

        if effectiveness.user_engagement < 0.5:
            findings.append(
                f"Low user engagement ({effectiveness.user_engagement:.1f} clicks/query) suggests poor result relevance"
            )

        insights["key_findings"] = findings

        # Improvement opportunities
        opportunities = []

        # High-frequency, low-success patterns
        problem_patterns = [
            p for p in query_patterns if p.frequency > 5 and p.success_rate < 0.6
        ]
        if problem_patterns:
            opportunities.append(
                {
                    "type": "query_optimization",
                    "description": f"Optimize {len(problem_patterns)} high-frequency patterns with low success rates",
                    "impact": "high",
                    "patterns": [p.pattern_text for p in problem_patterns[:3]],
                }
            )

        # Slow patterns
        slow_patterns = [p for p in query_patterns if p.avg_response_time > 200]
        if slow_patterns:
            opportunities.append(
                {
                    "type": "performance_optimization",
                    "description": f"Improve performance for {len(slow_patterns)} slow query patterns",
                    "impact": "medium",
                    "avg_time": statistics.mean(
                        [p.avg_response_time for p in slow_patterns]
                    ),
                }
            )

        insights["improvement_opportunities"] = opportunities

        return insights

    async def _generate_pattern_recommendations(
        self, insights: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Generate actionable recommendations based on pattern insights."""
        recommendations = []

        # Recommendations based on effectiveness assessment
        effectiveness = insights.get("effectiveness_assessment", "fair")

        if effectiveness == "poor":
            recommendations.append(
                {
                    "priority": "critical",
                    "category": "search_relevance",
                    "title": "Improve Search Algorithm",
                    "description": "Low success rate indicates fundamental search algorithm issues",
                    "actions": [
                        "Review and improve search indexing strategy",
                        "Implement better query processing and matching algorithms",
                        "Add spell checking and query suggestion features",
                    ],
                    "expected_impact": "40-60% improvement in success rate",
                }
            )

        # Recommendations based on key findings
        findings = insights.get("key_findings", [])

        for finding in findings:
            if "abandonment" in finding.lower():
                recommendations.append(
                    {
                        "priority": "high",
                        "category": "user_experience",
                        "title": "Reduce Query Abandonment",
                        "description": "High abandonment rate indicates user frustration",
                        "actions": [
                            "Implement progressive search with instant results",
                            "Add search suggestions and auto-complete",
                            "Improve result presentation and relevance",
                        ],
                        "expected_impact": "20-30% reduction in abandonment rate",
                    }
                )

            elif "refinement" in finding.lower():
                recommendations.append(
                    {
                        "priority": "medium",
                        "category": "query_processing",
                        "title": "Improve Initial Query Effectiveness",
                        "description": "High refinement rate suggests poor initial query understanding",
                        "actions": [
                            "Implement query expansion and synonym handling",
                            "Add context-aware search suggestions",
                            "Improve natural language query processing",
                        ],
                        "expected_impact": "15-25% reduction in refinement rate",
                    }
                )

        # Recommendations based on improvement opportunities
        opportunities = insights.get("improvement_opportunities", [])

        for opportunity in opportunities:
            if opportunity["type"] == "query_optimization":
                recommendations.append(
                    {
                        "priority": "high",
                        "category": "pattern_optimization",
                        "title": "Optimize High-Frequency Query Patterns",
                        "description": f"Focus on {len(opportunity.get('patterns', []))} specific patterns",
                        "actions": [
                            "Create specialized indexes for common patterns",
                            "Implement caching for frequent queries",
                            "Optimize query processing for identified patterns",
                        ],
                        "patterns": opportunity.get("patterns", []),
                        "expected_impact": "30-50% improvement for targeted patterns",
                    }
                )

        # Sort by priority
        priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        recommendations.sort(key=lambda r: priority_order.get(r["priority"], 3))

        return recommendations

    def _normalize_query_text(self, query_text: str) -> str:
        """Normalize query text for pattern analysis."""
        # Convert to lowercase
        normalized = query_text.lower().strip()

        # Remove special characters except wildcards
        normalized = re.sub(r"[^\w\s*?]", " ", normalized)

        # Collapse multiple spaces
        normalized = re.sub(r"\s+", " ", normalized)

        return normalized

    def _pattern_to_dict(self, pattern: QueryPattern) -> Dict[str, Any]:
        """Convert QueryPattern to dictionary for JSON serialization."""
        return {
            "pattern_type": pattern.pattern_type.value,
            "pattern_text": pattern.pattern_text,
            "frequency": pattern.frequency,
            "avg_response_time": pattern.avg_response_time,
            "success_rate": pattern.success_rate,
            "common_variations": pattern.common_variations,
            "associated_filters": pattern.associated_filters,
            "optimization_potential": pattern.optimization_potential,
        }

    def _sessions_to_summary(self, sessions: List[UserSession]) -> Dict[str, Any]:
        """Convert user sessions to summary statistics."""
        if not sessions:
            return {"total_sessions": 0}

        behavior_distribution = Counter(
            s.behavior_pattern.value for s in sessions if s.behavior_pattern
        )
        avg_satisfaction = statistics.mean(
            [s.satisfaction_score for s in sessions if s.satisfaction_score is not None]
        )
        conversion_rate = len([s for s in sessions if s.conversion_achieved]) / len(
            sessions
        )
        avg_queries_per_session = statistics.mean([len(s.queries) for s in sessions])

        return {
            "total_sessions": len(sessions),
            "behavior_distribution": dict(behavior_distribution),
            "avg_satisfaction_score": avg_satisfaction,
            "conversion_rate": conversion_rate,
            "avg_queries_per_session": avg_queries_per_session,
            "session_duration_avg": self._calculate_avg_session_duration(sessions),
        }

    def _calculate_avg_session_duration(self, sessions: List[UserSession]) -> float:
        """Calculate average session duration in seconds."""
        durations = []
        for session in sessions:
            if session.end_time and session.start_time:
                duration = (session.end_time - session.start_time).total_seconds()
                durations.append(duration)

        return statistics.mean(durations) if durations else 0

    def _effectiveness_to_dict(
        self, effectiveness: SearchEffectivenessMetrics
    ) -> Dict[str, Any]:
        """Convert SearchEffectivenessMetrics to dictionary."""
        return {
            "relevance_score": effectiveness.relevance_score,
            "user_engagement": effectiveness.user_engagement,
            "query_success_rate": effectiveness.query_success_rate,
            "time_to_success": effectiveness.time_to_success,
            "abandonment_rate": effectiveness.abandonment_rate,
            "refinement_rate": effectiveness.refinement_rate,
        }
