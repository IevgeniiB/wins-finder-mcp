"""LLM-powered wins analysis and correlation engine using OpenRouter."""

import json
from typing import Dict, List, Any, Optional
from datetime import datetime
import logging

from openai import OpenAI
from wins_finder.database.models import WinsDatabase

logger = logging.getLogger(__name__)


class WinsAnalyzer:
    """LLM-powered analyzer for extracting and correlating wins from activity data."""

    def __init__(self, db: Optional[WinsDatabase] = None):
        self.db = db or WinsDatabase()
        self._client = None
        self._api_key = None

    def _initialize_from_env(self):
        """Initialize API key from environment variable."""
        import os

        self._api_key = os.getenv("OPENROUTER_API_KEY")
        self._client = None

    def analyze_wins(
        self,
        activity_data: Dict[str, Any],
        audience: str = "self",
        focus_areas: List[str] = None,
    ) -> Dict[str, Any]:
        """Analyze activity data to extract meaningful wins and correlations."""
        focus_areas = focus_areas or []

        # Let LLM handle both correlation discovery and win analysis
        if self._get_client():
            wins = self._llm_analyze_wins(activity_data, audience, focus_areas)
        else:
            logger.warning("No OpenRouter API key configured, using heuristic analysis")
            # Fallback to heuristic correlation + analysis
            correlations = self._correlate_activities(activity_data)
            wins = self._heuristic_analyze_wins(
                activity_data, correlations, audience, focus_areas
            )

        return wins

    def generate_report(
        self,
        wins_data: Dict[str, Any],
        format: str = "markdown",
        audience: str = "self",
    ) -> str:
        """Generate a formatted report from wins data."""
        if format == "markdown":
            return self._generate_markdown_report(wins_data, audience)
        elif format == "json":
            return json.dumps(wins_data, indent=2)
        elif format == "slack":
            return self._generate_slack_report(wins_data)
        else:
            raise ValueError(f"Unsupported format: {format}")

    def _correlate_activities(
        self, activity_data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Find correlations between activities across services."""
        correlations = []

        # Get all activities from all services
        all_activities = []
        for service, data in activity_data.items():
            if isinstance(data, dict) and "activities" in data:
                for activity in data["activities"]:
                    activity["service"] = service
                    all_activities.append(activity)

        # Simple time-based correlation (activities within same day)
        time_groups = self._group_by_time(all_activities)

        for date, activities in time_groups.items():
            if len(activities) > 1:
                # Find potential correlations
                correlation = self._analyze_time_group(activities)
                if correlation:
                    correlations.append(correlation)

        # Keyword-based correlation
        keyword_correlations = self._find_keyword_correlations(all_activities)
        correlations.extend(keyword_correlations)

        return correlations

    def _group_by_time(
        self, activities: List[Dict[str, Any]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Group activities by date."""
        groups = {}

        for activity in activities:
            created_at = activity.get("created_at")
            if created_at:
                try:
                    date = datetime.fromisoformat(
                        created_at.replace("Z", "+00:00")
                    ).date()
                    date_str = date.strftime("%Y-%m-%d")

                    if date_str not in groups:
                        groups[date_str] = []
                    groups[date_str].append(activity)
                except Exception as e:
                    logger.warning(f"Error parsing date {created_at}: {e}")

        return groups

    def _analyze_time_group(
        self, activities: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """Analyze a group of activities that occurred on the same day."""
        if len(activities) < 2:
            return None

        services = set(activity["service"] for activity in activities)
        if len(services) < 2:
            return None  # Only correlate cross-service activities

        # Simple correlation based on having multiple services active same day
        return {
            "type": "temporal_correlation",
            "confidence": 0.6,  # Medium confidence for time-based correlation
            "description": f"Cross-service activity across {', '.join(services)}",
            "activities": activities,
            "date": activities[0].get("created_at", "").split("T")[0],
        }

    def _find_keyword_correlations(
        self, activities: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Find correlations based on keywords in titles/descriptions."""
        correlations = []

        # Simple keyword matching
        keyword_groups = {}

        for activity in activities:
            title = activity.get("title", "").lower()

            # Extract potential feature/project keywords
            words = title.split()
            for word in words:
                if len(word) > 4 and word not in [
                    "pull",
                    "request",
                    "issue",
                    "comment",
                    "review",
                ]:
                    if word not in keyword_groups:
                        keyword_groups[word] = []
                    keyword_groups[word].append(activity)

        # Find groups with activities from multiple services
        for keyword, group_activities in keyword_groups.items():
            if len(group_activities) > 1:
                services = set(activity["service"] for activity in group_activities)
                if len(services) > 1:
                    correlations.append(
                        {
                            "type": "keyword_correlation",
                            "keyword": keyword,
                            "confidence": 0.7,  # Medium-high confidence for keyword matching
                            "description": f"Activities related to '{keyword}' across {', '.join(services)}",
                            "activities": group_activities,
                        }
                    )

        return correlations

    def _llm_analyze_wins(
        self, activity_data: Dict[str, Any], audience: str, focus_areas: List[str]
    ) -> Dict[str, Any]:
        """Use LLM to find correlations and analyze wins from raw activity data."""
        client = self._get_client()
        if not client:
            correlations = self._correlate_activities(activity_data)
            return self._heuristic_analyze_wins(
                activity_data, correlations, audience, focus_areas
            )

        # Prepare raw activity data for LLM (let it find correlations)
        activity_summary = self._prepare_raw_activity_summary(activity_data)

        prompt = self._build_correlation_and_wins_prompt(
            activity_summary, audience, focus_areas
        )

        try:
            response = client.chat.completions.create(
                model="anthropic/claude-3.5-sonnet-20241022",  # Using Claude via OpenRouter
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert at analyzing developer work activity to identify meaningful accomplishments and wins. Focus on impact, collaboration, and growth.",
                    },
                    {"role": "user", "content": prompt},
                ],
                max_tokens=1000,
                temperature=0.3,
            )
            content = response.choices[0].message.content
        except Exception as e:
            logger.error(f"LLM API call failed: {e}")
            # Fallback to heuristic analysis if API call fails
            correlations = self._correlate_activities(activity_data)
            return self._heuristic_analyze_wins(
                activity_data, correlations, audience, focus_areas
            )

        # Try to parse the structured response after a successful API call
        try:
            wins = json.loads(content)
            # Validate required keys are present
            required_keys = ["summary", "categories", "correlations"]
            for key in required_keys:
                if key not in wins:
                    raise KeyError(f"Missing required key: {key}")
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"LLM analysis failed: {e}")
            # Fallback to structured parsing if JSON decoding fails or keys are missing
            wins = self._parse_llm_response(content, activity_summary)

        return wins

    def _heuristic_analyze_wins(
        self,
        activity_data: Dict[str, Any],
        correlations: List[Dict[str, Any]],
        audience: str,
        focus_areas: List[str],
    ) -> Dict[str, Any]:
        """Fallback heuristic analysis when LLM is unavailable."""
        wins = {
            "summary": {
                "total_activities": 0,
                "cross_service_correlations": len(correlations),
                "services_used": list(activity_data.keys()),
            },
            "categories": {},
            "correlations": correlations,
            "audience": audience,
            "focus_areas": focus_areas,
        }

        # Count activities by type
        activity_counts = {}
        for service, data in activity_data.items():
            if isinstance(data, dict) and "activities" in data:
                for activity in data["activities"]:
                    activity_type = activity.get("type", "unknown")
                    activity_counts[activity_type] = (
                        activity_counts.get(activity_type, 0) + 1
                    )
                    wins["summary"]["total_activities"] += 1

        # Create wins categories based on activity types
        if activity_counts.get("pull_request", 0) > 0:
            wins["categories"]["technical_contribution"] = {
                "title": "Code Contributions",
                "description": f"Created {activity_counts['pull_request']} pull requests",
                "impact": "high" if activity_counts["pull_request"] > 3 else "medium",
                "evidence_count": activity_counts["pull_request"],
            }

        if activity_counts.get("review", 0) > 0:
            wins["categories"]["collaboration"] = {
                "title": "Code Review & Collaboration",
                "description": f"Provided {activity_counts['review']} code reviews",
                "impact": "high" if activity_counts["review"] > 5 else "medium",
                "evidence_count": activity_counts["review"],
            }

        if activity_counts.get("commit", 0) > 0:
            wins["categories"]["development_velocity"] = {
                "title": "Development Activity",
                "description": f"Made {activity_counts['commit']} commits",
                "impact": "medium",
                "evidence_count": activity_counts["commit"],
            }

        return wins

    def _prepare_raw_activity_summary(
        self, activity_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Prepare raw activity data for LLM to find correlations and analyze wins."""
        summary = {"services": {}, "total_activities": 0, "time_range": None}

        earliest_date = None
        latest_date = None

        for service, data in activity_data.items():
            if isinstance(data, dict):
                activities = data.get("activities", [])

                # Track time range
                for activity in activities:
                    created_at = activity.get("created_at")
                    if created_at:
                        try:
                            date = datetime.fromisoformat(
                                created_at.replace("Z", "+00:00")
                            )
                            if not earliest_date or date < earliest_date:
                                earliest_date = date
                            if not latest_date or date > latest_date:
                                latest_date = date
                        except Exception:
                            continue

                service_summary = {
                    "activity_count": len(activities),
                    "summary_stats": data.get("summary", {}),
                    "activities": [
                        {
                            "type": act.get("type"),
                            "title": act.get("title", "")[
                                :100
                            ],  # Truncate for token efficiency
                            "created_at": act.get("created_at"),
                            "url": act.get("url"),
                            "repo": act.get("repo"),
                            "labels": act.get("labels", [])[:3],  # Limit labels
                        }
                        for act in activities[:15]  # Limit activities per service
                    ],
                }
                summary["services"][service] = service_summary
                summary["total_activities"] += len(activities)

        if earliest_date and latest_date:
            summary["time_range"] = (
                f"{earliest_date.strftime('%Y-%m-%d')} to {latest_date.strftime('%Y-%m-%d')}"
            )

        return summary

    def _prepare_activity_summary(
        self, activity_data: Dict[str, Any], correlations: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Prepare a concise summary for LLM analysis (fallback method)."""
        summary = {"services": {}, "correlations": correlations, "total_activities": 0}

        for service, data in activity_data.items():
            if isinstance(data, dict):
                service_summary = {
                    "activity_count": len(data.get("activities", [])),
                    "summary": data.get("summary", {}),
                    "key_activities": data.get("activities", [])[
                        :5
                    ],  # First 5 activities
                }
                summary["services"][service] = service_summary
                summary["total_activities"] += service_summary["activity_count"]

        return summary

    def _build_correlation_and_wins_prompt(
        self, activity_summary: Dict[str, Any], audience: str, focus_areas: List[str]
    ) -> str:
        """Build comprehensive prompt for LLM to find correlations and analyze wins."""
        audience_context = {
            "manager": "Focus on business impact, team contributions, measurable outcomes, and leadership qualities",
            "peer": "Emphasize technical depth, collaboration, knowledge sharing, and innovation",
            "self": "Include learning opportunities, growth areas, personal development, and skill building",
            "performance_review": "Highlight achievements, quantifiable metrics, career progression, and strategic contributions",
        }

        focus_context = ""
        if focus_areas:
            focus_context = (
                f"\nPay special attention to these areas: {', '.join(focus_areas)}"
            )

        prompt = f"""You are an expert at analyzing developer work activity to identify meaningful accomplishments, cross-platform correlations, and wins.

ACTIVITY DATA (Time range: {activity_summary.get("time_range", "Recent activity")}):
{json.dumps(activity_summary, indent=2)}

ANALYSIS CONTEXT:
- Target Audience: {audience}
- Audience Focus: {audience_context.get(audience, "General analysis")}{focus_context}

INSTRUCTIONS:
1. **Find Correlations**: Look for activities across different services that are related:
   - Feature delivery (GitHub PR + Linear issue + documentation)
   - Bug resolution (commit + issue closure + reduced incidents)  
   - Technical leadership (code reviews + mentoring + architecture discussions)
   - Knowledge sharing (documentation + presentations + onboarding)
   - Process improvement (tooling + templates + team adoption)

2. **Analyze Impact**: Determine the significance and business value of activities

3. **Categorize Wins**: Group activities into meaningful accomplishment categories

4. **Generate Insights**: Provide strategic insights about work patterns and growth

Return a JSON response with this structure:
{{
    "summary": {{
        "total_activities": {activity_summary.get("total_activities", 0)},
        "services_analyzed": {list(activity_summary.get("services", {}).keys())},
        "key_insight": "One sentence summarizing the most significant pattern or achievement",
        "cross_service_correlations_found": number
    }},
    "correlations": [
        {{
            "type": "feature_delivery|bug_resolution|technical_leadership|knowledge_sharing|process_improvement",
            "title": "Brief correlation title", 
            "description": "What this correlation represents",
            "confidence": 0.0-1.0,
            "business_impact": "high|medium|low",
            "activities": [
                {{
                    "service": "github|linear|notion",
                    "type": "activity type",
                    "title": "activity title",
                    "url": "activity URL"
                }}
            ]
        }}
    ],
    "categories": {{
        "technical_contribution": {{
            "title": "Category title",
            "description": "What was accomplished in this area",
            "impact": "high|medium|low",
            "evidence_count": number_of_supporting_activities,
            "key_achievements": ["achievement 1", "achievement 2"]
        }}
        // Add more categories as relevant: collaboration, leadership, learning, innovation, etc.
    }},
    "top_wins": [
        {{
            "title": "Specific win title",
            "description": "Detailed description of the accomplishment",
            "impact": "high|medium|low", 
            "correlation_id": "reference to correlation if applicable",
            "evidence": ["Specific supporting activities with URLs"]
        }}
    ],
    "growth_insights": {{
        "strengths_demonstrated": ["strength 1", "strength 2"],
        "areas_of_impact": ["area 1", "area 2"],
        "collaboration_patterns": "description of how they work with others"
    }}
}}

Focus on meaningful impact and genuine correlations. Look for patterns that show growth, collaboration, and business value beyond just counting activities."""

        return prompt

    def _build_analysis_prompt(
        self, summary: Dict[str, Any], audience: str, focus_areas: List[str]
    ) -> str:
        """Build LLM prompt for wins analysis."""
        audience_context = {
            "manager": "Focus on business impact, team contributions, and measurable outcomes",
            "peer": "Emphasize technical depth, collaboration, and knowledge sharing",
            "self": "Include learning, growth areas, and personal development",
            "performance_review": "Highlight achievements, metrics, and career progression",
        }

        focus_context = ""
        if focus_areas:
            focus_context = f"\nSpecial focus areas: {', '.join(focus_areas)}"

        prompt = f"""Analyze the following developer activity data and identify meaningful wins and accomplishments.

Activity Summary:
{json.dumps(summary, indent=2)}

Context:
- Audience: {audience} ({audience_context.get(audience, "")})
- Time period: Recent work activity{focus_context}

Please provide a JSON response with the following structure:
{{
    "summary": {{
        "total_activities": number,
        "key_insight": "brief overall insight",
        "cross_service_impact": "description of cross-service correlations"
    }},
    "categories": {{
        "technical_contribution": {{
            "title": "category title",
            "description": "what was accomplished",
            "impact": "high|medium|low",
            "evidence_count": number
        }},
        // ... more categories as relevant
    }},
    "top_wins": [
        {{
            "title": "win title",
            "description": "win description",
            "impact": "high|medium|low",
            "evidence": ["specific activities that support this win"]
        }}
    ]
}}

Focus on meaningful impact rather than just activity counts. Look for patterns that show growth, collaboration, and business value."""

        return prompt

    def _parse_llm_response(
        self, content: str, summary: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Parse LLM response if JSON parsing fails."""
        # Simple fallback parsing
        wins = {
            "summary": {
                "total_activities": summary.get("total_activities", 0),
                "key_insight": "LLM analysis completed",
                "cross_service_impact": f"Found {len(summary.get('correlations', []))} cross-service correlations",
            },
            "categories": {},
            "top_wins": [],
            "llm_response": content,
        }
        return wins

    def _generate_markdown_report(
        self, wins_data: Dict[str, Any], audience: str
    ) -> str:
        """Generate markdown report from wins data."""
        report_lines = []

        # Title based on audience
        audience_titles = {
            "manager": "Weekly Accomplishments - Manager Report",
            "peer": "Weekly Technical Contributions",
            "self": "Weekly Self-Reflection",
            "performance_review": "Performance Review - Key Accomplishments",
        }

        title = audience_titles.get(audience, "Weekly Wins Report")
        report_lines.append(f"# {title}\n")

        # Summary section
        summary = wins_data.get("summary", {})
        report_lines.append("## Summary")
        report_lines.append(
            f"- **Total Activities**: {summary.get('total_activities', 0)}"
        )

        if "key_insight" in summary:
            report_lines.append(f"- **Key Insight**: {summary['key_insight']}")

        if "cross_service_impact" in summary:
            report_lines.append(
                f"- **Cross-Service Impact**: {summary['cross_service_impact']}"
            )

        report_lines.append("")

        # Categories section
        categories = wins_data.get("categories", {})
        if categories:
            report_lines.append("## Key Accomplishments")
            for category_key, category in categories.items():
                impact_emoji = (
                    "🔥"
                    if category.get("impact") == "high"
                    else "📈"
                    if category.get("impact") == "medium"
                    else "✅"
                )
                report_lines.append(
                    f"### {impact_emoji} {category.get('title', category_key.title())}"
                )
                report_lines.append(f"{category.get('description', '')}")
                if category.get("evidence_count"):
                    report_lines.append(
                        f"*Evidence: {category['evidence_count']} supporting activities*"
                    )
                report_lines.append("")

        # Top wins section
        top_wins = wins_data.get("top_wins", [])
        if top_wins:
            report_lines.append("## Highlights")
            for win in top_wins:
                impact_emoji = (
                    "🔥"
                    if win.get("impact") == "high"
                    else "📈"
                    if win.get("impact") == "medium"
                    else "✅"
                )
                report_lines.append(
                    f"- {impact_emoji} **{win.get('title', '')}**: {win.get('description', '')}"
                )

        # Correlations section
        correlations = wins_data.get("correlations", [])
        if correlations:
            report_lines.append("\n## Cross-Platform Connections")
            for correlation in correlations:
                report_lines.append(
                    f"- **{correlation.get('description', '')}** (confidence: {correlation.get('confidence', 0):.0%})"
                )

        return "\n".join(report_lines)

    def _generate_slack_report(self, wins_data: Dict[str, Any]) -> str:
        """Generate Slack-formatted report."""
        summary = wins_data.get("summary", {})

        lines = [
            "🎉 *Weekly Wins Summary*",
            f"📊 {summary.get('total_activities', 0)} activities across platforms",
        ]

        # Top categories
        categories = wins_data.get("categories", {})
        for category_key, category in list(categories.items())[:3]:  # Top 3
            impact_emoji = "🔥" if category.get("impact") == "high" else "📈"
            lines.append(
                f"{impact_emoji} {category.get('title', '')}: {category.get('description', '')}"
            )

        if len(categories) > 3:
            lines.append(f"...and {len(categories) - 3} more accomplishments")

        return "\n".join(lines)

    def _get_client(self) -> Optional[OpenAI]:
        """Get OpenRouter client from environment variable."""
        if not self._client:
            import os

            api_key = os.getenv("OPENROUTER_API_KEY")
            if api_key:
                self._client = OpenAI(
                    base_url="https://openrouter.ai/api/v1", api_key=api_key
                )
        return self._client
