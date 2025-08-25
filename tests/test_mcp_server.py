"""Integration tests for MCP server tools."""

import pytest
from unittest.mock import patch
import json
from datetime import datetime

# Import the actual functions before they are decorated
# We need to access the unwrapped functions for testing
from wins_finder.mcp import server

# Get the actual functions from the decorated tools/resources
analyze_weekly_wins = server.analyze_weekly_wins.fn
test_authentication = server.test_authentication.fn
collect_activity_data = server.collect_activity_data.fn
correlate_activities = server.correlate_activities.fn
generate_report = server.generate_report.fn
save_preferences = server.save_preferences.fn
post_to_slack = server.post_to_slack.fn
clear_cache = server.clear_cache.fn
get_cache_stats = server.get_cache_stats.fn
get_current_preferences = server.get_current_preferences.fn
_parse_timeframe = server._parse_timeframe


@pytest.mark.integration
class TestMCPServerTools:
    """Test MCP server tool functions."""

    def test_parse_timeframe_last_week(self):
        """Test parsing 'last_week' timeframe."""
        start_date, end_date = _parse_timeframe("last_week")

        assert isinstance(start_date, datetime)
        assert isinstance(end_date, datetime)
        assert start_date < end_date
        # Should be approximately 7-8 days apart (last 7 days + buffer for current day)
        days_diff = (end_date - start_date).days
        assert 7 <= days_diff <= 8

    def test_parse_timeframe_custom_range(self):
        """Test parsing custom date range."""
        start_date, end_date = _parse_timeframe("2024-01-15_to_2024-01-21")

        assert start_date == datetime(2024, 1, 15)
        assert end_date == datetime(2024, 1, 21)

    def test_parse_timeframe_invalid_default(self):
        """Test parsing invalid timeframe defaults to last_week."""
        start_date, end_date = _parse_timeframe("invalid_format")

        assert isinstance(start_date, datetime)
        assert isinstance(end_date, datetime)
        days_diff = (end_date - start_date).days
        assert 7 <= days_diff <= 8

    @patch.dict("os.environ", {"GITHUB_TOKEN": "test_token"})
    def test_test_authentication_with_token(self):
        """Test authentication check with GitHub token."""
        result = test_authentication()

        assert isinstance(result, str)
        assert "GitHub" in result
        # Should indicate token is found
        assert (
            "environment variable found" in result
            or "Connected" in result
            or "Failed" in result
        )

    @patch.dict("os.environ", {}, clear=True)
    def test_test_authentication_no_tokens(self):
        """Test authentication check without tokens."""
        result = test_authentication()

        assert isinstance(result, str)
        assert "⚠️" in result  # Warning symbols for missing tokens
        assert "GITHUB_TOKEN" in result

    @patch("wins_finder.mcp.server.github")
    @patch("wins_finder.mcp.server.linear")
    @patch("wins_finder.mcp.server.notion")
    @patch("wins_finder.mcp.server.analyzer")
    @patch("wins_finder.mcp.server.db")
    def test_analyze_weekly_wins_success(
        self, mock_db, mock_analyzer, mock_notion, mock_linear, mock_github
    ):
        """Test successful weekly wins analysis."""
        # Mock service responses
        mock_github.get_activity.return_value = {"activities": [], "summary": {}}
        mock_linear.get_activity.return_value = {"activities": [], "summary": {}}
        mock_notion.get_activity.return_value = {"activities": [], "summary": {}}

        # Mock analyzer response
        mock_wins = {"summary": {"total_activities": 0}, "categories": {}}
        mock_analyzer.analyze_wins.return_value = mock_wins
        mock_analyzer.generate_report.return_value = "# Weekly Report"

        # Mock database
        mock_db.save_wins.return_value = 1

        result = analyze_weekly_wins("last_week", "manager", ["technical"])

        assert isinstance(result, str)
        assert "# Weekly Report" in result

        # Verify services were called
        mock_github.get_activity.assert_called_once()
        mock_linear.get_activity.assert_called_once()
        mock_notion.get_activity.assert_called_once()

        # Verify analyzer was called
        mock_analyzer.analyze_wins.assert_called_once()
        mock_analyzer.generate_report.assert_called_once()

        # Verify data was saved
        mock_db.save_wins.assert_called_once()

    @patch("wins_finder.mcp.server.github")
    def test_analyze_weekly_wins_service_error(self, mock_github):
        """Test weekly wins analysis with service error."""
        # Mock GitHub service error
        mock_github.get_activity.side_effect = Exception("GitHub API Error")

        with (
            patch("wins_finder.mcp.server.linear") as mock_linear,
            patch("wins_finder.mcp.server.notion") as mock_notion,
            patch("wins_finder.mcp.server.analyzer") as mock_analyzer,
            patch("wins_finder.mcp.server.db") as mock_db,
        ):
            mock_linear.get_activity.return_value = {"activities": []}
            mock_notion.get_activity.return_value = {"activities": []}
            mock_analyzer.analyze_wins.return_value = {"summary": {}}
            mock_analyzer.generate_report.return_value = "Report"
            mock_db.save_wins.return_value = 1

            result = analyze_weekly_wins("last_week", "self", [])

            # Should still complete despite GitHub error
            assert isinstance(result, str)
            # GitHub should have empty data due to error
            mock_analyzer.analyze_wins.assert_called_once()

    @patch("wins_finder.mcp.server.github")
    @patch("wins_finder.mcp.server.linear")
    @patch("wins_finder.mcp.server.notion")
    def test_collect_activity_data_success(self, mock_notion, mock_linear, mock_github):
        """Test successful activity data collection."""
        # Mock service responses
        mock_github.get_activity.return_value = {
            "activities": [1, 2, 3],
            "from_cache": False,
        }
        mock_linear.get_activity.return_value = {"activities": [1], "from_cache": True}
        mock_notion.get_activity.return_value = {"activities": [], "from_cache": False}

        result = collect_activity_data(
            "last_week", ["github", "linear", "notion"], True
        )

        assert isinstance(result, str)
        assert "Activity data collection results:" in result
        assert "✅ github: 3 activities" in result
        assert "✅ linear: 1 activities (cached)" in result
        assert "✅ notion: 0 activities" in result

    @patch("wins_finder.mcp.server.github")
    def test_collect_activity_data_service_error(self, mock_github):
        """Test activity data collection with service error."""
        mock_github.get_activity.side_effect = Exception("Service error")

        result = collect_activity_data("last_week", ["github"], False)

        assert isinstance(result, str)
        assert "❌ github: Service error" in result

    def test_correlate_activities_placeholder(self):
        """Test correlate activities placeholder function."""
        result = correlate_activities(force_refresh=True)

        assert isinstance(result, str)
        assert "correlation analysis completed" in result.lower()

    def test_generate_report_success(self, sample_wins_data):
        """Test report generation."""
        with patch("wins_finder.mcp.server.analyzer") as mock_analyzer:
            mock_analyzer.generate_report.return_value = "# Generated Report"

            result = generate_report(sample_wins_data, "markdown", "manager")

            assert result == "# Generated Report"
            mock_analyzer.generate_report.assert_called_once_with(
                sample_wins_data, "markdown", "manager"
            )

    def test_generate_report_error(self, sample_wins_data):
        """Test report generation with error."""
        with patch("wins_finder.mcp.server.analyzer") as mock_analyzer:
            mock_analyzer.generate_report.side_effect = Exception("Generation error")

            result = generate_report(sample_wins_data, "json", "self")

            assert "Error generating report" in result
            assert "Generation error" in result

    @patch("wins_finder.mcp.server.db")
    def test_save_preferences_success(self, mock_db):
        """Test saving preferences successfully."""
        preferences = {"audience": "manager", "focus_areas": ["technical"]}

        result = save_preferences(preferences)

        assert "Saved 2 preferences" in result
        assert mock_db.save_preference.call_count == 2

    @patch("wins_finder.mcp.server.db")
    def test_save_preferences_error(self, mock_db):
        """Test saving preferences with error."""
        mock_db.save_preference.side_effect = Exception("Database error")

        result = save_preferences({"key": "value"})

        assert "Error saving preferences" in result
        assert "Database error" in result

    @patch("wins_finder.mcp.server.slack")
    def test_post_to_slack_success(self, mock_slack):
        """Test posting to Slack successfully."""
        mock_slack.post_message.return_value = "Message posted"

        result = post_to_slack("Test message", "general")

        assert "✅ Posted to Slack" in result
        mock_slack.post_message.assert_called_once_with(
            "Test message", channel="general"
        )

    @patch("wins_finder.mcp.server.slack")
    def test_post_to_slack_error(self, mock_slack):
        """Test posting to Slack with error."""
        mock_slack.post_message.side_effect = Exception("Slack error")

        result = post_to_slack("Test message")

        assert "❌ Failed to post to Slack" in result
        assert "Slack error" in result

    @patch("wins_finder.mcp.server.db")
    def test_clear_cache_success(self, mock_db):
        """Test clearing cache successfully."""
        result = clear_cache(7)

        assert "✅ Cleared cache older than 7 days" in result
        mock_db.clear_cache.assert_called_once_with(7)

    @patch("wins_finder.mcp.server.db")
    def test_clear_cache_error(self, mock_db):
        """Test clearing cache with error."""
        mock_db.clear_cache.side_effect = Exception("Database error")

        result = clear_cache(3)

        assert "Error clearing cache" in result
        assert "Database error" in result

    @patch("wins_finder.mcp.server.db")
    def test_get_cache_stats_success(self, mock_db):
        """Test getting cache stats successfully."""
        mock_stats = {"github_prs": {"count": 10, "latest": "2024-01-20"}}
        mock_db.get_cache_stats.return_value = mock_stats

        result = get_cache_stats()

        # Should return JSON string
        parsed = json.loads(result)
        assert parsed == mock_stats

    @patch("wins_finder.mcp.server.db")
    def test_get_cache_stats_error(self, mock_db):
        """Test getting cache stats with error."""
        mock_db.get_cache_stats.side_effect = Exception("Database error")

        result = get_cache_stats()

        assert "Error getting cache stats" in result
        assert "Database error" in result

    @patch("wins_finder.mcp.server.db")
    def test_get_current_preferences_success(self, mock_db):
        """Test getting current preferences successfully."""
        mock_db.get_preference.side_effect = lambda key, default: {
            "audience_preference": "manager",
            "focus_areas": ["technical"],
            "report_format": "markdown",
        }.get(key, default)

        result = get_current_preferences()

        # Should return JSON string
        parsed = json.loads(result)
        assert parsed["audience_preference"] == "manager"
        assert parsed["focus_areas"] == ["technical"]
        assert parsed["report_format"] == "markdown"

    @patch("wins_finder.mcp.server.db")
    def test_get_current_preferences_error(self, mock_db):
        """Test getting current preferences with error."""
        mock_db.get_preference.side_effect = Exception("Database error")

        result = get_current_preferences()

        assert "Error getting preferences" in result
        assert "Database error" in result


@pytest.mark.integration
class TestMCPServerIntegration:
    """Integration tests with real components (but mocked external APIs)."""

    @patch.dict("os.environ", {"GITHUB_TOKEN": "test_token"})
    @patch("wins_finder.integrations.github_client.Github")
    def test_end_to_end_workflow(self, mock_github_class, temp_db, mock_github_api):
        """Test end-to-end workflow with mocked external APIs."""
        from wins_finder.integrations.github_client import GitHubClient
        from wins_finder.llm.analyzer import WinsAnalyzer
        from wins_finder.database.models import WinsDatabase

        # Set up mocked GitHub client
        mock_github_class.return_value = mock_github_api

        # Create real instances with temp database
        db = WinsDatabase(temp_db.engine.url)
        github_client = GitHubClient(db)
        analyzer = WinsAnalyzer(db)

        # Test the workflow
        start_date = datetime(2024, 1, 15)
        end_date = datetime(2024, 1, 21)

        # Get activity (should use mocked API)
        activity = github_client.get_activity(start_date, end_date, use_cache=False)
        assert activity["from_cache"] is False

        # Analyze wins (without LLM)
        activity_data = {"github": activity}
        with patch.object(analyzer, "_get_client", return_value=None):
            wins = analyzer.analyze_wins(activity_data, audience="self")

        assert "summary" in wins
        assert "categories" in wins

        # Generate report
        report = analyzer.generate_report(wins, format="markdown", audience="self")
        assert isinstance(report, str)
        assert "# Weekly Self-Reflection" in report
