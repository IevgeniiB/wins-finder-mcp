"""Unit tests for GitHub client functionality."""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime
import os

from github.GithubException import GithubException, RateLimitExceededException
from wins_finder.integrations.github_client import GitHubClient
from tests.conftest import create_mock_github_client, create_mock_rate_limit


@pytest.mark.unit
class TestGitHubClient:
    """Test GitHub client functionality."""

    def test_client_initialization(self, temp_db):
        """Test GitHub client initialization."""
        client = GitHubClient(temp_db)
        assert client.db == temp_db
        assert client._github is None
        assert client._api_key is None

    @patch.dict(os.environ, {"GITHUB_TOKEN": "test_token"})
    @patch("wins_finder.integrations.github_client.Github")
    def test_get_github_client_with_token(self, mock_github_class, temp_db):
        """Test getting GitHub client when token is available."""
        mock_github_instance = Mock()
        mock_github_class.return_value = mock_github_instance
        
        client = GitHubClient(temp_db)
        github_client = client._get_github_client()
        
        assert github_client == mock_github_instance
        mock_github_class.assert_called_once_with("test_token")

    @patch.dict(os.environ, {}, clear=True)
    def test_get_github_client_no_token(self, temp_db):
        """Test getting GitHub client when no token is available."""
        client = GitHubClient(temp_db)
        github_client = client._get_github_client()
        
        assert github_client is None

    @patch.dict(os.environ, {"GITHUB_TOKEN": "test_token"})
    @patch("wins_finder.integrations.github_client.Github")
    def test_test_connection_success(self, mock_github_class, temp_db, mock_github_user):
        """Test successful GitHub connection test."""
        mock_github_instance = Mock()
        mock_github_instance.get_user.return_value = mock_github_user
        mock_github_class.return_value = mock_github_instance
        
        client = GitHubClient(temp_db)
        result = client.test_connection()
        
        assert result is True
        mock_github_instance.get_user.assert_called_once()

    def test_test_connection_no_token(self, temp_db):
        """Test connection test without token."""
        client = GitHubClient(temp_db)
        result = client.test_connection()
        
        assert result is False

    @patch.dict(os.environ, {"GITHUB_TOKEN": "test_token"})
    @patch("wins_finder.integrations.github_client.Github")
    def test_test_connection_github_exception(self, mock_github_class, temp_db):
        """Test connection test with GitHub API error."""
        mock_github_instance = Mock()
        mock_github_instance.get_user.side_effect = GithubException(401, "Unauthorized")
        mock_github_class.return_value = mock_github_instance
        
        client = GitHubClient(temp_db)
        result = client.test_connection()
        
        assert result is False

    @patch.dict(os.environ, {"GITHUB_TOKEN": "test_token"})
    @patch("wins_finder.integrations.github_client.Github")
    def test_get_activity_cached(self, mock_github_class, temp_db, sample_github_activity, date_range):
        """Test getting activity when cached data is available."""
        start_date, end_date = date_range
        
        # Pre-cache some data
        temp_db.cache_activity_data(
            source="github",
            data_type="activity",
            data=sample_github_activity,
            timeframe_start=start_date,
            timeframe_end=end_date
        )
        
        client = GitHubClient(temp_db)
        result = client.get_activity(start_date, end_date, use_cache=True)
        
        assert result["from_cache"] is True
        assert result["user"]["login"] == "testuser"
        assert len(result["activities"]) == 3
        # Should not call GitHub API
        mock_github_class.assert_not_called()

    def test_get_activity_no_token(self, temp_db, date_range):
        """Test getting activity without GitHub token."""
        start_date, end_date = date_range
        
        client = GitHubClient(temp_db)
        
        with pytest.raises(ValueError, match="GitHub API key not configured"):
            client.get_activity(start_date, end_date, use_cache=False)

    @patch.dict(os.environ, {"GITHUB_TOKEN": "test_token"})
    @patch("wins_finder.integrations.github_client.Github")
    def test_get_activity_fresh_data(self, mock_github_class, temp_db, date_range, mock_github_api):
        """Test getting fresh activity data from GitHub API."""
        start_date, end_date = date_range
        mock_github_class.return_value = mock_github_api
        
        client = GitHubClient(temp_db)
        result = client.get_activity(start_date, end_date, use_cache=False)
        
        assert result["from_cache"] is False
        assert result["user"]["login"] == "testuser"
        assert result["summary"]["prs_created"] == 0
        assert result["summary"]["commits"] == 0
        assert "rate_limit" in result

    @patch.dict(os.environ, {"GITHUB_TOKEN": "test_token"})
    @patch("wins_finder.integrations.github_client.Github")
    def test_get_activity_rate_limit_exceeded(self, mock_github_class, temp_db, date_range):
        """Test handling of GitHub rate limit exceeded."""
        start_date, end_date = date_range
        
        mock_github_instance = Mock()
        mock_github_instance.get_user.side_effect = RateLimitExceededException(
            403, "Rate limit exceeded", {"x-ratelimit-reset": "1640995200"}
        )
        mock_github_class.return_value = mock_github_instance
        
        client = GitHubClient(temp_db)
        
        with pytest.raises(ValueError, match="GitHub rate limit exceeded"):
            client.get_activity(start_date, end_date, use_cache=False)

    def test_get_pull_requests_empty(self, temp_db, mock_github_api):
        """Test _get_pull_requests with empty results."""
        client = GitHubClient(temp_db)
        
        start_date = datetime(2024, 1, 15)
        end_date = datetime(2024, 1, 21)
        
        prs = client._get_pull_requests(mock_github_api, "testuser", start_date, end_date)
        
        assert prs == []
        mock_github_api.search_issues.assert_called_once()

    def test_get_commits_empty(self, temp_db, mock_github_user):
        """Test _get_commits with empty results.""" 
        client = GitHubClient(temp_db)
        
        mock_github = Mock()
        start_date = datetime(2024, 1, 15)
        end_date = datetime(2024, 1, 21)
        
        commits = client._get_commits(mock_github, mock_github_user, start_date, end_date)
        
        assert commits == []

    def test_get_reviews_empty(self, temp_db, mock_github_api):
        """Test _get_reviews with empty results."""
        client = GitHubClient(temp_db)
        
        start_date = datetime(2024, 1, 15)
        end_date = datetime(2024, 1, 21)
        
        reviews = client._get_reviews(mock_github_api, "testuser", start_date, end_date)
        
        assert reviews == []
        mock_github_api.search_issues.assert_called_once()

    def test_get_issue_comments_empty(self, temp_db, mock_github_api):
        """Test _get_issue_comments with empty results."""
        client = GitHubClient(temp_db)
        
        start_date = datetime(2024, 1, 15) 
        end_date = datetime(2024, 1, 21)
        
        comments = client._get_issue_comments(mock_github_api, "testuser", start_date, end_date)
        
        assert comments == []
        mock_github_api.search_issues.assert_called_once()

    def test_get_rate_limit_info_success(self, temp_db, mock_rate_limit):
        """Test getting rate limit info successfully."""
        client = GitHubClient(temp_db)
        mock_github = create_mock_github_client(rate_limit=mock_rate_limit)
        
        rate_info = client._get_rate_limit_info(mock_github)
        
        assert rate_info["core"]["limit"] == 5000
        assert rate_info["core"]["remaining"] == 4950
        assert rate_info["search"]["limit"] == 30
        assert rate_info["search"]["remaining"] == 25

    def test_get_rate_limit_info_error(self, temp_db):
        """Test getting rate limit info with error."""
        client = GitHubClient(temp_db)
        
        mock_github = Mock()
        mock_github.get_rate_limit.side_effect = Exception("API Error")
        
        rate_info = client._get_rate_limit_info(mock_github)
        
        assert "error" in rate_info
        assert rate_info["error"] == "API Error"

    def test_rate_limit_low_remaining(self, temp_db):
        """Test rate limit info with low remaining calls."""
        client = GitHubClient(temp_db)
        
        # Create rate limit with low remaining calls
        low_rate_limit = create_mock_rate_limit(core_remaining=10, search_remaining=2)
        mock_github = create_mock_github_client(rate_limit=low_rate_limit)
        
        rate_info = client._get_rate_limit_info(mock_github)
        
        assert rate_info["core"]["remaining"] == 10
        assert rate_info["search"]["remaining"] == 2