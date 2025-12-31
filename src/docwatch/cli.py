"""
Command-line interface for docwatch
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.markup import escape as rich_escape
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from docwatch.constants import (
    COVERAGE_HEALTHY_THRESHOLD,
    COVERAGE_WARNING_THRESHOLD,
    PRIORITY_HIGH_THRESHOLD,
    PRIORITY_MEDIUM_THRESHOLD,
)
from docwatch.scanner import categorize_files, get_directory_stats
from docwatch.extractor import process_directory
from docwatch.models import CodeFile, DocFile
from docwatch.analyzer import DocumentationAnalyzer
from docwatch.git import (
    ChangeTracker,
    ImpactAnalyzer,
    ImpactType,
    ChangeType,
    GitCommandError,
)

# Create a console instance for all output
console = Console()


def format_size(size_bytes: int | float) -> str:
    """Convert bytes to human-readable format."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def print_basic_results(results: dict[str, list[Path]]) -> None:
    """Print basic categorization results with Rich styling."""
    code_files = results['code']
    doc_files = results['docs']

    # Build summary text
    summary = Text()
    summary.append("Code files: ", style="bold")
    summary.append(f"{len(code_files)}\n", style="cyan bold")
    summary.append("Doc files:  ", style="bold")
    summary.append(f"{len(doc_files)}", style="green bold")

    console.print(Panel(summary, title="[bold blue]Scan Results[/]", border_style="blue"))

    if doc_files:
        console.print("\n[bold green]Documentation files:[/]")
        for f in sorted(doc_files):
            console.print(f"  [dim]•[/] [green]{rich_escape(str(f))}[/]")

    if code_files:
        console.print("\n[bold cyan]Code files:[/]")
        for f in sorted(code_files)[:20]:
            console.print(f"  [dim]•[/] [cyan]{rich_escape(str(f))}[/]")
        if len(code_files) > 20:
            console.print(f"  [dim]... and {len(code_files) - 20} more[/]")


def print_stats(stats: dict) -> None:
    """Print detailed statistics using Rich tables."""
    console.print()

    # Extension breakdown
    ext_table = Table(title="File Extensions", show_header=True, header_style="bold magenta")
    ext_table.add_column("Extension", style="cyan")
    ext_table.add_column("Count", justify="right", style="bold")

    extensions = list(stats['by_extension'].items())[:10]

    for extension, count in extensions:
        ext_table.add_row(extension, str(count))

    console.print(ext_table)

    # Category breakdown
    cat_table = Table(title="Categories", show_header=True, header_style="bold magenta")
    cat_table.add_column("Category", style="dim")
    cat_table.add_column("Count", justify="right", style="bold")

    for category, count in stats['by_category'].items():
        cat_table.add_row(category.capitalize(), str(count))

    console.print(cat_table)

    # Largest files
    console.print("\n[bold yellow]Largest files:[/]")
    for file_info in stats['largest_files'][:5]:
        size = format_size(file_info['size'])
        console.print(f"  [yellow]{size:>10}[/]  [dim]{rich_escape(str(file_info['path']))}[/]")


def print_extraction_results(
    code_files: list[CodeFile],
    doc_files: list[DocFile],
    base_dir: Path,
) -> None:
    """Print detailed extraction analysis."""
    from docwatch.models import EntityType

    # Code Analysis
    console.print("\n[bold cyan]Code Analysis:[/]")
    for cf in sorted(code_files, key=lambda x: x.path):
        rel_path = cf.path.relative_to(base_dir) if cf.path.is_relative_to(base_dir) else cf.path
        console.print(f"  [cyan]{rich_escape(str(rel_path))}[/]")

        # Get function names from entities
        func_names = [e.name for e in cf.entities if e.entity_type == EntityType.FUNCTION][:10]
        func_str = rich_escape(", ".join(func_names)) if func_names else "none"
        total_funcs = len([e for e in cf.entities if e.entity_type == EntityType.FUNCTION])
        if total_funcs > 10:
            func_str += f" [dim](+{total_funcs - 10} more)[/]"
        console.print(f"    Functions: [white]{func_str}[/]")

        # Get class names from entities
        class_names = [e.name for e in cf.entities if e.entity_type == EntityType.CLASS]
        class_str = rich_escape(", ".join(class_names)) if class_names else "none"
        console.print(f"    Classes: [white]{class_str}[/]")

    # Documentation Analysis
    console.print("\n[bold green]Documentation Analysis:[/]")
    for df in sorted(doc_files, key=lambda x: x.path):
        rel_path = df.path.relative_to(base_dir) if df.path.is_relative_to(base_dir) else df.path
        console.print(f"  [green]{rich_escape(str(rel_path))}[/]")

        headers = [h['text'] for h in df.headers[:5]]
        header_str = rich_escape(", ".join(headers)) if headers else "none"
        if len(df.headers) > 5:
            header_str += f" [dim](+{len(df.headers) - 5} more)[/]"
        console.print(f"    Headers: [white]{header_str}[/]")

        # Get code references from references list
        code_refs = [r.clean_text for r in df.references]
        # Filter to likely identifiers (no special chars, reasonable length)
        filtered_refs = [r for r in code_refs
                        if r.replace('_', '').isalnum() and 2 < len(r) < 50][:10]
        ref_str = rich_escape(", ".join(filtered_refs)) if filtered_refs else "none"
        total_valid = len([r for r in code_refs
                         if r.replace('_', '').isalnum() and 2 < len(r) < 50])
        if total_valid > 10:
            ref_str += f" [dim](+{total_valid - 10} more)[/]"
        console.print(f"    Code references: [white]{ref_str}[/]")

    # Potential links summary
    console.print("\n[bold yellow]Potential Links Found:[/]")

    # Collect all code symbols
    all_symbols = set()
    for cf in code_files:
        all_symbols.update(e.name for e in cf.entities)

    # Find which docs reference which symbols
    for df in sorted(doc_files, key=lambda x: x.path):
        rel_path = df.path.relative_to(base_dir) if df.path.is_relative_to(base_dir) else df.path

        # Find matching references
        matches = [r.clean_text for r in df.references if r.clean_text in all_symbols]

        if matches:
            console.print(f"  [green]{rich_escape(str(rel_path))}[/] references: [white]{rich_escape(', '.join(matches[:10]))}[/]")
            if len(matches) > 10:
                console.print(f"    [dim](+{len(matches) - 10} more)[/]")


def make_progress_bar(percentage: float, width: int = 10) -> str:
    """Create a text-based progress bar."""
    filled = int(percentage / 100 * width)
    empty = width - filled
    return "█" * filled + "░" * empty


def _relative_path(filepath: str | Path, base_dir: Path) -> Path:
    """Get path relative to base_dir, or absolute if not under base_dir."""
    path = Path(filepath)
    try:
        return path.relative_to(base_dir)
    except ValueError:
        return path


def _coverage_style(pct: float) -> str:
    """Get Rich style name based on coverage percentage."""
    if pct >= COVERAGE_HEALTHY_THRESHOLD:
        return "green"
    if pct >= COVERAGE_WARNING_THRESHOLD:
        return "yellow"
    return "red"


def _print_priority_issue(index: int, issue: dict, base_dir: Path) -> None:
    """Print a single priority issue."""
    if issue["type"] == "undocumented":
        entity = issue["entity"]
        rel_path = _relative_path(entity["location"]["file"], base_dir)
        console.print(
            f"  {index}. Document: [cyan]{rich_escape(str(rel_path))}[/]"
            f"::[white]{rich_escape(entity['name'])}[/]"
        )
    else:
        ref = issue["reference"]
        rel_path = _relative_path(ref["location"]["file"], base_dir)
        console.print(
            f"  {index}. Fix broken reference in [green]{rich_escape(str(rel_path))}[/] "
            f"line {ref['location']['line_start']}: [yellow]`{rich_escape(ref['clean_text'])}`[/]"
        )


def print_analysis_report(analyzer: DocumentationAnalyzer, base_dir: Path) -> None:
    """Print a comprehensive documentation health report."""
    stats = analyzer.get_coverage_stats()
    coverage_by_file = analyzer.get_coverage_by_file()
    priority_issues = analyzer.get_priority_issues()

    # Header
    console.print()
    console.print(Panel(
        "[bold]Documentation Health Report[/]",
        style="blue",
        expand=False
    ))

    # Overall coverage
    coverage_pct = stats.coverage_percent
    style = _coverage_style(coverage_pct)
    console.print()
    console.print(
        f"[bold]Coverage:[/] [{style}]{coverage_pct:.0f}%[/] "
        f"({stats.documented_entities} of {stats.total_entities} code entities documented)"
    )

    # By file table
    if coverage_by_file:
        console.print("\n[bold]By File:[/]")
        sorted_files = sorted(coverage_by_file.items(), key=lambda x: x[1])[:10]

        for filepath, pct in sorted_files:
            rel_path = _relative_path(filepath, base_dir)
            bar = make_progress_bar(pct)
            style = _coverage_style(pct)
            console.print(f"  {rich_escape(str(rel_path)):<30} [{style}]{pct:>3.0f}%[/] {bar}")

        if len(coverage_by_file) > 10:
            console.print(f"  [dim]... and {len(coverage_by_file) - 10} more files[/]")

    # Issues summary
    high_issues = [i for i in priority_issues if i["priority"] >= PRIORITY_HIGH_THRESHOLD]
    low_issues = [i for i in priority_issues if i["priority"] < PRIORITY_MEDIUM_THRESHOLD]

    undocumented_high = sum(1 for i in high_issues if i["type"] == "undocumented")
    broken_refs = sum(1 for i in priority_issues if i["type"] == "broken_reference")
    undocumented_low = sum(1 for i in low_issues if i["type"] == "undocumented")

    console.print("\n[bold]Issues Found:[/]")
    if undocumented_high > 0:
        console.print(f"  [red]HIGH:[/] {undocumented_high} public entities have no documentation")
    if broken_refs > 0:
        console.print(f"  [yellow]MEDIUM:[/] {broken_refs} documentation references point to non-existent code")
    if undocumented_low > 0:
        console.print(f"  [dim]LOW:[/] {undocumented_low} internal/private entities are undocumented")
    if not priority_issues:
        console.print("  [green]✓ No issues found![/]")

    # Top priority items
    if priority_issues:
        console.print("\n[bold]Top Priority:[/]")
        for i, issue in enumerate(priority_issues[:5], 1):
            _print_priority_issue(i, issue, base_dir)


def save_results(
    results: dict[str, list[Path]],
    stats: Optional[dict],
    output_path: Path,
) -> None:
    """Save results to JSON file."""
    output = {
        'categorized_files': {
            'code': [str(f) for f in results['code']],
            'docs': [str(f) for f in results['docs']]
        }
    }

    if stats:
        output['statistics'] = {
            'total_files': stats['total_files'],
            'by_category': stats['by_category'],
            'by_extension': stats['by_extension'],
            'largest_files': [
                {'path': str(f['path']), 'size': f['size']}
                for f in stats['largest_files']
            ]
        }

    with open(output_path, 'w') as f:
        json.dump(output, f, indent=2)

    console.print(f"\n[bold green]✓[/] Results saved to [underline]{rich_escape(str(output_path))}[/]")


def analyze_changes(repo_path: Path, since: str) -> int:
    """
    Analyze recent code changes and their documentation impact.

    Returns exit code (0 for success, 1 for error).
    """
    from datetime import datetime

    console.print(Panel(
        f"[bold]Analyzing changes since {since}[/]",
        style="blue",
        expand=False
    ))
    console.print()

    # Initialize change tracker
    try:
        tracker = ChangeTracker(repo_path)
    except (ValueError, GitCommandError) as e:
        console.print(f"[bold red]Error:[/] {e}")
        return 1

    # Get commits since the specified date
    try:
        commits = tracker.get_changes_since(since, include_diffs=True)
    except GitCommandError as e:
        console.print(f"[bold red]Error getting commits:[/] {e}")
        return 1

    if not commits:
        console.print("[yellow]No commits found in the specified time range.[/]")
        return 0

    console.print(f"[bold]Commits analyzed:[/] {len(commits)}")
    console.print()

    # Build documentation graph for the current state
    console.print("[dim]Building documentation graph...[/]")
    analyzer = DocumentationAnalyzer()
    try:
        analyzer.analyze_directory(repo_path)
    except Exception as e:
        console.print(f"[yellow]Warning: Could not analyze documentation: {e}[/]")

    # Create impact analyzer
    impact_analyzer = ImpactAnalyzer(analyzer.graph)

    # Collect all changes across commits
    all_entity_changes = []
    commits_with_changes = []

    for commit in commits:
        entity_changes = tracker.detect_entity_changes(commit)
        if entity_changes:
            commits_with_changes.append((commit, entity_changes))
            all_entity_changes.extend(entity_changes)

    # Print code changes
    if commits_with_changes:
        console.print("[bold cyan]Code Changes Detected:[/]")
        for commit, changes in commits_with_changes:
            short_hash = commit.hash[:7]
            # Truncate message to first line
            msg = commit.message.split('\n')[0][:60]
            console.print(f"  [cyan]{short_hash}[/] - \"{msg}\"")

            for change in changes:
                change_type = change.change_type.value.upper()
                entity_name = change.entity_name

                # Color based on change type
                if change.change_type == ChangeType.DELETED:
                    style = "red"
                elif change.change_type == ChangeType.ADDED:
                    style = "green"
                elif change.change_type == ChangeType.SIGNATURE_CHANGED:
                    style = "yellow"
                else:
                    style = "dim"

                rel_path = Path(change.file_path)
                try:
                    rel_path = rel_path.relative_to(repo_path)
                except ValueError:
                    pass

                console.print(f"    [{style}]{change_type}:[/] {rich_escape(str(rel_path))}::[white]{rich_escape(entity_name)}[/]")

                # Show signature changes
                if change.change_type == ChangeType.SIGNATURE_CHANGED:
                    if change.old_signature:
                        console.print(f"      [dim]Old:[/] [red]{rich_escape(change.old_signature)}[/]")
                    if change.new_signature:
                        console.print(f"      [dim]New:[/] [green]{rich_escape(change.new_signature)}[/]")
        console.print()
    else:
        console.print("[dim]No code entity changes detected in commits.[/]")
        console.print()

    # Analyze documentation impact
    impacts = impact_analyzer.analyze_changes(all_entity_changes)

    if impacts:
        # Group by severity
        high_impacts = [i for i in impacts if i.severity == "high"]
        medium_impacts = [i for i in impacts if i.severity == "medium"]
        low_impacts = [i for i in impacts if i.severity == "low"]

        console.print("[bold]Documentation Impact:[/]")

        if high_impacts:
            console.print("  [bold red]HIGH IMPACT:[/]")
            for impact in high_impacts:
                if impact.impact_type == ImpactType.BROKEN_REFERENCE:
                    console.print(
                        f"    [red]{rich_escape(str(impact.doc_path))}:{impact.doc_line}[/] - "
                        f"References deleted function [white]`{rich_escape(impact.referenced_entity)}`[/]"
                    )
                elif impact.impact_type == ImpactType.ADDED_UNDOCUMENTED:
                    console.print(
                        f"    [red]{rich_escape(str(impact.change.file_path))}[/] - "
                        f"New [white]`{rich_escape(impact.referenced_entity)}`[/] has no documentation"
                    )

        if medium_impacts:
            console.print("  [bold yellow]NEEDS REVIEW:[/]")
            for impact in medium_impacts:
                console.print(
                    f"    [yellow]{rich_escape(str(impact.doc_path))}:{impact.doc_line}[/] - "
                    f"References [white]`{rich_escape(impact.referenced_entity)}`[/], signature changed"
                )

        if low_impacts:
            console.print("  [dim]LOW PRIORITY:[/]")
            for impact in low_impacts[:5]:  # Limit to 5
                if impact.impact_type == ImpactType.NEEDS_UPDATE:
                    console.print(
                        f"    [dim]{rich_escape(str(impact.doc_path))}:{impact.doc_line}[/] - "
                        f"Docstring changed for [white]`{rich_escape(impact.referenced_entity)}`[/]"
                    )
                elif impact.impact_type == ImpactType.ADDED_UNDOCUMENTED:
                    console.print(
                        f"    [dim]{rich_escape(str(impact.change.file_path))}[/] - "
                        f"New [white]`{rich_escape(impact.referenced_entity)}`[/] is undocumented"
                    )
            if len(low_impacts) > 5:
                console.print(f"    [dim]... and {len(low_impacts) - 5} more[/]")

        console.print()

        # Generate recommendations
        recommendations = []

        for impact in high_impacts:
            if impact.impact_type == ImpactType.BROKEN_REFERENCE:
                recommendations.append(
                    f"Remove or update reference to `{rich_escape(impact.referenced_entity)}` "
                    f"in {rich_escape(str(impact.doc_path))}"
                )

        for impact in medium_impacts:
            recommendations.append(
                f"Update {rich_escape(str(impact.doc_path))} with new `{rich_escape(impact.referenced_entity)}` signature"
            )

        # Add recommendations for undocumented entities
        undocumented = [i for i in impacts if i.impact_type == ImpactType.ADDED_UNDOCUMENTED]
        if undocumented:
            entity_names = list(set(i.referenced_entity for i in undocumented))[:3]
            escaped_names = [rich_escape(name) for name in entity_names]
            if len(undocumented) > 3:
                recommendations.append(
                    f"Document new functions: {', '.join(escaped_names)}, "
                    f"and {len(undocumented) - 3} more"
                )
            else:
                recommendations.append(
                    f"Document new functions: {', '.join(escaped_names)}"
                )

        if recommendations:
            console.print("[bold]Recommended actions:[/]")
            for i, rec in enumerate(recommendations[:5], 1):
                console.print(f"  {i}. {rec}")
    else:
        console.print("[green]✓ No documentation impact detected.[/]")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Documentation decay detection system"
    )
    parser.add_argument(
        "directory",
        type=Path,
        help="Directory to scan"
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Show detailed statistics"
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Save results to JSON file"
    )
    parser.add_argument(
        "--no-ignore",
        action="store_true",
        help="Don't ignore common directories (.git, node_modules, etc.)"
    )
    parser.add_argument(
        "--extract",
        action="store_true",
        help="Extract and display code/documentation analysis"
    )
    parser.add_argument(
        "--analyze",
        action="store_true",
        help="Run full documentation analysis and show health report"
    )
    parser.add_argument(
        "--changes",
        action="store_true",
        help="Analyze recent code changes and their documentation impact"
    )
    parser.add_argument(
        "--since",
        type=str,
        default="7 days ago",
        help="Time range for --changes (default: '7 days ago')"
    )

    args = parser.parse_args()

    # Validate directory
    if not args.directory.exists():
        console.print(f"[bold red]Error:[/] Directory does not exist: {rich_escape(str(args.directory))}")
        return 1

    if not args.directory.is_dir():
        console.print(f"[bold red]Error:[/] Not a directory: {rich_escape(str(args.directory))}")
        return 1

    # Handle --changes separately (git-specific analysis)
    if args.changes:
        return analyze_changes(args.directory.resolve(), args.since)

    console.print(f"[bold]Scanning:[/] [blue]{rich_escape(str(args.directory.resolve()))}[/]")

    # Determine ignore settings
    ignore_dirs = set() if args.no_ignore else None

    # Get results
    results = categorize_files(args.directory, ignore_dirs=ignore_dirs)
    stats = get_directory_stats(args.directory, ignore_dirs=ignore_dirs) if args.stats else None

    # Display output
    print_basic_results(results)

    if args.stats:
        print_stats(stats)

    if args.extract:
        code_files, doc_files = process_directory(args.directory, ignore_dirs=ignore_dirs)
        print_extraction_results(code_files, doc_files, args.directory)

    # Run full analysis
    analyzer = None
    if args.analyze:
        analyzer = DocumentationAnalyzer()
        analyzer.analyze_directory(args.directory, ignore_dirs=ignore_dirs)
        print_analysis_report(analyzer, args.directory)

    # Save output
    if args.output:
        if analyzer:
            # Save full analysis
            analyzer.save(args.output)
            console.print(f"\n[bold green]✓[/] Graph saved to: [underline]{rich_escape(str(args.output))}[/]")
        else:
            save_results(results, stats, args.output)

    return 0


if __name__ == "__main__":
    exit(main())
