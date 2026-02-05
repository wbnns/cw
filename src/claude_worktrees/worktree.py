"""Git worktree operations."""

import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from .config import get_repo_worktree_dir


@dataclass
class WorktreeInfo:
    """Information about a git worktree."""
    path: Path
    branch: str
    commit: str
    is_bare: bool = False
    is_detached: bool = False
    prunable: bool = False


def get_git_root() -> Path | None:
    """Get the root directory of the current git repository."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        )
        return Path(result.stdout.strip())
    except subprocess.CalledProcessError:
        return None


def get_repo_name() -> str | None:
    """Get the name of the current git repository."""
    git_root = get_git_root()
    if git_root:
        return git_root.name
    return None


def get_main_branch() -> str:
    """Get the main branch name (main or master)."""
    try:
        result = subprocess.run(
            ["git", "symbolic-ref", "refs/remotes/origin/HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        # refs/remotes/origin/main -> main
        return result.stdout.strip().split("/")[-1]
    except subprocess.CalledProcessError:
        # Fallback: check if main or master exists
        for branch in ["main", "master"]:
            result = subprocess.run(
                ["git", "rev-parse", "--verify", f"refs/heads/{branch}"],
                capture_output=True,
            )
            if result.returncode == 0:
                return branch
        return "main"


def branch_exists(branch: str, remote: bool = False) -> bool:
    """Check if a branch exists locally or remotely."""
    if remote:
        ref = f"refs/remotes/origin/{branch}"
    else:
        ref = f"refs/heads/{branch}"

    result = subprocess.run(
        ["git", "rev-parse", "--verify", ref],
        capture_output=True,
    )
    return result.returncode == 0


def create_branch(branch: str, start_point: str | None = None) -> bool:
    """Create a new branch."""
    cmd = ["git", "branch", branch]
    if start_point:
        cmd.append(start_point)

    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0


def list_worktrees() -> list[WorktreeInfo]:
    """List all git worktrees for the current repository."""
    result = subprocess.run(
        ["git", "worktree", "list", "--porcelain"],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        return []

    worktrees = []
    current_worktree: dict = {}

    for line in result.stdout.strip().split("\n"):
        if not line:
            if current_worktree:
                worktrees.append(WorktreeInfo(
                    path=Path(current_worktree.get("worktree", "")),
                    branch=current_worktree.get("branch", "").replace("refs/heads/", ""),
                    commit=current_worktree.get("HEAD", ""),
                    is_bare=current_worktree.get("bare", False),
                    is_detached=current_worktree.get("detached", False),
                    prunable=current_worktree.get("prunable", False),
                ))
                current_worktree = {}
            continue

        if line.startswith("worktree "):
            current_worktree["worktree"] = line[9:]
        elif line.startswith("HEAD "):
            current_worktree["HEAD"] = line[5:]
        elif line.startswith("branch "):
            current_worktree["branch"] = line[7:]
        elif line == "bare":
            current_worktree["bare"] = True
        elif line == "detached":
            current_worktree["detached"] = True
        elif line.startswith("prunable"):
            current_worktree["prunable"] = True

    # Don't forget the last worktree
    if current_worktree:
        worktrees.append(WorktreeInfo(
            path=Path(current_worktree.get("worktree", "")),
            branch=current_worktree.get("branch", "").replace("refs/heads/", ""),
            commit=current_worktree.get("HEAD", ""),
            is_bare=current_worktree.get("bare", False),
            is_detached=current_worktree.get("detached", False),
            prunable=current_worktree.get("prunable", False),
        ))

    return worktrees


def list_managed_worktrees() -> list[WorktreeInfo]:
    """List only worktrees managed by claude-worktrees (in the worktree base dir)."""
    repo_name = get_repo_name()
    if not repo_name:
        return []

    worktree_dir = get_repo_worktree_dir(repo_name)
    all_worktrees = list_worktrees()

    return [
        wt for wt in all_worktrees
        if str(wt.path).startswith(str(worktree_dir))
    ]


def create_worktree(branch: str, path: Path, create_branch: bool = False) -> tuple[bool, str]:
    """Create a new git worktree.

    Returns:
        Tuple of (success, message)
    """
    cmd = ["git", "worktree", "add"]

    if create_branch:
        cmd.extend(["-b", branch, str(path)])
    else:
        cmd.extend([str(path), branch])

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode == 0:
        return True, f"Created worktree at {path}"
    else:
        return False, result.stderr.strip()


def remove_worktree(path: Path, force: bool = False) -> tuple[bool, str]:
    """Remove a git worktree.

    Returns:
        Tuple of (success, message)
    """
    cmd = ["git", "worktree", "remove"]
    if force:
        cmd.append("--force")
    cmd.append(str(path))

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode == 0:
        return True, f"Removed worktree at {path}"
    else:
        return False, result.stderr.strip()


def has_uncommitted_changes(path: Path) -> bool:
    """Check if a worktree has uncommitted changes."""
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        capture_output=True,
        text=True,
        cwd=path,
    )
    return bool(result.stdout.strip())


def is_branch_merged(branch: str, into: str | None = None) -> bool:
    """Check if a branch has been merged into another branch (default: main)."""
    if into is None:
        into = get_main_branch()

    result = subprocess.run(
        ["git", "branch", "--merged", into],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        return False

    merged_branches = [b.strip().lstrip("* ") for b in result.stdout.strip().split("\n")]
    return branch in merged_branches


def get_worktree_path(branch: str) -> Path:
    """Get the path where a worktree for the given branch should be created."""
    repo_name = get_repo_name()
    if not repo_name:
        raise RuntimeError("Not in a git repository")

    # Sanitize branch name for filesystem
    safe_branch = branch.replace("/", "-")

    return get_repo_worktree_dir(repo_name) / safe_branch


def get_worktree_disk_usage(path: Path) -> int:
    """Get disk usage in bytes for a worktree directory."""
    try:
        result = subprocess.run(
            ["du", "-sk", str(path)],
            capture_output=True,
            text=True,
            check=True,
        )
        # du -sk returns KB
        kb = int(result.stdout.split()[0])
        return kb * 1024
    except (subprocess.CalledProcessError, ValueError, IndexError):
        return 0


def format_size(size_bytes: int) -> str:
    """Format a size in bytes to a human-readable string."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def has_remote() -> bool:
    """Check if the repository has a remote configured."""
    result = subprocess.run(
        ["git", "remote"],
        capture_output=True,
        text=True,
    )
    return bool(result.stdout.strip())


def git_pull() -> tuple[bool, str]:
    """Run git pull. Returns (success, message)."""
    if not has_remote():
        return True, "No remote configured"

    result = subprocess.run(
        ["git", "pull", "--ff-only"],
        capture_output=True,
        text=True,
    )

    if result.returncode == 0:
        return True, "Pulled latest changes"
    else:
        # Don't fail on pull errors (might be offline, etc.)
        return True, "Could not pull (offline or conflicts)"


def get_worktree_age_days(path: Path) -> int:
    """Get the age of a worktree in days based on last modification time."""
    try:
        # Use the .git file in the worktree as the reference
        git_file = path / ".git"
        if git_file.exists():
            mtime = git_file.stat().st_mtime
        else:
            mtime = path.stat().st_mtime

        age_seconds = time.time() - mtime
        return int(age_seconds / 86400)  # Convert to days
    except (OSError, ValueError):
        return 0
