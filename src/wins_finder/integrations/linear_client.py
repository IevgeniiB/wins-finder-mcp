"""Linear integration client using GraphQL API with caching and metrics."""

import os
import json
import logging
import requests
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone

from wins_finder.database.models import WinsDatabase

logger = logging.getLogger(__name__)

# Linear GraphQL endpoint
LINEAR_API_URL = "https://api.linear.app/graphql"

# API rate limiting configuration
DEFAULT_ISSUE_LIMIT = int(os.getenv("LINEAR_ISSUE_LIMIT", "100"))
DEFAULT_COMMENT_LIMIT = int(os.getenv("LINEAR_COMMENT_LIMIT", "50"))


class LinearClient:
    """Client for fetching Linear activity data using GraphQL API."""

    def __init__(self, db: Optional[WinsDatabase] = None):
        self.db = db or WinsDatabase()
        self._api_key = None

    def test_connection(self, api_key: str = None) -> bool:
        """Test Linear API connection."""
        try:
            api_key = api_key or os.getenv("LINEAR_API_KEY")
            if not api_key:
                return False

            # Test with a simple query to get viewer info
            query = """
            query {
                viewer {
                    id
                    name
                    email
                }
            }
            """

            response = self._make_request(query, api_key=api_key)
            return bool(response and "viewer" in response.get("data", {}))

        except Exception as e:
            logger.error(f"Linear connection test failed: {e}")
            return False

    def get_activity(
        self, start_date: datetime, end_date: datetime, use_cache: bool = True
    ) -> Dict[str, Any]:
        """Get Linear activity for the specified time period."""
        # Check cache first
        if use_cache:
            cached_data = self.db.get_cached_activity(
                "linear", "activity", start_date, end_date, max_age_hours=6
            )
            if cached_data:
                logger.info("Using cached Linear data")
                return {**cached_data, "from_cache": True}

        # Get API key
        api_key = os.getenv("LINEAR_API_KEY")
        if not api_key:
            logger.warning("LINEAR_API_KEY not configured")
            return {"activities": [], "summary": {}, "from_cache": False}

        try:
            # Get user info
            viewer_query = """
            query {
                viewer {
                    id
                    name
                    email
                    displayName
                }
            }
            """

            viewer_response = self._make_request(viewer_query, api_key=api_key)
            if not viewer_response or "data" not in viewer_response or "viewer" not in viewer_response.get("data", {}):
                logger.error(f"Failed to get Linear user info: {viewer_response}")
                raise ValueError("Failed to get Linear user info")

            viewer = viewer_response["data"]["viewer"]

            # Collect activity data
            activity_data = {
                "user": {
                    "id": viewer["id"],
                    "name": viewer.get("name") or viewer.get("displayName", ""),
                    "email": viewer.get("email", ""),
                },
                "activities": [],
                "summary": {
                    "issues_created": 0,
                    "issues_completed": 0,
                    "issues_updated": 0,
                    "comments_made": 0,
                    "projects_contributed": set(),
                    "teams_contributed": set(),
                },
                "from_cache": False,
            }

            # Use basic query approach (filtered GraphQL queries consistently fail)
            logger.info(
                f"Fetching recent issues for date range {start_date} to {end_date}"
            )
            basic_issues = self._get_basic_issues(api_key)
            logger.info(f"Retrieved {len(basic_issues)} recent issues")
            
            if basic_issues:
                # Filter issues to find ones in our date range and calculate statistics
                filtered_issues = []
                for issue in basic_issues:
                    try:
                        updated_dt = datetime.fromisoformat(
                            issue["updated_at"].replace("Z", "+00:00")
                        )
                        if (
                            start_date
                            <= updated_dt.replace(tzinfo=None)
                            <= end_date
                        ):
                            filtered_issues.append(issue)
                    except (ValueError, KeyError):
                        continue

                activity_data["activities"] = filtered_issues
                
                # Calculate summary statistics from filtered issues
                activity_data["summary"]["recent_issues_in_timeframe"] = len(filtered_issues)
                
                # Count issues by state
                completed_states = ["done", "completed", "closed"]
                activity_data["summary"]["issues_completed"] = sum(
                    1 for issue in filtered_issues 
                    if issue.get("state", "").lower() in completed_states
                )
                
                logger.info(
                    f"Found {len(filtered_issues)} issues in timeframe ({activity_data['summary']['issues_completed']} completed)"
                )

            # Convert sets to lists for JSON serialization
            activity_data["summary"]["projects_contributed"] = list(
                activity_data["summary"]["projects_contributed"]
            )
            activity_data["summary"]["teams_contributed"] = list(
                activity_data["summary"]["teams_contributed"]
            )

            # Cache the results
            self.db.cache_activity_data(
                "linear", "activity", activity_data, start_date, end_date
            )

            logger.info(
                f"Fetched Linear activity: {len(activity_data['activities'])} items"
            )
            logger.info(f"Linear summary: {activity_data['summary']}")
            return activity_data

        except Exception as e:
            logger.error(f"Error fetching Linear activity: {e}")
            return {"activities": [], "summary": {}, "from_cache": False}

    def _make_request(
        self, query: str, variables: Dict[str, Any] = None, api_key: str = None
    ) -> Optional[Dict[str, Any]]:
        """Make a GraphQL request to Linear API."""
        api_key = api_key or os.getenv("LINEAR_API_KEY")
        if not api_key:
            return None

        headers = {
            "Authorization": api_key,
            "Content-Type": "application/json",
        }

        payload = {"query": query}
        if variables:
            payload["variables"] = variables

        try:
            response = requests.post(
                LINEAR_API_URL, json=payload, headers=headers, timeout=30
            )
            response.raise_for_status()

            data = response.json()

            # Check for GraphQL errors
            if "errors" in data:
                logger.error(f"Linear GraphQL errors: {data['errors']}")
                # Return the error data instead of None for debugging
                return {"graphql_errors": data["errors"]}

            return data

        except requests.exceptions.RequestException as e:
            logger.error(f"Linear API request failed: {e}")
            return {"request_error": str(e)}
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode Linear API response: {e}")
            return {"json_error": str(e)}
        except Exception as e:
            logger.error(f"Unexpected error in Linear API request: {e}")
            return {"unexpected_error": str(e)}

    def _get_created_issues(
        self, api_key: str, user_id: str, start_date: datetime, end_date: datetime
    ) -> List[Dict[str, Any]]:
        """Get issues created by the user in the time period."""
        # Convert to ISO format
        start_iso = start_date.replace(tzinfo=timezone.utc).isoformat()
        end_iso = end_date.replace(tzinfo=timezone.utc).isoformat()

        query = """
        query($userId: String!, $startDate: DateTime!, $endDate: DateTime!, $first: Int!) {
            issues(
                filter: {
                    createdAt: { gte: $startDate, lte: $endDate }
                    creator: { id: { eq: $userId } }
                }
                first: $first
            ) {
                nodes {
                    id
                    identifier
                    title
                    description
                    state {
                        name
                        type
                    }
                    priority
                    createdAt
                    updatedAt
                    url
                    team {
                        id
                        name
                    }
                    project {
                        id
                        name
                    }
                    labels {
                        nodes {
                            name
                        }
                    }
                }
            }
        }
        """

        variables = {
            "userId": user_id,
            "startDate": start_iso,
            "endDate": end_iso,
            "first": DEFAULT_ISSUE_LIMIT,
        }

        response = self._make_request(query, variables, api_key)
        if (
            not response
            or "data" not in response
            or "issues" not in response.get("data", {})
        ):
            logger.error(f"Invalid response for query: {response}")
            return []

        issues = []
        for issue in response["data"]["issues"]["nodes"]:
            issues.append(
                {
                    "type": "issue_created",
                    "id": issue["id"],
                    "identifier": issue["identifier"],
                    "title": issue["title"],
                    "description": issue.get("description", ""),
                    "state": issue["state"]["name"].lower(),
                    "priority": issue.get("priority", 0),
                    "created_at": issue["createdAt"],
                    "updated_at": issue["updatedAt"],
                    "url": issue["url"],
                    "team": issue.get("team", {}).get("name", ""),
                    "project": issue.get("project", {}).get("name", ""),
                    "labels": [
                        label["name"]
                        for label in issue.get("labels", {}).get("nodes", [])
                    ],
                    "service": "linear",
                }
            )

        return issues

    def _get_assigned_issues(
        self, api_key: str, user_id: str, start_date: datetime, end_date: datetime
    ) -> List[Dict[str, Any]]:
        """Get issues assigned to user that were updated in the time period."""
        start_iso = start_date.replace(tzinfo=timezone.utc).isoformat()
        end_iso = end_date.replace(tzinfo=timezone.utc).isoformat()

        query = """
        query($userId: String!, $startDate: DateTime!, $endDate: DateTime!, $first: Int!) {
            issues(
                filter: {
                    updatedAt: { gte: $startDate, lte: $endDate }
                    assignee: { id: { eq: $userId } }
                }
                first: $first
            ) {
                nodes {
                    id
                    identifier
                    title
                    state {
                        name
                        type
                    }
                    priority
                    createdAt
                    updatedAt
                    url
                    team {
                        id
                        name
                    }
                    project {
                        id
                        name
                    }
                }
            }
        }
        """

        variables = {
            "userId": user_id,
            "startDate": start_iso,
            "endDate": end_iso,
            "first": DEFAULT_ISSUE_LIMIT,
        }

        response = self._make_request(query, variables, api_key)
        if (
            not response
            or "data" not in response
            or "issues" not in response.get("data", {})
        ):
            logger.error(f"Invalid response for query: {response}")
            return []

        issues = []
        for issue in response["data"]["issues"]["nodes"]:
            issues.append(
                {
                    "type": "issue_updated",
                    "id": issue["id"],
                    "identifier": issue["identifier"],
                    "title": issue["title"],
                    "state": issue["state"]["name"].lower(),
                    "priority": issue.get("priority", 0),
                    "created_at": issue["createdAt"],
                    "updated_at": issue["updatedAt"],
                    "url": issue["url"],
                    "team": issue.get("team", {}).get("name", ""),
                    "project": issue.get("project", {}).get("name", ""),
                    "service": "linear",
                }
            )

        return issues

    def _get_user_comments(
        self, api_key: str, user_id: str, start_date: datetime, end_date: datetime
    ) -> List[Dict[str, Any]]:
        """Get comments made by user in the time period."""
        start_iso = start_date.replace(tzinfo=timezone.utc).isoformat()
        end_iso = end_date.replace(tzinfo=timezone.utc).isoformat()

        query = """
        query($userId: String!, $startDate: DateTime!, $endDate: DateTime!, $first: Int!) {
            comments(
                filter: {
                    createdAt: { gte: $startDate, lte: $endDate }
                    user: { id: { eq: $userId } }
                }
                first: $first
            ) {
                nodes {
                    id
                    body
                    createdAt
                    updatedAt
                    url
                    issue {
                        id
                        identifier
                        title
                        team {
                            name
                        }
                    }
                }
            }
        }
        """

        variables = {
            "userId": user_id,
            "startDate": start_iso,
            "endDate": end_iso,
            "first": DEFAULT_COMMENT_LIMIT,
        }

        response = self._make_request(query, variables, api_key)
        if (
            not response
            or "data" not in response
            or "comments" not in response.get("data", {})
        ):
            logger.error(f"Invalid response for comments: {response}")
            return []

        comments = []
        for comment in response["data"]["comments"]["nodes"]:
            comments.append(
                {
                    "type": "comment",
                    "id": comment["id"],
                    "body": comment["body"],
                    "created_at": comment["createdAt"],
                    "updated_at": comment["updatedAt"],
                    "url": comment.get("url", ""),
                    "issue_id": comment.get("issue", {}).get("id", ""),
                    "issue_identifier": comment.get("issue", {}).get("identifier", ""),
                    "issue_title": comment.get("issue", {}).get("title", ""),
                    "team": comment.get("issue", {}).get("team", {}).get("name", ""),
                    "service": "linear",
                }
            )

        return comments

    def _get_recent_issues(
        self, api_key: str, start_date: datetime, end_date: datetime
    ) -> List[Dict[str, Any]]:
        """Get recent issues without user filtering as fallback."""
        start_iso = start_date.replace(tzinfo=timezone.utc).isoformat()
        end_iso = end_date.replace(tzinfo=timezone.utc).isoformat()

        # Simple query without user filters
        query = """
        query($startDate: DateTime!, $endDate: DateTime!, $first: Int!) {
            issues(
                filter: {
                    updatedAt: { gte: $startDate, lte: $endDate }
                }
                first: $first
            ) {
                nodes {
                    id
                    identifier
                    title
                    state {
                        name
                        type
                    }
                    createdAt
                    updatedAt
                    url
                    team {
                        name
                    }
                    creator {
                        name
                        email
                    }
                    assignee {
                        name  
                        email
                    }
                }
            }
        }
        """

        variables = {
            "startDate": start_iso,
            "endDate": end_iso,
            "first": min(DEFAULT_ISSUE_LIMIT, 20),  # Limit to 20 for fallback
        }

        response = self._make_request(query, variables, api_key)
        if (
            not response
            or "data" not in response
            or "issues" not in response.get("data", {})
        ):
            logger.error(f"Invalid response for query: {response}")
            return []

        issues = []
        for issue in response["data"]["issues"]["nodes"]:
            issues.append(
                {
                    "type": "recent_issue",
                    "id": issue["id"],
                    "identifier": issue["identifier"],
                    "title": issue["title"],
                    "state": issue["state"]["name"].lower(),
                    "created_at": issue["createdAt"],
                    "updated_at": issue["updatedAt"],
                    "url": issue["url"],
                    "team": issue.get("team", {}).get("name", ""),
                    "creator": issue.get("creator", {}).get("name", ""),
                    "assignee": issue.get("assignee", {}).get("name", ""),
                    "service": "linear",
                }
            )

        return issues

    def _get_basic_issues(self, api_key: str) -> List[Dict[str, Any]]:
        """Get recent issues using basic query without filters."""
        query = """
        query {
            issues(first: 50) {
                nodes {
                    id
                    identifier
                    title
                    state {
                        name
                        type
                    }
                    createdAt
                    updatedAt
                    url
                    team {
                        name
                    }
                    creator {
                        name
                        email
                    }
                    assignee {
                        name  
                        email
                    }
                }
            }
        }
        """

        response = self._make_request(query, {}, api_key)
        if (
            not response
            or "data" not in response
            or "issues" not in response.get("data", {})
        ):
            logger.error(f"Invalid response for basic issues: {response}")
            return []

        issues = []
        for issue in response["data"]["issues"]["nodes"]:
            issues.append(
                {
                    "type": "issue",
                    "id": issue["id"],
                    "identifier": issue["identifier"],
                    "title": issue["title"],
                    "state": issue["state"]["name"].lower(),
                    "created_at": issue["createdAt"],
                    "updated_at": issue["updatedAt"],
                    "url": issue["url"],
                    "team": (issue.get("team") or {}).get("name", ""),
                    "creator": (issue.get("creator") or {}).get("name", ""),
                    "creator_email": (issue.get("creator") or {}).get("email", ""),
                    "assignee": (issue.get("assignee") or {}).get("name", ""),
                    "assignee_email": (issue.get("assignee") or {}).get("email", ""),
                    "service": "linear",
                }
            )

        return issues

    def debug_queries(self, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Debug method to test Linear queries step by step."""
        api_key = os.getenv("LINEAR_API_KEY")
        if not api_key:
            return {"error": "No LINEAR_API_KEY found"}

        results = {}

        # Test viewer query
        try:
            viewer_query = """
            query {
                viewer {
                    id
                    name
                    email
                    displayName
                }
            }
            """
            viewer_response = self._make_request(viewer_query, api_key=api_key)
            results["viewer"] = viewer_response

            if viewer_response and "viewer" in viewer_response.get("data", {}):
                user_id = viewer_response["data"]["viewer"]["id"]

                # Test simple issues query without user filter
                start_iso = start_date.replace(tzinfo=timezone.utc).isoformat()
                end_iso = end_date.replace(tzinfo=timezone.utc).isoformat()

                simple_query = """
                query($startDate: DateTime!, $endDate: DateTime!) {
                    issues(
                        filter: {
                            updatedAt: { gte: $startDate, lte: $endDate }
                        }
                        first: 5
                    ) {
                        nodes {
                            id
                            identifier
                            title
                            updatedAt
                        }
                    }
                }
                """

                simple_response = self._make_request(
                    simple_query, {"startDate": start_iso, "endDate": end_iso}, api_key
                )
                results["simple_issues"] = simple_response

                # Test even simpler query - just get any issues
                basic_query = """
                query {
                    issues(first: 5) {
                        nodes {
                            id
                            identifier
                            title
                            updatedAt
                        }
                    }
                }
                """

                basic_response = self._make_request(basic_query, {}, api_key)
                results["basic_issues"] = basic_response

                # Test user-filtered query
                user_query = """
                query($userId: String!, $startDate: DateTime!, $endDate: DateTime!) {
                    issues(
                        filter: {
                            updatedAt: { gte: $startDate, lte: $endDate }
                            creator: { id: { eq: $userId } }
                        }
                        first: 5
                    ) {
                        nodes {
                            id
                            identifier
                            title
                            updatedAt
                        }
                    }
                }
                """

                user_response = self._make_request(
                    user_query,
                    {"userId": user_id, "startDate": start_iso, "endDate": end_iso},
                    api_key,
                )
                results["user_issues"] = user_response

        except Exception as e:
            results["error"] = str(e)

        return results
