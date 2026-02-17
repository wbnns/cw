"""Configuration file handling for claude-worktrees."""

import os
import sys
from pathlib import Path
from typing import Any

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib


DEFAULT_CONFIG = {
    "global": {
        "worktree_base": "~/.claude-worktrees",
        "auto_cleanup": True,
    },
    "deps": {
        "strategy": "symlink",  # symlink | copy | custom | auto
        "post_create_hook": None,
    },
    "github": {
        "check_pr_status": True,
    },
}

CONFIG_PATH = Path.home() / ".claude-worktrees.toml"


def load_config() -> dict[str, Any]:
    """Load configuration from ~/.claude-worktrees.toml, with defaults."""
    config = DEFAULT_CONFIG.copy()

    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "rb") as f:
            user_config = tomllib.load(f)

        # Merge user config with defaults
        for section, values in user_config.items():
            if section in config and isinstance(config[section], dict):
                config[section] = {**config[section], **values}
            else:
                config[section] = values

    return config


def get_worktree_base() -> Path:
    """Get the base directory for worktrees."""
    config = load_config()
    base = config["global"]["worktree_base"]
    return Path(os.path.expanduser(base))


def get_deps_strategy() -> str:
    """Get the dependency sharing strategy."""
    config = load_config()
    return config["deps"]["strategy"]


def get_post_create_hook() -> str | None:
    """Get the post-create hook command if configured."""
    config = load_config()
    return config["deps"].get("post_create_hook")


def should_check_pr_status() -> bool:
    """Check if GitHub PR status checking is enabled."""
    config = load_config()
    return config["github"]["check_pr_status"]


def should_auto_cleanup() -> bool:
    """Check if automatic cleanup is enabled."""
    config = load_config()
    return config["global"]["auto_cleanup"]


def create_default_config() -> None:
    """Create a default configuration file if it doesn't exist."""
    if CONFIG_PATH.exists():
        return

    default_content = '''# Claude Worktrees Configuration

[global]
worktree_base = "~/.claude-worktrees"  # Where worktrees are stored
auto_cleanup = true                     # Enable post-fetch cleanup

[deps]
strategy = "symlink"  # symlink | copy | custom | auto
# Strategies:
#   symlink - Symlink node_modules, .venv, etc. from main repo (fast, shared)
#   copy    - Copy-on-write clone of dependency dirs (isolated, macOS only)
#   custom  - Run post_create_hook command (full control)
#   auto    - Detect lockfiles and run appropriate install command
#
# For custom strategy, set post_create_hook:
# post_create_hook = "pnpm install --frozen-lockfile"

[github]
check_pr_status = true  # Use GitHub API to check if PR is merged
'''

    CONFIG_PATH.write_text(default_content)


def get_repo_worktree_dir(repo_name: str) -> Path:
    """Get the worktree directory for a specific repo."""
    return get_worktree_base() / repo_name
