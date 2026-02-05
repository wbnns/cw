"""Dependency sharing strategies for worktrees."""

import os
import shutil
import subprocess
from pathlib import Path

from .config import get_deps_strategy, get_post_create_hook
from .worktree import get_git_root


# Common dependency directories to share (not build outputs)
DEPENDENCY_DIRS = [
    # JavaScript/Node (Rails uses these too for assets)
    "node_modules",
    ".pnpm-store",
    ".yarn/cache",

    # Ruby/Rails
    "vendor/bundle",
    ".bundle",

    # Python/Django
    ".venv",
    "venv",
    "env",

    # PHP (Composer)
    "vendor",

    # Go modules
    "vendor",

    # Elixir/Mix
    "deps",

    # iOS/macOS (CocoaPods)
    "Pods",

    # Java/Kotlin (Gradle cache)
    ".gradle",
]


def setup_dependencies(worktree_path: Path, strategy: str | None = None) -> tuple[bool, str]:
    """Set up dependencies for a new worktree.

    Args:
        worktree_path: Path to the new worktree
        strategy: Override the configured strategy (symlink, copy, custom)

    Returns:
        Tuple of (success, message)
    """
    if strategy is None:
        strategy = get_deps_strategy()

    if strategy == "symlink":
        return _setup_symlinks(worktree_path)
    elif strategy == "copy":
        return _setup_copy_on_write(worktree_path)
    elif strategy == "custom":
        return _run_custom_hook(worktree_path)
    else:
        return False, f"Unknown dependency strategy: {strategy}"


def _setup_symlinks(worktree_path: Path) -> tuple[bool, str]:
    """Set up symlinks from main repo to worktree for dependency directories."""
    main_repo = get_git_root()
    if not main_repo:
        return False, "Could not find main repository"

    linked = []

    for dep_dir in DEPENDENCY_DIRS:
        source = main_repo / dep_dir
        target = worktree_path / dep_dir

        if source.exists() and source.is_dir():
            # Remove existing directory if it exists
            if target.exists():
                if target.is_symlink():
                    target.unlink()
                else:
                    shutil.rmtree(target)

            # Create symlink
            target.symlink_to(source)
            linked.append(dep_dir)

    if linked:
        return True, f"Symlinked: {', '.join(linked)}"
    else:
        return True, "No dependency directories found to symlink"


def _setup_copy_on_write(worktree_path: Path) -> tuple[bool, str]:
    """Set up copy-on-write copies of dependency directories (macOS only)."""
    main_repo = get_git_root()
    if not main_repo:
        return False, "Could not find main repository"

    copied = []

    for dep_dir in DEPENDENCY_DIRS:
        source = main_repo / dep_dir
        target = worktree_path / dep_dir

        if source.exists() and source.is_dir():
            # Remove existing directory if it exists
            if target.exists():
                shutil.rmtree(target)

            # Use cp -c for copy-on-write on macOS
            result = subprocess.run(
                ["cp", "-cR", str(source), str(target)],
                capture_output=True,
                text=True,
            )

            if result.returncode == 0:
                copied.append(dep_dir)
            else:
                # Fallback to regular copy if CoW not supported
                shutil.copytree(source, target)
                copied.append(f"{dep_dir} (regular copy)")

    if copied:
        return True, f"Copied (CoW): {', '.join(copied)}"
    else:
        return True, "No dependency directories found to copy"


def _run_custom_hook(worktree_path: Path) -> tuple[bool, str]:
    """Run a custom post-create hook for dependency setup."""
    hook_cmd = get_post_create_hook()

    if not hook_cmd:
        return True, "No custom hook configured"

    result = subprocess.run(
        hook_cmd,
        shell=True,
        cwd=worktree_path,
        capture_output=True,
        text=True,
    )

    if result.returncode == 0:
        return True, f"Custom hook completed: {hook_cmd}"
    else:
        return False, f"Custom hook failed: {result.stderr}"


def cleanup_symlinks(worktree_path: Path) -> None:
    """Clean up symlinks before removing a worktree."""
    for dep_dir in DEPENDENCY_DIRS:
        target = worktree_path / dep_dir
        if target.is_symlink():
            target.unlink()
