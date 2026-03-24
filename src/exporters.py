"""
Exporters — Meeting Agent Pipeline
Convert pipeline output to multiple formats for downstream use.

Supported formats:
  - JSON      (default — full structured output)
  - Markdown  (human-readable report)
  - CSV       (tasks only — for import into Jira, Asana, Notion, etc.)

Usage:
    from src.exporters import export

    export(result, fmt="markdown", path="outputs/report.md")
    export(result, fmt="csv",      path="outputs/tasks.csv")
    export(result, fmt="json",     path="outputs/output.json")
"""

import csv
import json
import os
from datetime import datetime
from pathlib import Path


# ── Internal helpers ──────────────────────────────────────────────────────────

def _ensure_dir(path: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)


def _sensitivity_emoji(s: str) -> str:
    return {"PUBLIC": "🟢", "INTERNAL": "🔵", "CONFIDENTIAL": "🟡", "RESTRICTED": "🔴"}.get(s, "⚪")

def _priority_emoji(p: str) -> str:
    return {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}.get(p, "⚪")

def _severity_emoji(s: str) -> str:
    return {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}.get(s, "⚪")

def _action_emoji(a: str) -> str:
    return {"ESCALATION": "🚨", "REMINDER": "⏰", "REASSIGN": "🔄"}.get(a, "•")


# ── JSON ──────────────────────────────────────────────────────────────────────

def to_json(result: dict, indent: int = 2) -> str:
    return json.dumps(result, indent=indent, ensure_ascii=False)


def export_json(result: dict, path: str) -> str:
    _ensure_dir(path)
    content = to_json(result)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path


# ── Markdown ──────────────────────────────────────────────────────────────────

def to_markdown(result: dict) -> str:
    lines = []
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")

    lines.append(f"# Meeting pipeline report")
    lines.append(f"_Generated: {ts}_\n")

    # Summary
    lines.append("## Summary\n")
    lines.append(f"{result['meeting_summary']}\n")

    # Stats
    tasks = result["tasks"]
    high = sum(1 for t in tasks if t["priority"] == "HIGH")
    restricted = sum(1 for t in tasks if t["sensitivity"] == "RESTRICTED")
    lines.append("## At a glance\n")
    lines.append(f"| Metric | Value |")
    lines.append(f"|--------|-------|")
    lines.append(f"| Total tasks | {len(tasks)} |")
    lines.append(f"| High priority | {high} |")
    lines.append(f"| Restricted items | {restricted} |")
    lines.append(f"| Unassigned gaps | {len(result['unassigned_tasks'])} |")
    lines.append(f"| Risks & blockers | {len(result['risks_or_blockers'])} |")
    lines.append("")

    # Decisions
    lines.append("## Decisions\n")
    for d in result["decisions"]:
        em = _sensitivity_emoji(d["sensitivity"])
        lines.append(f"- {em} **{d['decision']}**")
        lines.append(f"  - _Context:_ {d['context']}")
        lines.append(f"  - _Sensitivity:_ `{d['sensitivity']}`")
    lines.append("")

    # Tasks
    lines.append("## Tasks\n")
    lines.append("| ID | Title | Owner | Deadline | Priority | Sensitivity |")
    lines.append("|----|-------|-------|----------|----------|-------------|")
    for t in tasks:
        pe = _priority_emoji(t["priority"])
        se = _sensitivity_emoji(t["sensitivity"])
        lines.append(
            f"| {t['task_id']} | {t['task_title']} | {t['owner']} "
            f"| {t['deadline']} | {pe} {t['priority']} | {se} {t['sensitivity']} |"
        )
    lines.append("")

    # Task details
    lines.append("### Task details\n")
    for t in tasks:
        lines.append(f"#### {t['task_id']} — {t['task_title']}")
        lines.append(f"- **Owner:** {t['owner']}")
        lines.append(f"- **Deadline:** {t['deadline']}")
        lines.append(f"- **Priority:** {t['priority']}")
        lines.append(f"- **Sensitivity:** {t['sensitivity']}")
        lines.append(f"- **Allowed roles:** {', '.join(t['allowed_roles'])}")
        lines.append(f"- **Description:** {t['description']}")
        lines.append(f"- **Masked preview:** _{t['masked_preview']}_")
        if t["dependencies"]:
            lines.append(f"- **Dependencies:** {', '.join(t['dependencies'])}")
        if t["risk_flags"]:
            lines.append("- **Risk flags:**")
            for flag in t["risk_flags"]:
                lines.append(f"  - ⚠️ {flag}")
        lines.append("")

    # Unassigned
    if result["unassigned_tasks"]:
        lines.append("## Unassigned gaps\n")
        for u in result["unassigned_tasks"]:
            lines.append(f"- ⚠️ **{u['task_title']}** — {u['reason']}")
        lines.append("")

    # Risks
    lines.append("## Risks and blockers\n")
    for r in result["risks_or_blockers"]:
        em = _severity_emoji(r["severity"])
        lines.append(f"### {em} {r['issue']}")
        lines.append(f"- **Severity:** {r['severity']}")
        lines.append(f"- **Suggested solution:** {r['suggested_solution']}")
        lines.append("")

    # Monitoring
    lines.append("## Monitoring insights\n")
    insights = result["monitoring_insights"]
    if insights["overdue_risk_tasks"]:
        lines.append(f"**Overdue-risk tasks:** {', '.join(insights['overdue_risk_tasks'])}\n")
    if insights["potential_delays"]:
        lines.append("**Potential delays:**\n")
        for d in insights["potential_delays"]:
            lines.append(f"- {d}")
        lines.append("")
    lines.append("**Recommended actions:**\n")
    lines.append("| Task | Action | Reason |")
    lines.append("|------|--------|--------|")
    for a in insights["recommended_actions"]:
        em = _action_emoji(a["action"])
        lines.append(f"| {a['task_id']} | {em} {a['action']} | {a['reason']} |")

    return "\n".join(lines)


def export_markdown(result: dict, path: str) -> str:
    _ensure_dir(path)
    content = to_markdown(result)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path


# ── CSV ───────────────────────────────────────────────────────────────────────

CSV_FIELDS = [
    "task_id", "task_title", "description", "owner", "deadline",
    "priority", "status", "dependencies", "sensitivity",
    "allowed_roles", "risk_flags", "masked_preview",
]


def to_csv(result: dict) -> str:
    import io
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=CSV_FIELDS, extrasaction="ignore")
    writer.writeheader()
    for t in result["tasks"]:
        row = dict(t)
        row["dependencies"] = "; ".join(t.get("dependencies", []))
        row["allowed_roles"] = "; ".join(t.get("allowed_roles", []))
        row["risk_flags"] = "; ".join(t.get("risk_flags", []))
        writer.writerow(row)
    return buf.getvalue()


def export_csv(result: dict, path: str) -> str:
    _ensure_dir(path)
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(to_csv(result))
    return path


# ── Unified export ────────────────────────────────────────────────────────────

FORMATS = {
    "json":     export_json,
    "markdown": export_markdown,
    "md":       export_markdown,
    "csv":      export_csv,
}


def export(result: dict, fmt: str, path: str) -> str:
    """
    Export pipeline output to a file.

    Args:
        result: Pipeline output dict.
        fmt:    One of 'json', 'markdown' / 'md', 'csv'.
        path:   Output file path.

    Returns:
        The path the file was written to.
    """
    fmt = fmt.lower()
    if fmt not in FORMATS:
        raise ValueError(f"Unknown export format: '{fmt}'. Choose from: {list(FORMATS.keys())}")
    return FORMATS[fmt](result, path)


def export_all(result: dict, base_dir: str, stem: str = "pipeline_output") -> dict:
    """
    Export to all formats at once.

    Returns a dict of {format: path} for all written files.
    """
    paths = {}
    for fmt, fn in [("json", export_json), ("markdown", export_markdown), ("csv", export_csv)]:
        ext = "md" if fmt == "markdown" else fmt
        path = os.path.join(base_dir, f"{stem}.{ext}")
        paths[fmt] = fn(result, path)
    return paths
