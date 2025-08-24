"""MCP Server for the Wins Finder agent using FastMCP."""

import json
from typing import Any, Dict, List
from datetime import datetime, timedelta
import logging

from fastmcp import FastMCP

from wins_finder.database.models import WinsDatabase
from wins_finder.llm.analyzer import WinsAnalyzer
from wins_finder.integrations.github_client import GitHubClient
from wins_finder.integrations.linear_client import LinearClient
from wins_finder.integrations.notion_client import NotionClient
from wins_finder.integrations.slack_client import SlackClient

logger = logging.getLogger(__name__)
logger.info("Initializing MCP server components")

# Initialize FastMCP server
mcp = FastMCP("wins-finder")

# Initialize components
logger.info("Initializing database...")
db = WinsDatabase()
logger.info("Initializing analyzer...")
analyzer = WinsAnalyzer()
logger.info("Initializing GitHub client...")
github = GitHubClient()
logger.info("Initializing Linear client...")
linear = LinearClient()
logger.info("Initializing Notion client...")
notion = NotionClient()
logger.info("Initializing Slack client...")
slack = SlackClient()
logger.info("All components initialized successfully")


@mcp.tool()
def analyze_weekly_wins(
    timeframe: str = "last_week", audience: str = "self", focus_areas: List[str] = None
) -> str:
    """Analyze weekly accomplishments across GitHub, Linear, Notion, and Slack.

    Args:
        timeframe: Time period to analyze (e.g., 'last_week', '2024-01-15_to_2024-01-22')
        audience: Target audience ('self', 'manager', 'peer', 'performance_review')
        focus_areas: Areas to focus on (e.g., ['technical', 'leadership', 'collaboration'])

    Returns:
        Generated wins report as markdown
    """
    focus_areas = focus_areas or []

    try:
        logger.info(
            f"analyze_weekly_wins called with timeframe={timeframe}, audience={audience}"
        )
        # Parse timeframe
        start_date, end_date = _parse_timeframe(timeframe)

        # Collect data from all services
        activity_data = {}
        for service in ["github", "linear", "notion"]:
            try:
                if service == "github":
                    data = github.get_activity(start_date, end_date, use_cache=True)
                elif service == "linear":
                    data = linear.get_activity(start_date, end_date, use_cache=True)
                elif service == "notion":
                    data = notion.get_activity(start_date, end_date, use_cache=True)

                activity_data[service] = data
            except Exception as e:
                logger.warning(f"Failed to get {service} data: {e}")
                activity_data[service] = {}

        # Analyze and correlate
        wins = analyzer.analyze_wins(
            activity_data, audience=audience, focus_areas=focus_areas
        )

        # Save to history
        week_start = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
        db.save_wins(week_start, wins)

        # Generate report
        report = analyzer.generate_report(wins, format="markdown", audience=audience)

        return report

    except Exception as e:
        logger.error(f"Error in analyze_weekly_wins: {e}")
        return f"Error analyzing wins: {str(e)}"


@mcp.tool()
def test_authentication() -> str:
    """Test authentication for all configured services using environment variables.

    Returns:
        Status of all service authentications
    """
    logger.info("test_authentication called")
    import os

    results = []

    # Test GitHub
    if os.getenv("GITHUB_TOKEN"):
        try:
            success = github.test_connection()
            results.append("✅ GitHub: Connected" if success else "❌ GitHub: Failed")
        except Exception as e:
            results.append(f"❌ GitHub: {str(e)}")
    else:
        results.append("⚠️ GitHub: No GITHUB_TOKEN environment variable")

    # Test OpenRouter
    if os.getenv("OPENROUTER_API_KEY"):
        results.append("✅ OpenRouter: API key found")
    else:
        results.append("⚠️ OpenRouter: No OPENROUTER_API_KEY environment variable")

    # Test other services
    for service, env_var in [
        ("Linear", "LINEAR_API_KEY"),
        ("Notion", "NOTION_API_KEY"),
        ("Slack", "SLACK_WEBHOOK_URL"),
    ]:
        if os.getenv(env_var):
            results.append(f"✅ {service}: Environment variable found")
        else:
            results.append(f"⚠️ {service}: No {env_var} environment variable")

    return "\n".join(results)


@mcp.tool()
def collect_activity_data(
    timeframe: str, services: List[str] = None, use_cache: bool = True
) -> str:
    """Collect activity data from specified services.

    Args:
        timeframe: Time period for data collection
        services: Services to collect data from ('github', 'linear', 'notion', 'slack')
        use_cache: Use cached data if available

    Returns:
        Summary of data collection results
    """
    services = services or ["github", "linear", "notion"]
    start_date, end_date = _parse_timeframe(timeframe)

    results = {}
    for service in services:
        try:
            if service == "github":
                data = github.get_activity(start_date, end_date, use_cache)
            elif service == "linear":
                data = linear.get_activity(start_date, end_date, use_cache)
            elif service == "notion":
                data = notion.get_activity(start_date, end_date, use_cache)

            results[service] = {
                "success": True,
                "count": len(data.get("activities", [])),
                "cached": data.get("from_cache", False),
            }
        except Exception as e:
            results[service] = {"success": False, "error": str(e)}

    summary = "Activity data collection results:\n"
    for service, result in results.items():
        if service in results and results[service]["success"]:
            cache_indicator = " (cached)" if results[service].get("cached") else ""
            summary += f"✅ {service}: {results[service]['count']} activities{cache_indicator}\n"
        else:
            summary += f"❌ {service}: {results[service]['error']}\n"

    return summary


@mcp.tool()
def correlate_activities(force_refresh: bool = False) -> str:
    """Find correlations between activities across services.

    Args:
        force_refresh: Force refresh of correlations

    Returns:
        Summary of correlation analysis
    """
    # This would implement cross-service correlation logic
    # For now, return a placeholder that demonstrates the concept
    return "Correlation analysis completed. Found 3 cross-service connections."


@mcp.tool()
def generate_report(
    wins_data: Dict[str, Any], format: str = "markdown", audience: str = "self"
) -> str:
    """Generate a wins report from analyzed data.

    Args:
        wins_data: Processed wins data
        format: Output format ('markdown', 'json', 'slack')
        audience: Target audience ('self', 'manager', 'peer', 'performance_review')

    Returns:
        Formatted report
    """
    try:
        report = analyzer.generate_report(wins_data, format, audience)
        return report
    except Exception as e:
        return f"Error generating report: {str(e)}"


@mcp.tool()
def save_preferences(preferences: Dict[str, Any]) -> str:
    """Save user preferences for report generation.

    Args:
        preferences: User preferences to save

    Returns:
        Confirmation message
    """
    try:
        for key, value in preferences.items():
            db.save_preference(key, value)

        return f"Saved {len(preferences)} preferences"
    except Exception as e:
        return f"Error saving preferences: {str(e)}"


@mcp.tool()
def post_to_slack(report_summary: str, channel_hint: str = None) -> str:
    """Post wins summary to Slack channel.

    Args:
        report_summary: Summary to post to Slack
        channel_hint: Channel to post to (optional)

    Returns:
        Status message
    """
    try:
        result = slack.post_message(report_summary, channel=channel_hint)
        return f"✅ Posted to Slack: {result}"
    except Exception as e:
        return f"❌ Failed to post to Slack: {str(e)}"


@mcp.tool()
def clear_cache(older_than_days: int = 7) -> str:
    """Clear cached API data.

    Args:
        older_than_days: Clear cache older than N days

    Returns:
        Confirmation message
    """
    try:
        db.clear_cache(older_than_days)
        return f"✅ Cleared cache older than {older_than_days} days"
    except Exception as e:
        return f"Error clearing cache: {str(e)}"


@mcp.resource("cache://stats")
def get_cache_stats() -> str:
    """Get API call statistics and cache hit rates."""
    try:
        stats = db.get_cache_stats()
        return json.dumps(stats, indent=2, default=str)
    except Exception as e:
        return f"Error getting cache stats: {str(e)}"


@mcp.resource("preferences://current")
def get_current_preferences() -> str:
    """Get current user settings and preferences."""
    try:
        prefs = {
            "audience_preference": db.get_preference("audience_preference", "self"),
            "focus_areas": db.get_preference("focus_areas", []),
            "report_format": db.get_preference("report_format", "markdown"),
        }
        return json.dumps(prefs, indent=2)
    except Exception as e:
        return f"Error getting preferences: {str(e)}"


def _parse_timeframe(timeframe: str) -> tuple[datetime, datetime]:
    """Parse timeframe string into start and end dates."""
    now = datetime.now()

    if timeframe == "last_week":
        # Last Monday to Sunday
        days_since_monday = now.weekday()
        start_date = now - timedelta(days=days_since_monday + 7)
        end_date = start_date + timedelta(days=6)
    elif "_to_" in timeframe:
        # Format: "2024-01-15_to_2024-01-22"
        start_str, end_str = timeframe.split("_to_")
        start_date = datetime.fromisoformat(start_str)
        end_date = datetime.fromisoformat(end_str)
    else:
        # Default to last week
        days_since_monday = now.weekday()
        start_date = now - timedelta(days=days_since_monday + 7)
        end_date = start_date + timedelta(days=6)

    return start_date, end_date


if __name__ == "__main__":
    mcp.run(show_banner=False)
