"""CLI entry point for claude-worktrees."""

import os
import subprocess
import sys
import time
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from . import __version__
from .config import (
    CONFIG_PATH,
    create_default_config,
    get_worktree_base,
    should_auto_cleanup,
    should_check_pr_status,
)
from .deps import cleanup_symlinks, setup_dependencies
from .github import get_pr_for_branch, get_pr_status_badge, is_pr_closed
from .hooks import install_all_hooks
from .worktree import (
    branch_exists,
    create_branch,
    create_worktree,
    format_size,
    get_git_root,
    get_main_branch,
    get_repo_name,
    get_worktree_age_days,
    get_worktree_disk_usage,
    get_worktree_path,
    git_pull,
    has_remote,
    has_uncommitted_changes,
    is_branch_merged,
    list_managed_worktrees,
    remove_worktree,
)

console = Console()


def ensure_git_repo():
    """Ensure we're in a git repository, exit with error if not."""
    git_root = get_git_root()
    if not git_root:
        console.print("[red]Error:[/red] Not in a git repository")
        console.print("Please run this command from within a git repository.")
        sys.exit(1)
    return git_root


def auto_init():
    """Silently initialize if not already done (config + hooks)."""
    # Create config if needed
    if not CONFIG_PATH.exists():
        create_default_config()

    # Create worktree base directory
    worktree_base = get_worktree_base()
    worktree_base.mkdir(parents=True, exist_ok=True)

    # Install hooks silently
    install_all_hooks()


@click.group(invoke_without_command=True)
@click.version_option(version=__version__)
@click.pass_context
def cli(ctx):
    """Claude Worktrees - Create worktrees for parallel Claude Code instances.

    Run without arguments to create a new worktree and launch Claude Code.
    """
    if ctx.invoked_subcommand is None:
        # Default action: create new worktree with unix timestamp and launch Claude
        git_root = ensure_git_repo()
        repo_name = get_repo_name()

        # Auto-initialize (config, hooks) if not already done
        auto_init()

        # Pull latest changes (triggers post-merge hook for cleanup)
        if has_remote():
            console.print("Pulling latest changes...")
            git_pull()

        # Create branch name from unix timestamp
        timestamp = int(time.time())
        branch = f"claude-{timestamp}"

        # Get worktree path
        worktree_path = get_worktree_path(branch)

        # Create parent directory
        worktree_path.parent.mkdir(parents=True, exist_ok=True)

        console.print(f"Creating worktree [cyan]{branch}[/cyan] for [cyan]{repo_name}[/cyan]...")

        # Create the worktree with new branch
        success, message = create_worktree(branch, worktree_path, create_branch=True)

        if not success:
            console.print(f"[red]Error:[/red] {message}")
            sys.exit(1)

        console.print(f"  [green]✓[/green] {message}")

        # Set up dependencies
        console.print("Setting up dependencies...")
        dep_success, dep_message = setup_dependencies(worktree_path)
        if dep_success:
            console.print(f"  [green]✓[/green] {dep_message}")
        else:
            console.print(f"  [yellow]Warning:[/yellow] {dep_message}")

        console.print(f"\n[green]Worktree ready![/green] Launching Claude Code...")
        console.print(f"  Path: [cyan]{worktree_path}[/cyan]")

        # Launch Claude Code
        claude_result = subprocess.run(["which", "claude"], capture_output=True)
        if claude_result.returncode == 0:
            os.chdir(worktree_path)
            os.execvp("claude", ["claude"])
        else:
            console.print("[yellow]Warning:[/yellow] Claude Code not found in PATH")
            console.print(f"  cd {worktree_path}")


@cli.command()
def init():
    """Initialize claude-worktrees in the current repository."""
    git_root = ensure_git_repo()
    repo_name = get_repo_name()

    console.print(f"Initializing claude-worktrees for [cyan]{repo_name}[/cyan]")

    # Create config file if it doesn't exist
    if not CONFIG_PATH.exists():
        create_default_config()
        console.print(f"  [green]✓[/green] Created config file: {CONFIG_PATH}")
    else:
        console.print(f"  [dim]○[/dim] Config file already exists: {CONFIG_PATH}")

    # Create worktree base directory
    worktree_base = get_worktree_base()
    worktree_base.mkdir(parents=True, exist_ok=True)
    console.print(f"  [green]✓[/green] Worktree directory: {worktree_base}")

    # Install git hooks
    results = install_all_hooks()
    for hook_name, success, message in results:
        if success:
            console.print(f"  [green]✓[/green] {message}")
        else:
            console.print(f"  [red]✗[/red] {message}")

    console.print("\n[green]Initialization complete![/green]")
    console.print("\nUsage:")
    console.print("  cw              Create a new worktree and launch Claude Code")
    console.print("  cw list         List active worktrees")
    console.print("  cw cleanup      Clean up merged worktrees")


@cli.command()
@click.argument("branch", required=False)
@click.option("--from", "from_branch", help="Use an existing branch instead of creating a new one")
@click.option("--no-deps", is_flag=True, help="Skip dependency setup")
@click.option("--no-claude", is_flag=True, help="Don't launch Claude Code after creation")
def new(branch: str | None, from_branch: str | None, no_deps: bool, no_claude: bool):
    """Create a new worktree for the given branch (or auto-generate name)."""
    git_root = ensure_git_repo()
    repo_name = get_repo_name()

    # Auto-generate branch name if not provided
    if not branch and not from_branch:
        timestamp = int(time.time())
        branch = f"claude-{timestamp}"

    # Determine the branch to use
    if from_branch:
        if not branch_exists(from_branch):
            if branch_exists(from_branch, remote=True):
                console.print(f"[yellow]Note:[/yellow] Branch '{from_branch}' exists remotely, will track it")
            else:
                console.print(f"[red]Error:[/red] Branch '{from_branch}' does not exist")
                sys.exit(1)
        target_branch = from_branch
        create_new_branch = False
    else:
        target_branch = branch
        if branch_exists(branch):
            console.print(f"[yellow]Note:[/yellow] Branch '{branch}' already exists, using it")
            create_new_branch = False
        else:
            create_new_branch = True

    # Get worktree path
    worktree_path = get_worktree_path(target_branch)

    if worktree_path.exists():
        console.print(f"[red]Error:[/red] Worktree path already exists: {worktree_path}")
        sys.exit(1)

    worktree_path.parent.mkdir(parents=True, exist_ok=True)

    console.print(f"Creating worktree [cyan]{target_branch}[/cyan] for [cyan]{repo_name}[/cyan]...")

    if create_new_branch:
        success, message = create_worktree(target_branch, worktree_path, create_branch=True)
    else:
        success, message = create_worktree(target_branch, worktree_path, create_branch=False)

    if not success:
        console.print(f"[red]Error:[/red] {message}")
        sys.exit(1)

    console.print(f"  [green]✓[/green] {message}")

    if not no_deps:
        console.print("Setting up dependencies...")
        success, message = setup_dependencies(worktree_path)
        if success:
            console.print(f"  [green]✓[/green] {message}")
        else:
            console.print(f"  [yellow]Warning:[/yellow] {message}")

    console.print(f"\n[green]Worktree ready![/green]")
    console.print(f"  Path: [cyan]{worktree_path}[/cyan]")

    if not no_claude:
        console.print("Launching Claude Code...")
        claude_result = subprocess.run(["which", "claude"], capture_output=True)
        if claude_result.returncode == 0:
            os.chdir(worktree_path)
            os.execvp("claude", ["claude"])
        else:
            console.print("[yellow]Warning:[/yellow] Claude Code not found in PATH")
            console.print(f"  cd {worktree_path}")


@cli.command("list")
def list_cmd():
    """List all managed worktrees with status."""
    git_root = ensure_git_repo()

    worktrees = list_managed_worktrees()

    if not worktrees:
        console.print("[dim]No managed worktrees found.[/dim]")
        console.print("\nRun [cyan]cw[/cyan] to create one.")
        return

    table = Table(title="Managed Worktrees")
    table.add_column("Branch", style="cyan")
    table.add_column("Path", style="dim")
    table.add_column("Status")
    table.add_column("PR")
    table.add_column("Size", justify="right")

    main_branch = get_main_branch()
    check_pr = should_check_pr_status()

    for wt in worktrees:
        if has_uncommitted_changes(wt.path):
            status = "[yellow]modified[/yellow]"
        elif is_branch_merged(wt.branch, main_branch):
            status = "[green]merged[/green]"
        else:
            status = "[dim]active[/dim]"

        if check_pr:
            pr_info = get_pr_for_branch(wt.branch)
            pr_badge = get_pr_status_badge(pr_info)
        else:
            pr_badge = "[dim]—[/dim]"

        size = get_worktree_disk_usage(wt.path)
        size_str = format_size(size)

        table.add_row(wt.branch, str(wt.path), status, pr_badge, size_str)

    console.print(table)


@cli.command()
@click.option("--dry-run", is_flag=True, help="Show what would be removed without removing")
@click.option("--force", is_flag=True, help="Remove without prompting")
@click.option("--auto", is_flag=True, hidden=True, help="Run in auto mode for hooks")
def cleanup(dry_run: bool, force: bool, auto: bool):
    """Clean up worktrees for merged branches."""
    git_root = get_git_root()
    if not git_root:
        if not auto:
            console.print("[red]Error:[/red] Not in a git repository")
        sys.exit(1)

    if auto and not should_auto_cleanup():
        sys.exit(0)

    worktrees = list_managed_worktrees()

    if not worktrees:
        if not auto:
            console.print("[dim]No managed worktrees found.[/dim]")
        return

    main_branch = get_main_branch()
    check_pr = should_check_pr_status()
    max_age_days = 7  # Clean up worktrees older than 7 days with no active PR

    to_remove = []

    for wt in worktrees:
        merged_git = is_branch_merged(wt.branch, main_branch)
        closed_pr = is_pr_closed(wt.branch) if check_pr else False
        age_days = get_worktree_age_days(wt.path)

        # Check if worktree is stale (old with no active PR)
        stale = False
        if age_days >= max_age_days:
            if check_pr:
                pr_info = get_pr_for_branch(wt.branch)
                # Stale if no PR or PR is not open
                stale = pr_info is None or pr_info.is_closed
            else:
                # No GitHub - use age-based cleanup
                stale = True

        if merged_git or closed_pr or stale:
            to_remove.append(wt)

    if not to_remove:
        if not auto:
            console.print("[dim]No worktrees to clean up.[/dim]")
        return

    if dry_run:
        console.print("[cyan]Would remove the following worktrees:[/cyan]")
        for wt in to_remove:
            console.print(f"  • {wt.branch} ({wt.path})")
        return

    for wt in to_remove:
        if has_uncommitted_changes(wt.path):
            if force or auto:
                console.print(f"[yellow]Skipping[/yellow] {wt.branch} (has uncommitted changes)")
                continue
            else:
                if not click.confirm(f"Worktree {wt.branch} has uncommitted changes. Remove anyway?"):
                    continue

        if not force and not auto:
            if not click.confirm(f"Remove worktree for '{wt.branch}'?"):
                continue

        cleanup_symlinks(wt.path)
        success, message = remove_worktree(wt.path, force=True)
        if success:
            console.print(f"[green]✓[/green] Removed {wt.branch}")
        else:
            console.print(f"[red]✗[/red] Failed to remove {wt.branch}: {message}")


@cli.command()
@click.argument("branch")
@click.option("--force", is_flag=True, help="Force removal even with uncommitted changes")
def remove(branch: str, force: bool):
    """Remove a specific worktree."""
    git_root = ensure_git_repo()

    worktrees = list_managed_worktrees()

    target = None
    for wt in worktrees:
        if wt.branch == branch:
            target = wt
            break

    if not target:
        console.print(f"[red]Error:[/red] No worktree found for branch '{branch}'")
        sys.exit(1)

    if has_uncommitted_changes(target.path):
        if not force:
            console.print(f"[yellow]Warning:[/yellow] Worktree has uncommitted changes")
            if not click.confirm("Remove anyway?"):
                return

    cleanup_symlinks(target.path)
    success, message = remove_worktree(target.path, force=force)
    if success:
        console.print(f"[green]✓[/green] Removed worktree for '{branch}'")
    else:
        console.print(f"[red]Error:[/red] {message}")
        sys.exit(1)


@cli.command("open")
@click.argument("branch")
def open_cmd(branch: str):
    """Open Claude Code in a worktree."""
    git_root = ensure_git_repo()

    worktrees = list_managed_worktrees()

    target = None
    for wt in worktrees:
        if wt.branch == branch:
            target = wt
            break

    if not target:
        console.print(f"[red]Error:[/red] No worktree found for branch '{branch}'")
        sys.exit(1)

    claude_result = subprocess.run(["which", "claude"], capture_output=True)
    if claude_result.returncode == 0:
        console.print(f"Launching Claude Code in {target.path}...")
        os.chdir(target.path)
        os.execvp("claude", ["claude"])
    else:
        console.print("[yellow]Warning:[/yellow] Claude Code not found in PATH")
        console.print(f"  cd {target.path}")


if __name__ == "__main__":
    cli()
