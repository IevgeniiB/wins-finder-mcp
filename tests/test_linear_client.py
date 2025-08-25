"""Unit tests for Linear client functionality."""

import pytest
import os
from datetime import datetime
from unittest.mock import Mock, patch

from wins_finder.integrations.linear_client import LinearClient


@pytest.mark.unit
class TestLinearClient:
    """Test Linear client functionality."""

    def test_linear_client_initialization(self, temp_db):
        """Test Linear client initialization."""
        client = LinearClient(temp_db)
        assert client.db == temp_db
        assert client._api_key is None

    @patch.dict(os.environ, {"LINEAR_API_KEY": "test_api_key"})
    @patch("wins_finder.integrations.linear_client.requests.post")
    def test_test_connection_success(self, mock_post, temp_db):
        """Test successful Linear connection test."""
        # Mock successful response
        mock_response = Mock()
        mock_response.json.return_value = {
            "data": {
                "viewer": {
                    "id": "user123",
                    "name": "Test User",
                    "email": "test@example.com",
                }
            }
        }
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        client = LinearClient(temp_db)
        result = client.test_connection()

        assert result is True
        mock_post.assert_called_once()

    @patch.dict(os.environ, {}, clear=True)
    def test_test_connection_no_api_key(self, temp_db):
        """Test connection test without API key."""
        client = LinearClient(temp_db)
        result = client.test_connection()

        assert result is False

    @patch.dict(os.environ, {"LINEAR_API_KEY": "test_api_key"})
    @patch("wins_finder.integrations.linear_client.requests.post")
    def test_test_connection_api_error(self, mock_post, temp_db):
        """Test connection test with API error."""
        mock_post.side_effect = Exception("API Error")

        client = LinearClient(temp_db)
        result = client.test_connection()

        assert result is False

    @patch.dict(os.environ, {}, clear=True)
    def test_get_activity_no_api_key(self, temp_db):
        """Test get_activity without API key."""
        client = LinearClient(temp_db)
        start_date = datetime(2024, 1, 15)
        end_date = datetime(2024, 1, 21)

        result = client.get_activity(start_date, end_date, use_cache=False)

        assert result == {"activities": [], "summary": {}, "from_cache": False}

    @patch.dict(os.environ, {"LINEAR_API_KEY": "test_api_key"})
    def test_get_activity_with_cache(self, temp_db, sample_linear_activity):
        """Test get_activity with cached data."""
        start_date = datetime(2024, 1, 15)
        end_date = datetime(2024, 1, 21)

        # Mock cached data
        with patch.object(
            temp_db, "get_cached_activity", return_value=sample_linear_activity
        ):
            client = LinearClient(temp_db)
            result = client.get_activity(start_date, end_date, use_cache=True)

        assert result["from_cache"] is True
        assert "user" in result

    @patch.dict(os.environ, {"LINEAR_API_KEY": "test_api_key"})
    @patch("wins_finder.integrations.linear_client.requests.post")
    def test_get_activity_success(self, mock_post, temp_db):
        """Test successful activity retrieval."""
        start_date = datetime(2024, 1, 15)
        end_date = datetime(2024, 1, 21)

        # Mock API responses
        viewer_response = Mock()
        viewer_response.json.return_value = {
            "data": {
                "viewer": {
                    "id": "user123",
                    "name": "Test User",
                    "email": "test@example.com",
                    "displayName": "Test User",
                }
            }
        }
        viewer_response.raise_for_status.return_value = None

        issues_response = Mock()
        issues_response.json.return_value = {
            "data": {
                "issues": {
                    "nodes": [
                        {
                            "id": "issue123",
                            "identifier": "TEST-1",
                            "title": "Test issue",
                            "description": "Test description",
                            "state": {"name": "In Progress", "type": "started"},
                            "priority": 1,
                            "createdAt": "2024-01-15T10:00:00Z",
                            "updatedAt": "2024-01-15T11:00:00Z",
                            "url": "https://linear.app/test/issue/TEST-1",
                            "team": {"id": "team1", "name": "Test Team"},
                            "project": {"id": "proj1", "name": "Test Project"},
                            "labels": {"nodes": [{"name": "bug"}]},
                        }
                    ]
                }
            }
        }
        issues_response.raise_for_status.return_value = None

        comments_response = Mock()
        comments_response.json.return_value = {
            "data": {
                "comments": {
                    "nodes": [
                        {
                            "id": "comment123",
                            "body": "Test comment",
                            "createdAt": "2024-01-16T10:00:00Z",
                            "updatedAt": "2024-01-16T10:00:00Z",
                            "url": "https://linear.app/test/comment/123",
                            "issue": {
                                "id": "issue123",
                                "identifier": "TEST-1",
                                "title": "Test issue",
                                "team": {"name": "Test Team"},
                            },
                        }
                    ]
                }
            }
        }
        comments_response.raise_for_status.return_value = None

        # Mock sequence of responses (viewer, basic issues query only)
        mock_post.side_effect = [
            viewer_response,
            issues_response,  # This is now the basic issues query response
        ]

        # Mock cache methods
        with (
            patch.object(temp_db, "get_cached_activity", return_value=None),
            patch.object(temp_db, "cache_activity_data") as mock_cache,
        ):
            client = LinearClient(temp_db)
            result = client.get_activity(start_date, end_date, use_cache=False)

        assert result["from_cache"] is False
        assert "user" in result
        assert result["user"]["id"] == "user123"
        assert len(result["activities"]) == 1  # 1 issue from basic query
        assert result["summary"]["recent_issues_in_timeframe"] == 1
        assert result["summary"]["issues_completed"] == 0  # "In Progress" is not a completed state

        # Verify caching was called
        mock_cache.assert_called_once()

    @patch.dict(os.environ, {"LINEAR_API_KEY": "test_api_key"})
    @patch("wins_finder.integrations.linear_client.requests.post")
    def test_make_request_success(self, mock_post, temp_db):
        """Test successful GraphQL request."""
        mock_response = Mock()
        mock_response.json.return_value = {"data": {"test": "success"}}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        client = LinearClient(temp_db)
        result = client._make_request("query { test }")

        assert result == {"data": {"test": "success"}}
        mock_post.assert_called_once()

    @patch.dict(os.environ, {"LINEAR_API_KEY": "test_api_key"})
    @patch("wins_finder.integrations.linear_client.requests.post")
    def test_make_request_graphql_errors(self, mock_post, temp_db):
        """Test GraphQL request with errors."""
        mock_response = Mock()
        mock_response.json.return_value = {"errors": [{"message": "Invalid query"}]}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        client = LinearClient(temp_db)
        result = client._make_request("invalid query")

        assert result == {"graphql_errors": [{"message": "Invalid query"}]}

    @patch.dict(os.environ, {"LINEAR_API_KEY": "test_api_key"})
    @patch("wins_finder.integrations.linear_client.requests.post")
    def test_make_request_network_error(self, mock_post, temp_db):
        """Test GraphQL request with network error."""
        mock_post.side_effect = Exception("Network error")

        client = LinearClient(temp_db)
        result = client._make_request("query { test }")

        assert result == {"unexpected_error": "Network error"}



@pytest.fixture
def sample_linear_activity():
    """Sample Linear activity data for testing."""
    return {
        "user": {"id": "user123", "name": "Test User", "email": "test@example.com"},
        "activities": [
            {
                "type": "issue_created",
                "id": "issue123",
                "identifier": "TEST-1",
                "title": "Test issue",
                "description": "Test description",
                "state": "in progress",
                "priority": 1,
                "created_at": "2024-01-15T10:00:00Z",
                "updated_at": "2024-01-15T11:00:00Z",
                "url": "https://linear.app/test/issue/TEST-1",
                "team": "Test Team",
                "project": "Test Project",
                "labels": ["bug"],
                "service": "linear",
            }
        ],
        "summary": {
            "issues_created": 1,
            "issues_completed": 0,
            "issues_updated": 0,
            "comments_made": 0,
            "projects_contributed": [],
            "teams_contributed": [],
        },
        "from_cache": False,
    }
