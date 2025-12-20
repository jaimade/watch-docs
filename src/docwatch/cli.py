"""
Command-line interface for docwatch
"""
import argparse
import json
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from docwatch.scanner import categorize_files, get_directory_stats
from docwatch.extractor import process_directory
from docwatch.analyzer import DocumentationAnalyzer

# Create a console instance for all output
console = Console()


def format_size(size_bytes):
    """Convert bytes to human-readable format."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def print_basic_results(results):
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
            console.print(f"  [dim]•[/] [green]{f}[/]")

    if code_files:
        console.print("\n[bold cyan]Code files:[/]")
        for f in sorted(code_files)[:20]:
            console.print(f"  [dim]•[/] [cyan]{f}[/]")
        if len(code_files) > 20:
            console.print(f"  [dim]... and {len(code_files) - 20} more[/]")


def print_stats(stats):
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
        console.print(f"  [yellow]{size:>10}[/]  [dim]{file_info['path']}[/]")


def print_extraction_results(code_files, doc_files, base_dir):
    """Print detailed extraction analysis."""
    from docwatch.models import EntityType

    # Code Analysis
    console.print("\n[bold cyan]Code Analysis:[/]")
    for cf in sorted(code_files, key=lambda x: x.path):
        rel_path = cf.path.relative_to(base_dir) if cf.path.is_relative_to(base_dir) else cf.path
        console.print(f"  [cyan]{rel_path}[/]")

        # Get function names from entities
        func_names = [e.name for e in cf.entities if e.entity_type == EntityType.FUNCTION][:10]
        func_str = ", ".join(func_names) if func_names else "none"
        total_funcs = len([e for e in cf.entities if e.entity_type == EntityType.FUNCTION])
        if total_funcs > 10:
            func_str += f" [dim](+{total_funcs - 10} more)[/]"
        console.print(f"    Functions: [white]{func_str}[/]")

        # Get class names from entities
        class_names = [e.name for e in cf.entities if e.entity_type == EntityType.CLASS]
        class_str = ", ".join(class_names) if class_names else "none"
        console.print(f"    Classes: [white]{class_str}[/]")

    # Documentation Analysis
    console.print("\n[bold green]Documentation Analysis:[/]")
    for df in sorted(doc_files, key=lambda x: x.path):
        rel_path = df.path.relative_to(base_dir) if df.path.is_relative_to(base_dir) else df.path
        console.print(f"  [green]{rel_path}[/]")

        headers = [h['text'] for h in df.headers[:5]]
        header_str = ", ".join(headers) if headers else "none"
        if len(df.headers) > 5:
            header_str += f" [dim](+{len(df.headers) - 5} more)[/]"
        console.print(f"    Headers: [white]{header_str}[/]")

        # Get code references from references list
        code_refs = [r.clean_text for r in df.references]
        # Filter to likely identifiers (no special chars, reasonable length)
        filtered_refs = [r for r in code_refs
                        if r.replace('_', '').isalnum() and 2 < len(r) < 50][:10]
        ref_str = ", ".join(filtered_refs) if filtered_refs else "none"
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
            console.print(f"  [green]{rel_path}[/] references: [white]{', '.join(matches[:10])}[/]")
            if len(matches) > 10:
                console.print(f"    [dim](+{len(matches) - 10} more)[/]")


def make_progress_bar(percentage: float, width: int = 10) -> str:
    """Create a text-based progress bar."""
    filled = int(percentage / 100 * width)
    empty = width - filled
    return "█" * filled + "░" * empty


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
    if coverage_pct >= 80:
        coverage_style = "green"
    elif coverage_pct >= 50:
        coverage_style = "yellow"
    else:
        coverage_style = "red"

    console.print()
    console.print(
        f"[bold]Coverage:[/] [{coverage_style}]{coverage_pct:.0f}%[/] "
        f"({stats.documented_entities} of {stats.total_entities} code entities documented)"
    )

    # By file table
    if coverage_by_file:
        console.print("\n[bold]By File:[/]")

        # Sort by coverage (lowest first to highlight problem areas)
        sorted_files = sorted(coverage_by_file.items(), key=lambda x: x[1])

        for filepath, pct in sorted_files[:10]:
            # Make path relative if possible
            try:
                rel_path = Path(filepath).relative_to(base_dir)
            except ValueError:
                rel_path = Path(filepath)

            bar = make_progress_bar(pct)

            if pct >= 80:
                style = "green"
            elif pct >= 50:
                style = "yellow"
            else:
                style = "red"

            console.print(f"  {str(rel_path):<30} [{style}]{pct:>3.0f}%[/] {bar}")

        if len(coverage_by_file) > 10:
            console.print(f"  [dim]... and {len(coverage_by_file) - 10} more files[/]")

    # Issues summary
    high_issues = [i for i in priority_issues if i["priority"] >= 0.7]
    medium_issues = [i for i in priority_issues if 0.4 <= i["priority"] < 0.7]
    low_issues = [i for i in priority_issues if i["priority"] < 0.4]

    # Count by type
    undocumented_high = len([i for i in high_issues if i["type"] == "undocumented"])
    broken_refs = len([i for i in priority_issues if i["type"] == "broken_reference"])
    undocumented_low = len([i for i in low_issues if i["type"] == "undocumented"])

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
            if issue["type"] == "undocumented":
                entity = issue["entity"]
                location = entity["location"]
                try:
                    rel_path = Path(location["file"]).relative_to(base_dir)
                except ValueError:
                    rel_path = Path(location["file"])
                console.print(f"  {i}. Document: [cyan]{rel_path}[/]::[white]{entity['name']}[/]")
            else:
                ref = issue["reference"]
                location = ref["location"]
                try:
                    rel_path = Path(location["file"]).relative_to(base_dir)
                except ValueError:
                    rel_path = Path(location["file"])
                console.print(
                    f"  {i}. Fix broken reference in [green]{rel_path}[/] "
                    f"line {location['line_start']}: [yellow]`{ref['clean_text']}`[/]"
                )


def save_results(results, stats, output_path):
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

    console.print(f"\n[bold green]✓[/] Results saved to [underline]{output_path}[/]")


def main():
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

    args = parser.parse_args()

    # Validate directory
    if not args.directory.exists():
        console.print(f"[bold red]Error:[/] Directory does not exist: {args.directory}")
        return 1

    if not args.directory.is_dir():
        console.print(f"[bold red]Error:[/] Not a directory: {args.directory}")
        return 1

    console.print(f"[bold]Scanning:[/] [blue]{args.directory.resolve()}[/]")

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
            console.print(f"\n[bold green]✓[/] Graph saved to: [underline]{args.output}[/]")
        else:
            save_results(results, stats, args.output)

    return 0


if __name__ == "__main__":
    exit(main())
