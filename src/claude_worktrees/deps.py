"""Dependency sharing strategies for worktrees."""

import os
import shutil
import subprocess
from pathlib import Path

from .config import get_deps_strategy, get_post_create_hook
from .worktree import get_git_root


# Common dotfiles to symlink (gitignored config files)
DOTFILES = [
    ".env",
    ".env.local",
    ".env.development",
    ".env.development.local",
    ".env.test",
    ".env.test.local",
]

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

# Package manager detection rules: (lockfile, install_command, manager_name)
# Order matters - more specific lockfiles first within each ecosystem
PACKAGE_MANAGER_RULES = [
    # JavaScript/Node - lockfiles (most specific first)
    ("pnpm-lock.yaml", "pnpm install --frozen-lockfile", "pnpm"),
    ("yarn.lock", "yarn install --frozen-lockfile", "yarn"),
    ("bun.lockb", "bun install --frozen-lockfile", "bun"),
    ("package-lock.json", "npm ci", "npm"),

    # Python
    ("Pipfile.lock", "pipenv install --deploy", "pipenv"),
    ("poetry.lock", "poetry install --no-interaction", "poetry"),
    ("requirements.txt", "pip install -r requirements.txt", "pip"),

    # Ruby
    ("Gemfile.lock", "bundle install --frozen", "bundler"),

    # Go
    ("go.sum", "go mod download", "go"),

    # Rust
    ("Cargo.lock", "cargo build", "cargo"),
]

# Map package managers to their ecosystem for deduplication
ECOSYSTEM_MAP = {
    "pnpm": "node",
    "yarn": "node",
    "bun": "node",
    "npm": "node",
    "pipenv": "python",
    "poetry": "python",
    "pip": "python",
    "bundler": "ruby",
    "go": "go",
    "cargo": "rust",
}


def setup_dependencies(worktree_path: Path, strategy: str | None = None) -> tuple[bool, str]:
    """Set up dependencies for a new worktree.

    Args:
        worktree_path: Path to the new worktree
        strategy: Override the configured strategy (symlink, copy, custom, auto)

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
    elif strategy == "auto":
        return _setup_auto_install(worktree_path)
    else:
        return False, f"Unknown dependency strategy: {strategy}"


def _detect_package_managers(worktree_path: Path) -> list[tuple[Path, str, str]]:
    """Detect package managers in the worktree based on lockfiles.

    Args:
        worktree_path: Path to the worktree to analyze

    Returns:
        List of (directory, install_command, manager_name) tuples
    """
    detected = []
    ecosystems_found = set()

    # First, check root directory for lockfiles (handles workspace monorepos)
    for lockfile, command, manager in PACKAGE_MANAGER_RULES:
        lockfile_path = worktree_path / lockfile
        if lockfile_path.exists():
            ecosystem = ECOSYSTEM_MAP.get(manager, manager)
            if ecosystem not in ecosystems_found:
                detected.append((worktree_path, command, manager))
                ecosystems_found.add(ecosystem)

    # If we found lockfiles at root, we're done (workspace monorepo case)
    if detected:
        return detected

    # No root lockfiles - search subdirectories (max depth 2)
    # This handles independent subfolder monorepos
    for depth in range(1, 3):
        pattern = "/".join(["*"] * depth)
        for subdir in worktree_path.glob(pattern):
            if not subdir.is_dir():
                continue
            # Skip hidden directories and common non-project dirs
            if any(part.startswith(".") for part in subdir.relative_to(worktree_path).parts):
                continue
            if subdir.name in ("node_modules", "vendor", "dist", "build", "__pycache__"):
                continue

            for lockfile, command, manager in PACKAGE_MANAGER_RULES:
                lockfile_path = subdir / lockfile
                if lockfile_path.exists():
                    ecosystem = ECOSYSTEM_MAP.get(manager, manager)
                    # Track ecosystem per directory to allow different managers in different subdirs
                    dir_ecosystem_key = (subdir, ecosystem)
                    if dir_ecosystem_key not in ecosystems_found:
                        detected.append((subdir, command, manager))
                        ecosystems_found.add(dir_ecosystem_key)

    return detected


def _setup_auto_install(worktree_path: Path) -> tuple[bool, str]:
    """Auto-detect project type and run appropriate install commands.

    Args:
        worktree_path: Path to the worktree

    Returns:
        Tuple of (success, message)
    """
    detected = _detect_package_managers(worktree_path)

    if not detected:
        return True, "No package managers detected"

    results = []
    all_success = True

    for directory, command, manager in detected:
        rel_path = directory.relative_to(worktree_path) if directory != worktree_path else Path(".")

        result = subprocess.run(
            command,
            shell=True,
            cwd=directory,
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            results.append(f"{manager} ({rel_path}): success")
        else:
            all_success = False
            error_msg = result.stderr.strip() or result.stdout.strip() or "unknown error"
            # Truncate long error messages
            if len(error_msg) > 100:
                error_msg = error_msg[:100] + "..."
            results.append(f"{manager} ({rel_path}): failed - {error_msg}")

    message = "Auto-install: " + "; ".join(results)
    return all_success, message


def _setup_symlinks(worktree_path: Path) -> tuple[bool, str]:
    """Set up symlinks from main repo to worktree for dependencies and dotfiles."""
    main_repo = get_git_root()
    if not main_repo:
        return False, "Could not find main repository"

    linked = []

    # Symlink dependency directories
    for dep_dir in DEPENDENCY_DIRS:
        source = main_repo / dep_dir
        target = worktree_path / dep_dir

        if source.exists() and source.is_dir():
            # Ensure parent directory exists for nested paths like vendor/bundle
            target.parent.mkdir(parents=True, exist_ok=True)

            # Remove existing directory if it exists
            if target.exists():
                if target.is_symlink():
                    target.unlink()
                else:
                    shutil.rmtree(target)

            # Create symlink
            target.symlink_to(source)
            linked.append(dep_dir)

    # Symlink dotfiles
    for dotfile in DOTFILES:
        source = main_repo / dotfile
        target = worktree_path / dotfile

        if source.exists() and source.is_file():
            # Remove existing file if it exists
            if target.exists() or target.is_symlink():
                target.unlink()

            # Create symlink
            target.symlink_to(source)
            linked.append(dotfile)

    if linked:
        return True, f"Symlinked: {', '.join(linked)}"
    else:
        return True, "No dependencies or dotfiles found to symlink"


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

    for dotfile in DOTFILES:
        target = worktree_path / dotfile
        if target.is_symlink():
            target.unlink()
