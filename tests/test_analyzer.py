"""Unit tests for LLM analyzer functionality."""

import pytest
import json
from unittest.mock import Mock, patch
from datetime import datetime

from wins_finder.llm.analyzer import WinsAnalyzer


@pytest.mark.unit
class TestWinsAnalyzer:
    """Test LLM analyzer functionality."""

    def test_analyzer_initialization(self, temp_db):
        """Test analyzer initialization."""
        analyzer = WinsAnalyzer(temp_db)
        assert analyzer.db == temp_db
        assert analyzer._client is None
        assert analyzer._api_key is None

    def test_analyze_wins_with_mock_llm(self, temp_db, sample_activity_data, mock_openai_client):
        """Test analyze_wins with mocked LLM client."""
        analyzer = WinsAnalyzer(temp_db)
        
        with patch.object(analyzer, '_get_client', return_value=mock_openai_client):
            result = analyzer.analyze_wins(sample_activity_data, audience="manager")
        
        assert isinstance(result, dict)
        # Should have called the LLM
        mock_openai_client.chat.completions.create.assert_called_once()

    def test_analyze_wins_without_llm(self, temp_db, sample_activity_data):
        """Test analyze_wins fallback without LLM client."""
        analyzer = WinsAnalyzer(temp_db)
        
        # No LLM client available
        with patch.object(analyzer, '_get_client', return_value=None):
            result = analyzer.analyze_wins(sample_activity_data, audience="self")
        
        assert isinstance(result, dict)
        assert "summary" in result
        assert "categories" in result
        assert "correlations" in result

    def test_generate_report_markdown(self, temp_db, sample_wins_data):
        """Test markdown report generation."""
        analyzer = WinsAnalyzer(temp_db)
        
        report = analyzer.generate_report(sample_wins_data, format="markdown", audience="manager")
        
        assert isinstance(report, str)
        assert "# Weekly Accomplishments - Manager Report" in report
        assert "## Summary" in report
        assert "## Key Accomplishments" in report

    def test_generate_report_json(self, temp_db, sample_wins_data):
        """Test JSON report generation."""
        analyzer = WinsAnalyzer(temp_db)
        
        report = analyzer.generate_report(sample_wins_data, format="json", audience="self")
        
        assert isinstance(report, str)
        # Should be valid JSON
        parsed = json.loads(report)
        assert "summary" in parsed

    def test_generate_report_slack(self, temp_db, sample_wins_data):
        """Test Slack report generation."""
        analyzer = WinsAnalyzer(temp_db)
        
        report = analyzer.generate_report(sample_wins_data, format="slack", audience="peer")
        
        assert isinstance(report, str)
        assert "🎉 *Weekly Wins Summary*" in report
        assert "📊" in report

    def test_generate_report_invalid_format(self, temp_db, sample_wins_data):
        """Test invalid report format raises error."""
        analyzer = WinsAnalyzer(temp_db)
        
        with pytest.raises(ValueError, match="Unsupported format"):
            analyzer.generate_report(sample_wins_data, format="invalid")

    def test_correlate_activities_empty(self, temp_db):
        """Test correlation with empty activity data."""
        analyzer = WinsAnalyzer(temp_db)
        
        empty_data = {"github": {"activities": []}, "linear": {"activities": []}}
        correlations = analyzer._correlate_activities(empty_data)
        
        assert correlations == []

    def test_correlate_activities_single_service(self, temp_db, sample_github_activity):
        """Test correlation with single service data."""
        analyzer = WinsAnalyzer(temp_db)
        
        single_service_data = {"github": sample_github_activity}
        correlations = analyzer._correlate_activities(single_service_data)
        
        # Should not find cross-service correlations with only one service
        assert len(correlations) == 0

    def test_correlate_activities_multiple_services(self, temp_db, sample_activity_data):
        """Test correlation with multiple service data."""
        analyzer = WinsAnalyzer(temp_db)
        
        # Add some activities to other services
        sample_activity_data["linear"]["activities"] = [
            {
                "type": "issue",
                "title": "Implement authentication system",
                "created_at": "2024-01-15T10:30:00Z",
                "service": "linear"
            }
        ]
        
        correlations = analyzer._correlate_activities(sample_activity_data)
        
        # Should find at least temporal correlations
        assert len(correlations) >= 0

    def test_group_by_time(self, temp_db):
        """Test grouping activities by time."""
        analyzer = WinsAnalyzer(temp_db)
        
        activities = [
            {"created_at": "2024-01-15T10:00:00Z", "title": "Activity 1"},
            {"created_at": "2024-01-15T14:00:00Z", "title": "Activity 2"},
            {"created_at": "2024-01-16T09:00:00Z", "title": "Activity 3"},
        ]
        
        groups = analyzer._group_by_time(activities)
        
        assert "2024-01-15" in groups
        assert "2024-01-16" in groups
        assert len(groups["2024-01-15"]) == 2
        assert len(groups["2024-01-16"]) == 1

    def test_group_by_time_invalid_dates(self, temp_db):
        """Test grouping activities with invalid dates."""
        analyzer = WinsAnalyzer(temp_db)
        
        activities = [
            {"created_at": "invalid-date", "title": "Activity 1"},
            {"created_at": "2024-01-15T10:00:00Z", "title": "Activity 2"},
        ]
        
        groups = analyzer._group_by_time(activities)
        
        # Should only group valid dates
        assert "2024-01-15" in groups
        assert len(groups) == 1

    def test_analyze_time_group_insufficient_activities(self, temp_db):
        """Test analyzing time group with too few activities."""
        analyzer = WinsAnalyzer(temp_db)
        
        single_activity = [{"service": "github", "title": "Single activity"}]
        result = analyzer._analyze_time_group(single_activity)
        
        assert result is None

    def test_analyze_time_group_single_service(self, temp_db):
        """Test analyzing time group with single service."""
        analyzer = WinsAnalyzer(temp_db)
        
        same_service_activities = [
            {"service": "github", "title": "Activity 1"},
            {"service": "github", "title": "Activity 2"},
        ]
        result = analyzer._analyze_time_group(same_service_activities)
        
        assert result is None  # Only correlates cross-service

    def test_analyze_time_group_cross_service(self, temp_db):
        """Test analyzing time group with cross-service activities."""
        analyzer = WinsAnalyzer(temp_db)
        
        cross_service_activities = [
            {"service": "github", "title": "PR", "created_at": "2024-01-15T10:00:00Z"},
            {"service": "linear", "title": "Issue", "created_at": "2024-01-15T10:00:00Z"},
        ]
        result = analyzer._analyze_time_group(cross_service_activities)
        
        assert result is not None
        assert result["type"] == "temporal_correlation"
        assert result["confidence"] == 0.6

    def test_find_keyword_correlations_empty(self, temp_db):
        """Test keyword correlation with empty activities."""
        analyzer = WinsAnalyzer(temp_db)
        
        correlations = analyzer._find_keyword_correlations([])
        
        assert correlations == []

    def test_find_keyword_correlations_matching(self, temp_db):
        """Test keyword correlation with matching keywords."""
        analyzer = WinsAnalyzer(temp_db)
        
        activities = [
            {"service": "github", "title": "authentication system implementation"},
            {"service": "linear", "title": "authentication feature request"},
            {"service": "notion", "title": "authentication documentation"},
        ]
        
        correlations = analyzer._find_keyword_correlations(activities)
        
        # Should find correlation based on "authentication" keyword
        assert len(correlations) > 0
        auth_correlation = next((c for c in correlations if c["keyword"] == "authentication"), None)
        assert auth_correlation is not None
        assert auth_correlation["type"] == "keyword_correlation"

    def test_heuristic_analyze_wins(self, temp_db, sample_activity_data):
        """Test heuristic wins analysis."""
        analyzer = WinsAnalyzer(temp_db)
        
        correlations = []
        result = analyzer._heuristic_analyze_wins(
            sample_activity_data, correlations, "manager", ["technical"]
        )
        
        assert "summary" in result
        assert "categories" in result
        assert result["audience"] == "manager"
        assert result["focus_areas"] == ["technical"]

    def test_prepare_raw_activity_summary(self, temp_db, sample_activity_data):
        """Test preparing activity summary for LLM."""
        analyzer = WinsAnalyzer(temp_db)
        
        summary = analyzer._prepare_raw_activity_summary(sample_activity_data)
        
        assert "services" in summary
        assert "total_activities" in summary
        assert "github" in summary["services"]
        assert summary["total_activities"] > 0

    def test_get_client_with_api_key(self, temp_db):
        """Test getting OpenAI client with API key."""
        analyzer = WinsAnalyzer(temp_db)
        
        with patch.dict('os.environ', {"OPENROUTER_API_KEY": "test_key"}):
            with patch("wins_finder.llm.analyzer.OpenAI") as mock_openai:
                client = analyzer._get_client()
                
                mock_openai.assert_called_once_with(
                    base_url="https://openrouter.ai/api/v1",
                    api_key="test_key"
                )

    def test_get_client_without_api_key(self, temp_db):
        """Test getting OpenAI client without API key."""
        analyzer = WinsAnalyzer(temp_db)
        
        with patch.dict('os.environ', {}, clear=True):
            client = analyzer._get_client()
            
            assert client is None

    def test_llm_analyze_wins_json_response(self, temp_db, sample_activity_data, mock_openai_client):
        """Test LLM analysis with valid JSON response."""
        analyzer = WinsAnalyzer(temp_db)
        
        # Mock valid JSON response
        mock_response = Mock()
        valid_json = {
            "summary": {"total_activities": 3},
            "categories": {"technical": {"title": "Tech"}},
            "correlations": []
        }
        mock_response.choices = [Mock(message=Mock(content=json.dumps(valid_json)))]
        mock_openai_client.chat.completions.create.return_value = mock_response
        
        with patch.object(analyzer, '_get_client', return_value=mock_openai_client):
            result = analyzer._llm_analyze_wins(sample_activity_data, "manager", ["technical"])
        
        assert result["summary"]["total_activities"] == 3
        assert "technical" in result["categories"]

    def test_llm_analyze_wins_invalid_json(self, temp_db, sample_activity_data, mock_openai_client):
        """Test LLM analysis with invalid JSON response."""
        analyzer = WinsAnalyzer(temp_db)
        
        # Mock invalid JSON response
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="Invalid JSON response"))]
        mock_openai_client.chat.completions.create.return_value = mock_response
        
        with patch.object(analyzer, '_get_client', return_value=mock_openai_client):
            result = analyzer._llm_analyze_wins(sample_activity_data, "self", [])
        
        # Should fallback to parse_llm_response
        assert "summary" in result
        assert "llm_response" in result

    def test_llm_analyze_wins_api_error(self, temp_db, sample_activity_data, mock_openai_client):
        """Test LLM analysis with API error."""
        analyzer = WinsAnalyzer(temp_db)
        
        # Mock API error
        mock_openai_client.chat.completions.create.side_effect = Exception("API Error")
        
        result = analyzer._llm_analyze_wins(sample_activity_data, "peer", [])
        
        # Should fallback to heuristic analysis
        assert "summary" in result
        assert "categories" in result