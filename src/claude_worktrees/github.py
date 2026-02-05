"""GitHub PR status checking using the gh CLI."""

import json
import subprocess
from dataclasses import dataclass
from enum import Enum


class PRState(Enum):
    """State of a GitHub pull request."""
    OPEN = "open"
    MERGED = "merged"
    CLOSED = "closed"
    NOT_FOUND = "not_found"
    ERROR = "error"


@dataclass
class PRInfo:
    """Information about a GitHub pull request."""
    number: int | None
    title: str
    state: PRState
    url: str | None = None

    @property
    def is_merged(self) -> bool:
        return self.state == PRState.MERGED

    @property
    def is_closed(self) -> bool:
        return self.state in (PRState.MERGED, PRState.CLOSED)


def is_gh_available() -> bool:
    """Check if the gh CLI is available and authenticated."""
    result = subprocess.run(
        ["gh", "auth", "status"],
        capture_output=True,
    )
    return result.returncode == 0


def get_pr_for_branch(branch: str) -> PRInfo | None:
    """Get PR information for a branch using the gh CLI.

    Returns:
        PRInfo if a PR exists for the branch, None otherwise
    """
    if not is_gh_available():
        return None

    # Try to find a PR for this branch
    result = subprocess.run(
        ["gh", "pr", "list", "--head", branch, "--state", "all", "--json",
         "number,title,state,url", "--limit", "1"],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        return None

    try:
        prs = json.loads(result.stdout)
        if not prs:
            return None

        pr = prs[0]
        state_str = pr.get("state", "").upper()

        if state_str == "OPEN":
            state = PRState.OPEN
        elif state_str == "MERGED":
            state = PRState.MERGED
        elif state_str == "CLOSED":
            state = PRState.CLOSED
        else:
            state = PRState.NOT_FOUND

        return PRInfo(
            number=pr.get("number"),
            title=pr.get("title", ""),
            state=state,
            url=pr.get("url"),
        )
    except (json.JSONDecodeError, KeyError):
        return None


def get_pr_status_badge(pr_info: PRInfo | None) -> str:
    """Get a colored status badge for a PR."""
    if pr_info is None:
        return "[dim]no PR[/dim]"

    if pr_info.state == PRState.OPEN:
        return f"[green]PR #{pr_info.number} open[/green]"
    elif pr_info.state == PRState.MERGED:
        return f"[magenta]PR #{pr_info.number} merged[/magenta]"
    elif pr_info.state == PRState.CLOSED:
        return f"[red]PR #{pr_info.number} closed[/red]"
    else:
        return "[dim]no PR[/dim]"


def is_pr_merged(branch: str) -> bool:
    """Quick check if a PR for a branch has been merged."""
    pr_info = get_pr_for_branch(branch)
    return pr_info is not None and pr_info.is_merged


def is_pr_closed(branch: str) -> bool:
    """Quick check if a PR for a branch is closed (merged or closed without merging)."""
    pr_info = get_pr_for_branch(branch)
    return pr_info is not None and pr_info.is_closed
