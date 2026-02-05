"""Git hook installation for automatic cleanup."""

import os
import stat
from pathlib import Path

from .worktree import get_git_root


POST_FETCH_HOOK = '''#!/bin/bash
# Claude Worktrees - Automatic cleanup hook
# This hook runs after 'git fetch' to clean up merged worktrees

# Check if cw command exists
if command -v cw &> /dev/null; then
    cw cleanup --auto 2>/dev/null || true
fi
'''

POST_MERGE_HOOK = '''#!/bin/bash
# Claude Worktrees - Automatic cleanup hook
# This hook runs after 'git merge' (including pull) to clean up merged worktrees

# Check if cw command exists
if command -v cw &> /dev/null; then
    cw cleanup --auto 2>/dev/null || true
fi
'''


def get_hooks_dir() -> Path | None:
    """Get the git hooks directory for the current repository."""
    git_root = get_git_root()
    if not git_root:
        return None

    # Check for custom hooks path
    hooks_path = git_root / ".git" / "hooks"

    # Handle worktrees where .git is a file pointing to the main repo
    git_path = git_root / ".git"
    if git_path.is_file():
        content = git_path.read_text().strip()
        if content.startswith("gitdir:"):
            git_dir = Path(content[7:].strip())
            if not git_dir.is_absolute():
                git_dir = git_root / git_dir
            hooks_path = git_dir / "hooks"

    return hooks_path


def install_hook(hook_name: str, content: str) -> tuple[bool, str]:
    """Install a git hook.

    Args:
        hook_name: Name of the hook (e.g., 'post-fetch')
        content: Content of the hook script

    Returns:
        Tuple of (success, message)
    """
    hooks_dir = get_hooks_dir()
    if not hooks_dir:
        return False, "Not in a git repository"

    hooks_dir.mkdir(parents=True, exist_ok=True)
    hook_path = hooks_dir / hook_name

    # Check if hook already exists
    if hook_path.exists():
        existing_content = hook_path.read_text()
        if "Claude Worktrees" in existing_content:
            return True, f"Hook {hook_name} already installed"

        # Append to existing hook
        if not existing_content.endswith("\n"):
            existing_content += "\n"
        content = existing_content + "\n" + content

    # Write hook
    hook_path.write_text(content)

    # Make executable
    hook_path.chmod(hook_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    return True, f"Installed {hook_name} hook"


def install_all_hooks() -> list[tuple[str, bool, str]]:
    """Install all claude-worktrees git hooks.

    Returns:
        List of (hook_name, success, message) tuples
    """
    results = []

    # Note: post-fetch doesn't exist as a standard git hook
    # but post-merge runs after 'git pull' which includes a fetch
    hooks_to_install = [
        ("post-merge", POST_MERGE_HOOK),
    ]

    for hook_name, content in hooks_to_install:
        success, message = install_hook(hook_name, content)
        results.append((hook_name, success, message))

    return results


def uninstall_hooks() -> list[tuple[str, bool, str]]:
    """Remove claude-worktrees git hooks.

    Returns:
        List of (hook_name, success, message) tuples
    """
    hooks_dir = get_hooks_dir()
    if not hooks_dir:
        return [("all", False, "Not in a git repository")]

    results = []

    for hook_name in ["post-merge", "post-fetch"]:
        hook_path = hooks_dir / hook_name

        if not hook_path.exists():
            results.append((hook_name, True, "Hook not present"))
            continue

        content = hook_path.read_text()

        if "Claude Worktrees" not in content:
            results.append((hook_name, True, "Hook not managed by claude-worktrees"))
            continue

        # Remove our section from the hook
        lines = content.split("\n")
        new_lines = []
        skip_until_empty = False

        for line in lines:
            if "Claude Worktrees" in line:
                skip_until_empty = True
                continue
            if skip_until_empty:
                if line.strip() == "" or line.startswith("#"):
                    continue
                if line.startswith("if command") or line.startswith("    cw cleanup") or line.startswith("fi"):
                    continue
                skip_until_empty = False
            new_lines.append(line)

        new_content = "\n".join(new_lines).strip()

        if new_content and new_content != "#!/bin/bash":
            hook_path.write_text(new_content + "\n")
            results.append((hook_name, True, "Removed claude-worktrees section"))
        else:
            hook_path.unlink()
            results.append((hook_name, True, "Removed hook file"))

    return results
