# cw

Git worktree manager for running multiple Claude Code instances in parallel.

## Installation

Clone or download this repository anywhere on your system, then install with pipx:

```bash
git clone https://github.com/wbnns/claude-worktrees ~/claude-worktrees
pipx install ~/claude-worktrees
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
- **Ruby/Rails:** `vendor/bundle`, `.bundle`
- **Python/Django:** `.venv`, `venv`, `env`
- **PHP:** `vendor`
- **Go:** `vendor`
- **Elixir:** `deps`
- **iOS/macOS:** `Pods`
- **Java/Kotlin:** `.gradle`

All worktrees share the same dependencies, saving disk space and install time.

## Dotfiles

`cw` also symlinks common environment dotfiles so your config is available in each worktree:

- `.env`
- `.env.local`
- `.env.development`
- `.env.development.local`
- `.env.test`
- `.env.test.local`

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

Running `cw` automatically:
1. Pulls latest changes from remote (if configured)
2. Triggers the `post-merge` hook which cleans up stale worktrees

Worktrees are cleaned up when:
- **Branch merged locally** - detected via `git branch --merged`
- **PR merged on GitHub** - detected via `gh` CLI
- **PR closed on GitHub** - abandoned PRs
- **Older than 7 days** - with no active PR (for repos without GitHub)

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
