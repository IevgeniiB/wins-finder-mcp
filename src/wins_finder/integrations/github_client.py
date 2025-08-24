"""GitHub integration client using PyGitHub with caching and metrics."""

from github import Github
from github.GithubException import GithubException, RateLimitExceededException
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import logging

from wins_finder.database.models import WinsDatabase

logger = logging.getLogger(__name__)

# API rate limiting configuration
DEFAULT_PR_LIMIT = 50
DEFAULT_REPO_LIMIT = 10
DEFAULT_COMMIT_LIMIT = 20
DEFAULT_REVIEW_LIMIT = 30
DEFAULT_COMMENT_LIMIT = 20


class GitHubClient:
    """Client for fetching GitHub activity data using PyGitHub."""
    
    def __init__(self, db: Optional[WinsDatabase] = None):
        self.db = db or WinsDatabase()
        self._github = None
        self._api_key = None
    
    def test_connection(self) -> bool:
        """Test GitHub API connection using environment variable."""
        try:
            github = self._get_github_client()
            if not github:
                return False
            # Test with a simple API call
            user = github.get_user()
            user.login  # This will trigger the API call
            return True
        except GithubException as e:
            logger.error(f"GitHub connection test failed: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error testing GitHub connection: {e}")
            return False
    
    def get_activity(
        self, 
        start_date: datetime, 
        end_date: datetime, 
        use_cache: bool = True
    ) -> Dict[str, Any]:
        """Get GitHub activity for the specified time period."""
        # Check cache first
        if use_cache:
            cached_data = self.db.get_cached_activity(
                "github", "activity", start_date, end_date, max_age_hours=6
            )
            if cached_data:
                logger.info("Using cached GitHub data")
                return {**cached_data, "from_cache": True}
        
        # Initialize GitHub client
        github = self._get_github_client()
        if not github:
            raise ValueError(
                "GitHub API key not configured. Please:\n"
                "1. Create a Personal Access Token at https://github.com/settings/personal-access-tokens/new\n"
                "2. Grant permissions: Contents (Read), Issues (Read), Pull requests (Read), Metadata (Read)\n"
                "3. Set GITHUB_TOKEN environment variable or add to claude_desktop_config.json env section"
            )
        
        try:
            # Get authenticated user info
            user = github.get_user()
            username = user.login
            
            # Collect different types of activity
            activity_data = {
                "user": {
                    "login": user.login,
                    "name": user.name,
                    "email": user.email,
                    "public_repos": user.public_repos,
                    "followers": user.followers,
                    "following": user.following
                },
                "activities": [],
                "summary": {
                    "prs_created": 0,
                    "prs_merged": 0, 
                    "commits": 0,
                    "reviews_given": 0,
                    "issues_commented": 0,
                    "repos_contributed": set()
                },
                "rate_limit": self._get_rate_limit_info(github)
            }
            
            # Get pull requests created by user
            prs = self._get_pull_requests(github, username, start_date, end_date)
            activity_data["activities"].extend(prs)
            activity_data["summary"]["prs_created"] = len(prs)
            activity_data["summary"]["prs_merged"] = len([pr for pr in prs if pr.get("merged")])
            
            # Get commits across user's repositories
            commits = self._get_commits(github, user, start_date, end_date)
            activity_data["activities"].extend(commits)
            activity_data["summary"]["commits"] = len(commits)
            
            # Get reviews given by user
            reviews = self._get_reviews(github, username, start_date, end_date)
            activity_data["activities"].extend(reviews)
            activity_data["summary"]["reviews_given"] = len(reviews)
            
            # Get issue comments
            issue_comments = self._get_issue_comments(github, username, start_date, end_date)
            activity_data["activities"].extend(issue_comments)
            activity_data["summary"]["issues_commented"] = len(issue_comments)
            
            # Update contributed repos from all activities
            for activity in activity_data["activities"]:
                if activity.get("repo"):
                    activity_data["summary"]["repos_contributed"].add(activity["repo"])
            
            # Convert set to list for JSON serialization
            activity_data["summary"]["repos_contributed"] = list(activity_data["summary"]["repos_contributed"])
            
            # Cache the results
            self.db.cache_activity_data("github", "activity", activity_data, start_date, end_date)
            
            logger.info(f"Fetched GitHub activity: {len(activity_data['activities'])} items")
            return {**activity_data, "from_cache": False}
        
        except RateLimitExceededException as e:
            reset_time = e.headers.get('x-ratelimit-reset', 'unknown')
            logger.error(f"GitHub rate limit exceeded, resets at {reset_time}")
            raise ValueError(
                f"GitHub rate limit exceeded. Please wait until {reset_time} or upgrade your GitHub plan for higher limits. "
                "Current limits can be viewed at https://docs.github.com/en/rest/overview/resources-in-the-rest-api#rate-limiting"
            )
        except GithubException as e:
            logger.error(f"GitHub API error: {e}")
            raise ValueError(f"GitHub API error: {str(e)}")
        except Exception as e:
            logger.error(f"Error fetching GitHub activity: {e}")
            raise
    
    def _get_pull_requests(
        self, 
        github: Github, 
        username: str, 
        start_date: datetime, 
        end_date: datetime
    ) -> List[Dict[str, Any]]:
        """Get pull requests created by user in the time period."""
        prs = []
        
        try:
            # Search for PRs authored by user
            query = f"author:{username} type:pr created:{start_date.strftime('%Y-%m-%d')}..{end_date.strftime('%Y-%m-%d')}"
            search_results = github.search_issues(query)
            
            for pr in search_results[:DEFAULT_PR_LIMIT]:  # Limit for demo performance
                try:
                    pr_data = {
                        "type": "pull_request", 
                        "title": pr.title,
                        "url": pr.html_url,
                        "created_at": pr.created_at.isoformat(),
                        "state": pr.state,
                        "merged": hasattr(pr, 'pull_request') and pr.pull_request and hasattr(pr.pull_request, 'merged_at') and pr.pull_request.merged_at is not None,
                        "repo": pr.repository.name if pr.repository else "unknown",
                        "labels": [label.name for label in pr.labels],
                        "comments": pr.comments
                    }
                    
                    if hasattr(pr, 'pull_request') and pr.pull_request and pr.pull_request.merged_at:
                        pr_data["merged_at"] = pr.pull_request.merged_at.isoformat()
                    
                    prs.append(pr_data)
                except Exception as e:
                    logger.warning(f"Error processing PR {pr.number}: {e}")
                    continue
        
        except Exception as e:
            logger.warning(f"Error fetching pull requests: {e}")
        
        return prs
    
    def _get_commits(
        self, 
        github: Github,
        user,
        start_date: datetime, 
        end_date: datetime
    ) -> List[Dict[str, Any]]:
        """Get commits by the user in the time period."""
        commits = []
        
        try:
            # Get user's repositories (limited for demo performance)
            repos = list(user.get_repos(type="owner", sort="updated"))[:DEFAULT_REPO_LIMIT]
            
            for repo in repos:
                try:
                    # Get commits in the time range
                    repo_commits = repo.get_commits(
                        author=user,
                        since=start_date,
                        until=end_date
                    )
                    
                    for commit in list(repo_commits)[:DEFAULT_COMMIT_LIMIT]:  # Limit commits per repo
                        commits.append({
                            "type": "commit",
                            "title": commit.commit.message.split('\n')[0][:100],  # First line, truncated
                            "sha": commit.sha[:7],  # Short SHA
                            "url": commit.html_url,
                            "created_at": commit.commit.author.date.isoformat(),
                            "repo": repo.name,
                            "additions": commit.stats.additions if commit.stats else 0,
                            "deletions": commit.stats.deletions if commit.stats else 0,
                            "files_changed": len(commit.files) if commit.files else 0
                        })
                
                except Exception as e:
                    logger.warning(f"Error fetching commits for repo {repo.name}: {e}")
                    continue
        
        except Exception as e:
            logger.warning(f"Error fetching commits: {e}")
        
        return commits
    
    def _get_reviews(
        self, 
        github: Github, 
        username: str, 
        start_date: datetime, 
        end_date: datetime
    ) -> List[Dict[str, Any]]:
        """Get code reviews given by the user."""
        reviews = []
        
        try:
            # Search for PRs where user commented (reviews)
            query = f"commenter:{username} type:pr updated:{start_date.strftime('%Y-%m-%d')}..{end_date.strftime('%Y-%m-%d')}"
            search_results = github.search_issues(query)
            
            for pr in list(search_results)[:DEFAULT_REVIEW_LIMIT]:  # Limit for performance
                try:
                    reviews.append({
                        "type": "review",
                        "title": f"Review on: {pr.title}",
                        "url": pr.html_url,
                        "created_at": pr.updated_at.isoformat(),
                        "repo": pr.repository.name if pr.repository else "unknown",
                        "pr_number": pr.number,
                        "pr_state": pr.state
                    })
                except Exception as e:
                    logger.warning(f"Error processing review for PR {pr.number}: {e}")
                    continue
        
        except Exception as e:
            logger.warning(f"Error fetching reviews: {e}")
        
        return reviews
    
    def _get_issue_comments(
        self, 
        github: Github, 
        username: str, 
        start_date: datetime, 
        end_date: datetime
    ) -> List[Dict[str, Any]]:
        """Get issue comments by the user."""
        comments = []
        
        try:
            # Search for issues where user commented
            query = f"commenter:{username} type:issue updated:{start_date.strftime('%Y-%m-%d')}..{end_date.strftime('%Y-%m-%d')}"
            search_results = github.search_issues(query)
            
            for issue in list(search_results)[:DEFAULT_COMMENT_LIMIT]:  # Limit for performance
                try:
                    comments.append({
                        "type": "issue_comment",
                        "title": f"Comment on: {issue.title}",
                        "url": issue.html_url,
                        "created_at": issue.updated_at.isoformat(),
                        "repo": issue.repository.name if issue.repository else "unknown",
                        "issue_number": issue.number,
                        "issue_state": issue.state,
                        "labels": [label.name for label in issue.labels]
                    })
                except Exception as e:
                    logger.warning(f"Error processing issue comment {issue.number}: {e}")
                    continue
        
        except Exception as e:
            logger.warning(f"Error fetching issue comments: {e}")
        
        return comments
    
    def _get_rate_limit_info(self, github: Github) -> Dict[str, Any]:
        """Get current rate limit information."""
        try:
            rate_limit = github.get_rate_limit()
            return {
                "core": {
                    "limit": rate_limit.core.limit,
                    "remaining": rate_limit.core.remaining,
                    "reset": rate_limit.core.reset.isoformat()
                },
                "search": {
                    "limit": rate_limit.search.limit,
                    "remaining": rate_limit.search.remaining,
                    "reset": rate_limit.search.reset.isoformat()
                }
            }
        except Exception as e:
            logger.warning(f"Error getting rate limit info: {e}")
            return {"error": str(e)}
    
    def _get_github_client(self) -> Optional[Github]:
        """Get authenticated GitHub client from environment variable."""
        if not self._github:
            import os
            api_key = os.getenv("GITHUB_TOKEN")
            if api_key:
                self._github = Github(api_key)
        return self._github