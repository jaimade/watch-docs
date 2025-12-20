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

    # Code Analysis
    console.print("\n[bold cyan]Code Analysis:[/]")
    for cf in sorted(code_files, key=lambda x: x.path):
        rel_path = cf.path.relative_to(base_dir) if cf.path.is_relative_to(base_dir) else cf.path
        console.print(f"  [cyan]{rel_path}[/]")

        funcs = cf.functions[:10]
        func_str = ", ".join(funcs) if funcs else "none"
        if len(cf.functions) > 10:
            func_str += f" [dim](+{len(cf.functions) - 10} more)[/]"
        console.print(f"    Functions: [white]{func_str}[/]")

        class_str = ", ".join(cf.classes) if cf.classes else "none"
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

        # Filter code references to likely identifiers (no special chars, reasonable length)
        refs = [r for r in df.code_references
                if r.replace('_', '').isalnum() and 2 < len(r) < 50][:10]
        ref_str = ", ".join(refs) if refs else "none"
        if len(refs) < len(df.code_references):
            remaining = len([r for r in df.code_references
                           if r.replace('_', '').isalnum() and 2 < len(r) < 50]) - 10
            if remaining > 0:
                ref_str += f" [dim](+{remaining} more)[/]"
        console.print(f"    Code references: [white]{ref_str}[/]")

    # Potential links summary
    console.print("\n[bold yellow]Potential Links Found:[/]")

    # Collect all code symbols
    all_functions = set()
    all_classes = set()
    for cf in code_files:
        all_functions.update(cf.functions)
        all_classes.update(cf.classes)
    all_symbols = all_functions | all_classes

    # Find which docs reference which symbols
    for df in sorted(doc_files, key=lambda x: x.path):
        rel_path = df.path.relative_to(base_dir) if df.path.is_relative_to(base_dir) else df.path

        # Find matching references
        matches = [r for r in df.code_references if r in all_symbols]

        if matches:
            console.print(f"  [green]{rel_path}[/] references: [white]{', '.join(matches[:10])}[/]")
            if len(matches) > 10:
                console.print(f"    [dim](+{len(matches) - 10} more)[/]")


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

    if args.output:
        save_results(results, stats, args.output)

    return 0


if __name__ == "__main__":
    exit(main())
