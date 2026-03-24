"""
CLI — Meeting Agent Pipeline
Rich terminal interface with color-coded output and export options.

Usage:
    python -m cli.run <transcript_file> [options]

Options:
    --date YYYY-MM-DD   Meeting date for deadline normalization
    --output FILE       Save JSON output to file
    --format json|rich  Output format (default: rich)
    --quiet             Suppress progress messages, print JSON only
"""

import argparse
import json
import sys
import os
from datetime import datetime

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.text import Text
    from rich import box
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

from src.pipeline import run_pipeline_from_file, run_pipeline

console = Console() if RICH_AVAILABLE else None


SENSITIVITY_COLORS = {
    "PUBLIC":       "green",
    "INTERNAL":     "blue",
    "CONFIDENTIAL": "yellow",
    "RESTRICTED":   "red",
}

PRIORITY_COLORS = {
    "HIGH":   "red",
    "MEDIUM": "yellow",
    "LOW":    "green",
}

SEVERITY_COLORS = {
    "HIGH":   "red",
    "MEDIUM": "yellow",
    "LOW":    "green",
}

ACTION_COLORS = {
    "ESCALATION": "red",
    "REMINDER":   "yellow",
    "REASSIGN":   "blue",
}


def print_rich(result: dict) -> None:
    if not RICH_AVAILABLE:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return

    # ── Summary ──────────────────────────────────────────────────────────────
    console.print(Panel(
        result["meeting_summary"],
        title="[bold]Meeting summary[/bold]",
        border_style="bright_blue",
    ))

    # ── Stats ─────────────────────────────────────────────────────────────────
    tasks = result["tasks"]
    high = sum(1 for t in tasks if t["priority"] == "HIGH")
    restricted = sum(1 for t in tasks if t["sensitivity"] == "RESTRICTED")
    console.print(
        f"\n  [bold]Tasks:[/bold] {len(tasks)}   "
        f"[red]High priority:[/red] {high}   "
        f"[red]Restricted:[/red] {restricted}   "
        f"[yellow]Unassigned gaps:[/yellow] {len(result['unassigned_tasks'])}   "
        f"[red]Risks:[/red] {len(result['risks_or_blockers'])}\n"
    )

    # ── Decisions ─────────────────────────────────────────────────────────────
    dec_table = Table(box=box.SIMPLE_HEAD, show_header=True, header_style="bold")
    dec_table.add_column("Decision", style="white", ratio=4)
    dec_table.add_column("Sensitivity", ratio=1, justify="center")
    for d in result["decisions"]:
        color = SENSITIVITY_COLORS.get(d["sensitivity"], "white")
        dec_table.add_row(
            d["decision"],
            f"[{color}]{d['sensitivity']}[/{color}]",
        )
    console.print(Panel(dec_table, title="[bold]Decisions[/bold]", border_style="blue"))

    # ── Tasks ─────────────────────────────────────────────────────────────────
    task_table = Table(box=box.SIMPLE_HEAD, show_header=True, header_style="bold")
    task_table.add_column("ID", width=4)
    task_table.add_column("Title", ratio=3)
    task_table.add_column("Owner", ratio=1)
    task_table.add_column("Deadline", ratio=2)
    task_table.add_column("Priority", ratio=1, justify="center")
    task_table.add_column("Sensitivity", ratio=1, justify="center")
    for t in tasks:
        pc = PRIORITY_COLORS.get(t["priority"], "white")
        sc = SENSITIVITY_COLORS.get(t["sensitivity"], "white")
        task_table.add_row(
            t["task_id"],
            t["task_title"],
            t["owner"],
            t["deadline"],
            f"[{pc}]{t['priority']}[/{pc}]",
            f"[{sc}]{t['sensitivity']}[/{sc}]",
        )
    console.print(Panel(task_table, title="[bold]Tasks[/bold]", border_style="blue"))

    # ── Unassigned ────────────────────────────────────────────────────────────
    if result["unassigned_tasks"]:
        for u in result["unassigned_tasks"]:
            console.print(f"  [yellow]⚠ UNASSIGNED:[/yellow] {u['task_title']} — {u['reason']}")
        console.print()

    # ── Risks ─────────────────────────────────────────────────────────────────
    risk_table = Table(box=box.SIMPLE_HEAD, show_header=True, header_style="bold")
    risk_table.add_column("Issue", ratio=3)
    risk_table.add_column("Severity", ratio=1, justify="center")
    risk_table.add_column("Suggested solution", ratio=3)
    for r in result["risks_or_blockers"]:
        sc = SEVERITY_COLORS.get(r["severity"], "white")
        risk_table.add_row(
            r["issue"],
            f"[{sc}]{r['severity']}[/{sc}]",
            r["suggested_solution"],
        )
    console.print(Panel(risk_table, title="[bold]Risks and blockers[/bold]", border_style="red"))

    # ── Monitoring ────────────────────────────────────────────────────────────
    insights = result["monitoring_insights"]
    mon_table = Table(box=box.SIMPLE_HEAD, show_header=True, header_style="bold")
    mon_table.add_column("Task ID", width=7)
    mon_table.add_column("Action", width=12)
    mon_table.add_column("Reason", ratio=4)
    for a in insights["recommended_actions"]:
        ac = ACTION_COLORS.get(a["action"], "white")
        mon_table.add_row(
            a["task_id"],
            f"[{ac}]{a['action']}[/{ac}]",
            a["reason"],
        )
    console.print(Panel(mon_table, title="[bold]Monitoring — recommended actions[/bold]", border_style="yellow"))

    if insights["potential_delays"]:
        console.print("[bold yellow]Potential delays:[/bold yellow]")
        for d in insights["potential_delays"]:
            console.print(f"  • {d}")
        console.print()


def main():
    parser = argparse.ArgumentParser(
        description="Meeting Agent Pipeline — convert a transcript to structured JSON"
    )
    parser.add_argument("transcript", nargs="?", help="Path to transcript .txt file")
    parser.add_argument("--date", metavar="YYYY-MM-DD", help="Meeting date for deadline normalization")
    parser.add_argument("--output", metavar="FILE", help="Save JSON output to this file")
    parser.add_argument("--format", choices=["json", "rich"], default="rich", dest="fmt")
    parser.add_argument("--quiet", action="store_true", help="Print JSON only, no progress")
    parser.add_argument("--stdin", action="store_true", help="Read transcript from stdin")
    args = parser.parse_args()

    # Read transcript
    if args.stdin or not args.transcript:
        if not args.quiet:
            print("Reading transcript from stdin (Ctrl+D when done)...", file=sys.stderr)
        transcript = sys.stdin.read()
        result = run_pipeline(transcript, args.date)
    else:
        if not os.path.exists(args.transcript):
            print(f"Error: file not found: {args.transcript}", file=sys.stderr)
            sys.exit(1)
        result = run_pipeline_from_file(args.transcript, args.date)

    # Output
    if args.fmt == "json" or args.quiet or not RICH_AVAILABLE:
        output = json.dumps(result, indent=2, ensure_ascii=False)
        print(output)
    else:
        print_rich(result)

    # Save to file
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        if not args.quiet:
            print(f"\nOutput saved to: {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
