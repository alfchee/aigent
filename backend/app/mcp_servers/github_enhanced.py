import os
import logging
from typing import List, Optional
from datetime import datetime

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field
from github import Github, GithubException, Auth

# Initialize FastMCP server
mcp = FastMCP("github-enhanced")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("github-enhanced")

def get_github_client() -> Github:
    """Get authenticated GitHub client from environment variables."""
    token = os.environ.get("GITHUB_PERSONAL_ACCESS_TOKEN")
    if not token:
        raise ValueError("GITHUB_PERSONAL_ACCESS_TOKEN environment variable is required")
    auth = Auth.Token(token)
    return Github(auth=auth)

# --- Helper Models ---

class DateRange(BaseModel):
    start: Optional[str] = Field(None, description="Start date (YYYY-MM-DD)")
    end: Optional[str] = Field(None, description="End date (YYYY-MM-DD)")

class FilterCriteria(BaseModel):
    labels: Optional[List[str]] = Field(None, description="Filter by labels")
    assignee: Optional[str] = Field(None, description="Filter by assignee username")
    milestone: Optional[str] = Field(None, description="Filter by milestone title")
    state: str = Field("open", description="State: open, closed, all")
    sort: str = Field("created", description="Sort by: created, updated, comments")
    direction: str = Field("desc", description="Direction: asc, desc")
    since: Optional[str] = Field(None, description="Only issues updated at or after this time (ISO 8601)")

# --- Tools ---

@mcp.tool()
def search_issues_and_prs(
    query: str,
    sort: Optional[str] = None,
    order: Optional[str] = "desc",
    per_page: int = 30
) -> str:
    """
    Search issues and pull requests using GitHub's powerful search syntax.
    Supports advanced filtering like:
    - created:>2024-01-01
    - updated:2024-01-01..2024-12-31
    - comments:>10
    - reactions:>5
    - label:bug
    - is:pr or is:issue
    """
    try:
        g = get_github_client()
        
        # Construct search query
        final_query = query
        
        # Execute search
        results = g.search_issues(query=final_query, sort=sort or "created", order=order)
        
        items = []
        for i, item in enumerate(results):
            if i >= per_page:
                break
            
            user_login = "unknown"
            if item.user:
                user_login = item.user.login
                
            labels = []
            if item.labels:
                labels = [l.name for l in item.labels]
                
            items.append({
                "number": item.number,
                "title": item.title,
                "state": item.state,
                "html_url": item.html_url,
                "created_at": item.created_at.isoformat(),
                "updated_at": item.updated_at.isoformat(),
                "user": user_login,
                "labels": labels,
                "comments": item.comments,
                "is_pr": item.pull_request is not None
            })
            
        return str(items)
    except GithubException as e:
        logger.error(f"GitHub API Error: {e}", exc_info=True)
        return f"GitHub API Error: {e}"
    except Exception as e:
        logger.error(f"Error in search_issues_and_prs: {e}", exc_info=True)
        return f"Error: {e}"

@mcp.tool()
def list_repository_issues(
    owner: str,
    repo: str,
    state: str = "open",
    labels: Optional[List[str]] = None,
    assignee: Optional[str] = None,
    milestone: Optional[str] = None,
    since: Optional[str] = None,
    sort: str = "created",
    direction: str = "desc"
) -> str:
    """
    List issues in a repository with advanced filtering.
    """
    g = get_github_client()
    try:
        repository = g.get_repo(f"{owner}/{repo}")
        
        # Prepare arguments
        kwargs = {
            "state": state,
            "sort": sort,
            "direction": direction
        }
        
        if labels:
            # PyGithub expects a list of Label objects or strings? 
            # get_issues doc says: labels: list of strings or Label objects
            kwargs["labels"] = labels
            
        if assignee:
            kwargs["assignee"] = assignee
            
        if milestone:
            # We need to fetch the milestone object first if passed as string, 
            # but get_issues expects Milestone object or 'none'/'*'.
            # For simplicity, if it's not special, we try to find it.
            if milestone not in ["none", "*"]:
                m_obj = None
                for m in repository.get_milestones(state="all"):
                    if m.title == milestone:
                        m_obj = m
                        break
                if m_obj:
                    kwargs["milestone"] = m_obj
                else:
                    return f"Error: Milestone '{milestone}' not found."
            else:
                kwargs["milestone"] = milestone

        if since:
            try:
                kwargs["since"] = datetime.fromisoformat(since.replace("Z", "+00:00"))
            except ValueError:
                return "Error: Invalid date format for 'since'. Use ISO 8601 (e.g., 2024-01-01T00:00:00)."

        issues = repository.get_issues(**kwargs)
        
        results = []
        for issue in issues[:30]:  # Limit to 30
            results.append({
                "number": issue.number,
                "title": issue.title,
                "state": issue.state,
                "assignees": [a.login for a in issue.assignees],
                "milestone": issue.milestone.title if issue.milestone else None,
                "labels": [l.name for l in issue.labels],
                "created_at": issue.created_at.isoformat()
            })
            
        return str(results)
    except Exception as e:
        return f"Error: {e}"

@mcp.tool()
def get_pr_details_and_status(
    owner: str,
    repo: str,
    pr_number: int
) -> str:
    """
    Get detailed information about a Pull Request, including:
    - Merge status (mergeable)
    - CI/CD status (combined status)
    - Review status
    """
    g = get_github_client()
    try:
        repository = g.get_repo(f"{owner}/{repo}")
        pr = repository.get_pull(pr_number)
        
        # CI Status
        try:
            head_commit = pr.get_commits().reversed[0]
            combined_status = head_commit.get_combined_status().state
        except IndexError:
            combined_status = "unknown"
            
        # Reviews
        reviews = pr.get_reviews()
        review_states = {}
        for review in reviews:
            review_states[review.user.login] = review.state

        return str({
            "number": pr.number,
            "title": pr.title,
            "state": pr.state,
            "mergeable": pr.mergeable,
            "mergeable_state": pr.mergeable_state,
            "merged": pr.merged,
            "ci_status": combined_status,
            "reviews": review_states,
            "additions": pr.additions,
            "deletions": pr.deletions,
            "changed_files": pr.changed_files
        })
    except Exception as e:
        return f"Error: {e}"

@mcp.tool()
def list_projects(
    owner: str,
    repo: str,
    state: str = "open"
) -> str:
    """
    List projects in a repository.
    """
    g = get_github_client()
    try:
        repository = g.get_repo(f"{owner}/{repo}")
        projects = repository.get_projects(state=state)
        return str([{"id": p.id, "name": p.name, "state": p.state, "number": p.number} for p in projects])
    except Exception as e:
        return f"Error: {e}"

@mcp.tool()
def list_project_columns(
    project_id: int
) -> str:
    """
    List columns in a project.
    """
    g = get_github_client()
    try:
        project = g.get_project(project_id)
        columns = project.get_columns()
        return str([{"id": c.id, "name": c.name} for c in columns])
    except Exception as e:
        return f"Error: {e}"

@mcp.tool()
def create_project_card(
    project_id: int,
    column_id: int,
    note: Optional[str] = None,
    content_id: Optional[int] = None,
    content_type: Optional[str] = None
) -> str:
    """
    Create a project card. 
    Can create a note card (provide 'note') or an issue/PR card (provide 'content_id' and 'content_type').
    """
    g = get_github_client()
    try:
        project = g.get_project(project_id)
        column = project.get_column(column_id)
        
        if note:
            card = column.create_card(note=note)
        elif content_id and content_type:
            card = column.create_card(content_id=content_id, content_type=content_type)
        else:
            return "Error: Must provide either 'note' or 'content_id' and 'content_type'."
            
        return str({
            "id": card.id,
            "note": card.note,
            "url": card.url
        })
    except Exception as e:
        return f"Error: {e}"

@mcp.tool()
def add_issue_comment_threaded(
    owner: str,
    repo: str,
    issue_number: int,
    body: str
) -> str:
    """
    Add a comment to an issue or PR.
    Note: GitHub's REST API treats PR comments and Issue comments slightly differently, 
    but `issue.create_comment` works for the main conversation thread of both.
    """
    g = get_github_client()
    try:
        repository = g.get_repo(f"{owner}/{repo}")
        issue = repository.get_issue(issue_number)
        comment = issue.create_comment(body)
        return str({
            "id": comment.id,
            "url": comment.html_url,
            "body": comment.body,
            "user": comment.user.login
        })
    except Exception as e:
        return f"Error: {e}"

@mcp.tool()
def batch_add_comments(
    owner: str,
    repo: str,
    issue_numbers: List[int],
    body: str
) -> str:
    """
    Add the same comment to multiple issues or PRs (Batch operation).
    """
    g = get_github_client()
    results = {}
    try:
        repository = g.get_repo(f"{owner}/{repo}")
        for num in issue_numbers:
            try:
                issue = repository.get_issue(num)
                issue.create_comment(body)
                results[num] = "Success"
            except Exception as e:
                results[num] = f"Error: {e}"
        return str(results)
    except Exception as e:
        return f"Error accessing repo: {e}"

@mcp.tool()
def get_repo_prs_status(
    owner: str,
    repo: str,
    state: str = "open",
    limit: int = 10
) -> str:
    """
    Get status (CI, Mergeability, Reviews) for multiple PRs in a repository.
    Useful for bulk checks.
    """
    g = get_github_client()
    try:
        repository = g.get_repo(f"{owner}/{repo}")
        prs = repository.get_pulls(state=state, sort="updated", direction="desc")
        
        results = []
        for i, pr in enumerate(prs):
            if i >= limit:
                break
            
            # CI Status
            try:
                head_commit = pr.get_commits().reversed[0]
                combined_status = head_commit.get_combined_status().state
            except IndexError:
                combined_status = "unknown"
            
            results.append({
                "number": pr.number,
                "title": pr.title,
                "mergeable": pr.mergeable,
                "ci_status": combined_status,
                "reviews_count": pr.get_reviews().totalCount
            })
            
        return str(results)
    except Exception as e:
        return f"Error: {e}"

@mcp.tool()
def get_issue_comments(
    owner: str,
    repo: str,
    issue_number: int,
    since: Optional[str] = None
) -> str:
    """
    Get comments for a specific issue or PR.
    Optional 'since' parameter (ISO 8601) to filter comments updated at or after a specific time.
    Returns a list of comments with author, body, and creation date.
    """
    g = get_github_client()
    try:
        repository = g.get_repo(f"{owner}/{repo}")
        issue = repository.get_issue(issue_number)
        
        kwargs = {}
        if since:
            try:
                kwargs["since"] = datetime.fromisoformat(since.replace("Z", "+00:00"))
            except ValueError:
                return "Error: Invalid date format for 'since'. Use ISO 8601 (e.g., 2024-01-01T00:00:00)."

        comments = issue.get_comments(**kwargs)
        
        results = []
        for comment in comments:
            results.append({
                "id": comment.id,
                "user": comment.user.login,
                "body": comment.body,
                "created_at": comment.created_at.isoformat(),
                "updated_at": comment.updated_at.isoformat(),
                "url": comment.html_url
            })
            
        return str(results)
    except Exception as e:
        return f"Error: {e}"

if __name__ == "__main__":
    mcp.run()
