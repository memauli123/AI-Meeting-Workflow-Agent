"""
# NOTE: This async pipeline uses the Anthropic SDK.
# If using Gemini, use the standard pipeline.py instead.

Async Pipeline — Meeting Agent Pipeline
Async variant of the pipeline using asyncio + concurrent agent calls
where agents don't depend on each other's output.

Dependency graph:
  Transcript
      │
      ├─► [Agent 1] Comprehension    (independent)
      │
      └─► [Agent 2] Extraction       (independent)
              │
              ├─► [Agent 3] Classification  (needs extraction output)
              │
              └─► [Agent 4] Risk            (needs extraction output)
                      │
                      └─► [Agent 5] Monitoring (needs tasks + risks)

Agents 1 and 2 run concurrently.
Agents 3 and 4 run concurrently once Agent 2 completes.
Agent 5 runs after agents 3 and 4 complete.

This typically reduces wall-clock time by ~35-45% vs the sequential pipeline.
"""

import asyncio
import json
import re
from datetime import datetime
import anthropic

from src.utils.date_normalizer import normalize_dates
from src.utils.schema_validator import validate_output
from src.agents.classification_agent import RBAC_MAP


# ── Async Anthropic helper ────────────────────────────────────────────────────

async def _acall(client: anthropic.AsyncAnthropic, system: str, user: str, max_tokens: int = 2000) -> str:
    message = await client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return message.content[0].text.strip()


def _parse(raw: str) -> dict | list:
    clean = re.sub(r"```(?:json)?|```", "", raw).strip()
    return json.loads(clean)


# ── Agent coroutines ──────────────────────────────────────────────────────────

async def _agent_comprehension(client, transcript: str) -> str:
    system = """You are a meeting comprehension agent.
Produce a concise 3-4 line summary covering main topics, key decisions, blockers, and unresolved items.
Return ONLY the summary as plain text."""
    return await _acall(client, system, f"Transcript:\n\n{transcript}", max_tokens=300)


async def _agent_extraction(client, transcript: str) -> tuple[list, list, list]:
    decisions_system = """Extract every decision from this transcript.
Return STRICT JSON array: [{"decision":"...","context":"..."}]
No extra text. No markdown fences."""

    tasks_system = """Extract every actionable task from this transcript.
Return STRICT JSON: {"tasks":[...],"unassigned_tasks":[...]}
Each task: task_id(T1...), task_title, description, owner, deadline, priority(HIGH|MEDIUM|LOW), status(PENDING), dependencies([]).
No extra text. No markdown fences."""

    decisions_raw, tasks_raw = await asyncio.gather(
        _acall(client, decisions_system, f"Transcript:\n\n{transcript}"),
        _acall(client, tasks_system, f"Transcript:\n\n{transcript}", max_tokens=3000),
    )

    decisions = _parse(decisions_raw)
    tasks_data = _parse(tasks_raw)
    return decisions, tasks_data.get("tasks", []), tasks_data.get("unassigned_tasks", [])


async def _agent_classification(client, decisions: list, tasks: list) -> tuple[list, list]:
    classify_system = """Add "sensitivity": PUBLIC|INTERNAL|CONFIDENTIAL|RESTRICTED to each item.
Rules: salary/compensation/HR → RESTRICTED, client/budget/vendor → CONFIDENTIAL,
team plans/sprints → INTERNAL, safe for all → PUBLIC.
Return SAME JSON array with sensitivity added. No extra text. No markdown fences."""

    mask_system = """Add "masked_preview" to each task: a version of task_title with sensitive data replaced by [REDACTED].
Redact: salary figures, client names, vendor names, compensation, budget numbers, personal employee details.
Return SAME JSON array. No extra text. No markdown fences."""

    classified_decisions_raw, classified_tasks_raw = await asyncio.gather(
        _acall(client, classify_system, json.dumps(decisions, ensure_ascii=False)),
        _acall(client, classify_system, json.dumps(tasks, ensure_ascii=False), max_tokens=3000),
    )

    classified_decisions = _parse(classified_decisions_raw)
    classified_tasks = _parse(classified_tasks_raw)

    # Apply RBAC
    for item in classified_decisions + classified_tasks:
        item["allowed_roles"] = RBAC_MAP.get(item.get("sensitivity", "INTERNAL"), ["TEAM", "MANAGER"])

    # Mask tasks
    masked_raw = await _acall(client, mask_system, json.dumps(classified_tasks, ensure_ascii=False), max_tokens=3000)
    masked_tasks = _parse(masked_raw)

    for t in masked_tasks:
        t.setdefault("risk_flags", [])

    return classified_decisions, masked_tasks


async def _agent_risk(client, tasks: list, decisions: list) -> list:
    system = """Identify all risks and blockers across these tasks and decisions.
Return STRICT JSON array: [{"issue":"...","severity":"HIGH|MEDIUM|LOW","suggested_solution":"..."}]
No extra text. No markdown fences."""
    payload = json.dumps({"tasks": tasks, "decisions": decisions}, ensure_ascii=False)
    raw = await _acall(client, system, payload, max_tokens=2000)
    return _parse(raw)


async def _agent_monitoring(client, tasks: list, risks: list) -> dict:
    system = """Generate monitoring intelligence.
Return STRICT JSON: {
  "overdue_risk_tasks": ["T1"],
  "potential_delays": ["T1 — reason"],
  "recommended_actions": [{"task_id":"T1","action":"REMINDER|ESCALATION|REASSIGN","reason":"..."}]
}
No extra text. No markdown fences."""
    payload = json.dumps({"tasks": tasks, "risks": risks}, ensure_ascii=False)
    raw = await _acall(client, system, payload, max_tokens=1500)
    return _parse(raw)


# ── Main async pipeline ───────────────────────────────────────────────────────

async def run_pipeline_async(transcript: str, meeting_date: str = None) -> dict:
    """
    Run the full pipeline asynchronously with parallelised agent execution.

    Args:
        transcript:   Raw meeting transcript.
        meeting_date: ISO date (YYYY-MM-DD) for deadline normalization.

    Returns:
        Validated structured output dict.
    """
    client = anthropic.AsyncAnthropic()
    start = datetime.now()

    print("[Async Pipeline] Starting...")

    # Stage 1 — Comprehension + Extraction run concurrently
    print("[Stage 1] Comprehension + Extraction (concurrent)...")
    summary, (decisions, tasks, unassigned) = await asyncio.gather(
        _agent_comprehension(client, transcript),
        _agent_extraction(client, transcript),
    )

    # Stage 2 — Classification + Risk run concurrently (both need extraction output)
    print("[Stage 2] Classification + Risk detection (concurrent)...")
    (classified_decisions, classified_tasks), risks = await asyncio.gather(
        _agent_classification(client, decisions, tasks),
        _agent_risk(client, tasks, decisions),
    )

    # Stage 3 — Monitoring (needs classified tasks + risks)
    print("[Stage 3] Monitoring intelligence...")
    insights = await _agent_monitoring(client, classified_tasks, risks)

    # Date normalization
    if meeting_date:
        classified_tasks = normalize_dates(classified_tasks, meeting_date)

    output = {
        "meeting_summary": summary,
        "decisions": classified_decisions,
        "tasks": classified_tasks,
        "unassigned_tasks": unassigned,
        "risks_or_blockers": risks,
        "monitoring_insights": insights,
    }

    validate_output(output)

    elapsed = (datetime.now() - start).total_seconds()
    print(f"[Async Pipeline] Complete in {elapsed:.1f}s")
    return output


def run_pipeline_async_sync(transcript: str, meeting_date: str = None) -> dict:
    """Synchronous wrapper around the async pipeline — use in non-async contexts."""
    return asyncio.run(run_pipeline_async(transcript, meeting_date))
