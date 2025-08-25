"""Pytest configuration and shared fixtures."""

import pytest
import tempfile
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from wins_finder.database.models import WinsDatabase


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    
    db_url = f"sqlite:///{db_path}"
    db = WinsDatabase(db_url)
    yield db
    
    # Cleanup - close engine connections
    if hasattr(db.engine, 'dispose'):
        db.engine.dispose()
    Path(db_path).unlink(missing_ok=True)


@pytest.fixture
def sample_github_activity():
    """Sample GitHub activity data for testing."""
    return {
        "user": {
            "login": "testuser",
            "name": "Test User",
            "email": "test@example.com",
            "public_repos": 10,
            "followers": 50,
            "following": 25,
        },
        "activities": [
            {
                "type": "pull_request",
                "title": "Add user authentication feature",
                "url": "https://github.com/org/repo/pull/123",
                "created_at": "2024-01-15T10:00:00Z",
                "state": "merged",
                "merged": True,
                "repo": "test-repo",
                "labels": ["feature", "authentication"],
                "comments": 5,
            },
            {
                "type": "commit",
                "title": "Fix database connection bug",
                "sha": "abc1234",
                "url": "https://github.com/org/repo/commit/abc1234",
                "created_at": "2024-01-16T14:30:00Z",
                "repo": "test-repo",
                "additions": 25,
                "deletions": 10,
                "files_changed": 3,
            },
            {
                "type": "review",
                "title": "Review on: Implement password reset",
                "url": "https://github.com/org/repo/pull/124",
                "created_at": "2024-01-17T09:15:00Z",
                "repo": "test-repo",
                "pr_number": 124,
                "pr_state": "open",
            },
        ],
        "summary": {
            "prs_created": 1,
            "prs_merged": 1,
            "commits": 1,
            "reviews_given": 1,
            "issues_commented": 0,
            "repos_contributed": ["test-repo"],
        },
        "rate_limit": {
            "core": {"limit": 5000, "remaining": 4950, "reset": "2024-01-18T00:00:00Z"},
            "search": {"limit": 30, "remaining": 25, "reset": "2024-01-18T00:00:00Z"},
        },
    }


@pytest.fixture
def sample_activity_data(sample_github_activity):
    """Sample multi-service activity data."""
    return {
        "github": sample_github_activity,
        "linear": {"activities": [], "summary": {}, "from_cache": False},
        "notion": {"activities": [], "summary": {}, "from_cache": False},
    }


@pytest.fixture
def sample_wins_data():
    """Sample analyzed wins data."""
    return {
        "summary": {
            "total_activities": 3,
            "cross_service_correlations": 1,
            "services_used": ["github"],
            "key_insight": "Strong technical contribution with authentication focus",
        },
        "categories": {
            "technical_contribution": {
                "title": "Code Contributions",
                "description": "Created 1 pull requests, made 1 commits",
                "impact": "high",
                "evidence_count": 2,
            },
            "collaboration": {
                "title": "Code Review & Collaboration",
                "description": "Provided 1 code reviews",
                "impact": "medium",
                "evidence_count": 1,
            },
        },
        "correlations": [
            {
                "type": "feature_delivery",
                "title": "Authentication feature implementation",
                "description": "Complete feature delivery with PR and follow-up fixes",
                "confidence": 0.9,
                "activities": [
                    {"service": "github", "type": "pull_request", "title": "Add user authentication feature"},
                    {"service": "github", "type": "commit", "title": "Fix database connection bug"},
                ],
            }
        ],
        "top_wins": [
            {
                "title": "Successfully delivered authentication feature",
                "description": "Implemented complete user authentication with security best practices",
                "impact": "high",
                "evidence": ["https://github.com/org/repo/pull/123"],
            }
        ],
    }


@pytest.fixture
def mock_github_client():
    """Mock GitHub client for testing."""
    mock_client = Mock()
    mock_client.test_connection.return_value = True
    mock_client.get_activity.return_value = {
        "activities": [],
        "summary": {"prs_created": 0},
        "from_cache": False,
    }
    return mock_client


@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client for LLM testing."""
    mock_client = Mock()
    mock_response = Mock()
    mock_response.choices = [
        Mock(message=Mock(content='{"summary": {"total_activities": 1}, "categories": {}}'))
    ]
    mock_client.chat.completions.create.return_value = mock_response
    return mock_client


@pytest.fixture
def date_range():
    """Standard date range for testing."""
    start_date = datetime(2024, 1, 15)
    end_date = datetime(2024, 1, 21)
    return start_date, end_date


# Helper functions for creating mock objects
def create_mock_github_user(
    login="testuser",
    name="Test User", 
    email="test@example.com",
    public_repos=10,
    followers=50,
    following=25
):
    """Create a mock GitHub user object."""
    mock_user = Mock()
    mock_user.login = login
    mock_user.name = name
    mock_user.email = email
    mock_user.public_repos = public_repos
    mock_user.followers = followers
    mock_user.following = following
    mock_user.get_repos.return_value = []  # Default empty repos
    return mock_user


def create_mock_rate_limit(
    core_limit=5000,
    core_remaining=4950,
    search_limit=30,
    search_remaining=25,
    reset_time=None
):
    """Create a mock GitHub rate limit object."""
    if reset_time is None:
        reset_time = datetime(2024, 1, 18)
    
    mock_core_limit = Mock()
    mock_core_limit.limit = core_limit
    mock_core_limit.remaining = core_remaining
    mock_core_limit.reset = reset_time
    
    mock_search_limit = Mock()
    mock_search_limit.limit = search_limit
    mock_search_limit.remaining = search_remaining
    mock_search_limit.reset = reset_time
    
    mock_rate_limit = Mock()
    mock_rate_limit.core = mock_core_limit
    mock_rate_limit.search = mock_search_limit
    
    return mock_rate_limit


def create_mock_github_client(user=None, rate_limit=None, search_results=None):
    """Create a fully configured mock GitHub client."""
    mock_github = Mock()
    
    # Set up user
    if user is None:
        user = create_mock_github_user()
    mock_github.get_user.return_value = user
    
    # Set up rate limit
    if rate_limit is None:
        rate_limit = create_mock_rate_limit()
    mock_github.get_rate_limit.return_value = rate_limit
    
    # Set up search results
    if search_results is None:
        search_results = []
    mock_github.search_issues.return_value = search_results
    
    return mock_github


@pytest.fixture
def mock_github_user():
    """Fixture for mock GitHub user."""
    return create_mock_github_user()


@pytest.fixture 
def mock_rate_limit():
    """Fixture for mock GitHub rate limit."""
    return create_mock_rate_limit()


@pytest.fixture
def mock_github_api():
    """Fixture for fully configured mock GitHub client."""
    return create_mock_github_client()