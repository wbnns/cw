# cw

Git worktree manager for running multiple Claude Code instances in parallel.

## Installation

```bash
pipx install -e ~/claude-worktrees
```

After installation, the `cw` command is available globally.

## Quick Start

```bash
# Navigate to any git repository
cd your-repo

# Create a worktree and launch Claude Code
cw
```

That's it. Running `cw` with no arguments:
1. Auto-initializes config and git hooks (first run only)
2. Creates a new branch named `claude-<unix-timestamp>`
3. Creates a worktree in `~/.claude-worktrees/<repo>/<branch>`
4. Symlinks dependency directories from the main repo
5. Launches Claude Code in the new worktree

## Commands

### `cw` (no arguments)

Create a new worktree with auto-generated name and launch Claude Code.

### `cw new [branch]`

Create a worktree with a specific branch name.

```bash
cw new feature/auth          # Create new branch + worktree
cw new --from existing-branch existing-branch  # Use existing branch
cw new --no-claude           # Don't launch Claude Code
cw new --no-deps             # Skip dependency symlinking
```

### `cw list`

List all managed worktrees with status, PR info, and disk usage.

### `cw cleanup`

Remove worktrees for merged branches.

```bash
cw cleanup              # Interactive
cw cleanup --dry-run    # Preview what would be removed
cw cleanup --force      # Remove without prompting
```

### `cw remove <branch>`

Remove a specific worktree.

### `cw open <branch>`

Launch Claude Code in an existing worktree.

### `cw init`

Manually initialize config and git hooks. This runs automatically on first `cw` use, so you typically don't need this.

## Dependency Sharing

To avoid reinstalling dependencies for each worktree, `cw` symlinks common dependency directories from your main repo:

- **JavaScript/Node:** `node_modules`, `.pnpm-store`, `.yarn/cache`
- **Ruby:** `vendor/bundle`
- **Python:** `.venv`, `venv`
- **PHP:** `vendor`
- **Go:** `vendor`
- **Elixir:** `deps`
- **iOS/macOS:** `Pods`
- **Java/Kotlin:** `.gradle`

All worktrees share the same dependencies, saving disk space and install time.

## Configuration

Optional config at `~/.claude-worktrees.toml`:

```toml
[global]
worktree_base = "~/.claude-worktrees"
auto_cleanup = true

[deps]
strategy = "symlink"  # symlink | copy | custom
# post_create_hook = "bundle install"  # for custom strategy

[github]
check_pr_status = true  # Check PR merge status via gh CLI
```

### Dependency Strategies

- **symlink** (default): Symlinks deps from main repo. Fast, saves space.
- **copy**: Copy-on-write copies (macOS). Independent but space-efficient.
- **custom**: Run your own command via `post_create_hook`.

## Automatic Cleanup

A git `post-merge` hook is installed that runs `cw cleanup --auto` after each `git pull`. This removes worktrees whose branches have been merged into main.

## Directory Structure

```
~/.claude-worktrees/
└── my-project/
    ├── claude-1738789200/
    ├── claude-1738789500/
    └── feature-auth/
```

## Requirements

- Python 3.10+
- Git
- Claude Code CLI (`claude`)
- `gh` CLI (optional, for PR status checking)
