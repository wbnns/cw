# Claude Worktrees

A CLI tool for managing Git worktrees when running multiple Claude Code instances in parallel.

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
1. Creates a new branch named `claude-<unix-timestamp>`
2. Creates a worktree in `~/.claude-worktrees/<repo>/<branch>`
3. Sets up dependency symlinks (node_modules, etc.)
4. Launches Claude Code in the new worktree

## Commands

### `cw` (no arguments)

Create a new worktree with auto-generated name and launch Claude Code.

### `cw new [branch]`

Create a worktree with a specific branch name.

```bash
cw new feature/auth          # Create new branch + worktree
cw new --from existing-branch existing-branch  # Use existing branch
cw new --no-claude           # Don't launch Claude Code
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

Initialize config and install git hooks for automatic cleanup after merges.

## Configuration

Optional config at `~/.claude-worktrees.toml`:

```toml
[global]
worktree_base = "~/.claude-worktrees"
auto_cleanup = true

[deps]
strategy = "symlink"  # symlink | copy | custom
# post_create_hook = "pnpm install --frozen-lockfile"

[github]
check_pr_status = true
```

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
- `gh` CLI (optional, for PR status)
