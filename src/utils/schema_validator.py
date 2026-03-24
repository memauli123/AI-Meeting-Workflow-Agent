"""
Utility — Schema Validator
Validates the final pipeline output against the required schema.
Raises ValueError with a clear message if any required field is missing.
"""

REQUIRED_TOP_LEVEL = [
    "meeting_summary",
    "decisions",
    "tasks",
    "unassigned_tasks",
    "risks_or_blockers",
    "monitoring_insights",
]

REQUIRED_TASK_FIELDS = [
    "task_id", "task_title", "description", "owner",
    "deadline", "priority", "status", "dependencies",
    "sensitivity", "allowed_roles", "risk_flags", "masked_preview",
]

REQUIRED_DECISION_FIELDS = ["decision", "context", "sensitivity"]

REQUIRED_RISK_FIELDS = ["issue", "severity", "suggested_solution"]

REQUIRED_MONITORING_FIELDS = [
    "overdue_risk_tasks", "potential_delays", "recommended_actions"
]

VALID_SENSITIVITY = {"PUBLIC", "INTERNAL", "CONFIDENTIAL", "RESTRICTED"}
VALID_PRIORITY = {"HIGH", "MEDIUM", "LOW"}
VALID_ACTION = {"REMINDER", "ESCALATION", "REASSIGN"}


def validate_output(output: dict) -> None:
    """
    Validate the pipeline output dict.
    Raises ValueError on the first schema violation found.
    """
    # Top-level keys
    for key in REQUIRED_TOP_LEVEL:
        if key not in output:
            raise ValueError(f"[Validator] Missing top-level key: '{key}'")

    # Decisions
    for i, d in enumerate(output["decisions"]):
        for f in REQUIRED_DECISION_FIELDS:
            if f not in d:
                raise ValueError(f"[Validator] Decision[{i}] missing field: '{f}'")
        if d["sensitivity"] not in VALID_SENSITIVITY:
            raise ValueError(
                f"[Validator] Decision[{i}] invalid sensitivity: '{d['sensitivity']}'"
            )

    # Tasks
    for i, t in enumerate(output["tasks"]):
        for f in REQUIRED_TASK_FIELDS:
            if f not in t:
                raise ValueError(f"[Validator] Task[{i}] missing field: '{f}'")
        if t["sensitivity"] not in VALID_SENSITIVITY:
            raise ValueError(
                f"[Validator] Task[{i}] invalid sensitivity: '{t['sensitivity']}'"
            )
        if t["priority"] not in VALID_PRIORITY:
            raise ValueError(
                f"[Validator] Task[{i}] invalid priority: '{t['priority']}'"
            )
        if not isinstance(t["allowed_roles"], list):
            raise ValueError(f"[Validator] Task[{i}] allowed_roles must be a list")
        if not isinstance(t["risk_flags"], list):
            raise ValueError(f"[Validator] Task[{i}] risk_flags must be a list")

    # Risks
    for i, r in enumerate(output["risks_or_blockers"]):
        for f in REQUIRED_RISK_FIELDS:
            if f not in r:
                raise ValueError(f"[Validator] Risk[{i}] missing field: '{f}'")

    # Monitoring
    m = output["monitoring_insights"]
    for f in REQUIRED_MONITORING_FIELDS:
        if f not in m:
            raise ValueError(f"[Validator] monitoring_insights missing field: '{f}'")
    for i, action in enumerate(m["recommended_actions"]):
        if action.get("action") not in VALID_ACTION:
            raise ValueError(
                f"[Validator] recommended_actions[{i}] invalid action type: '{action.get('action')}'"
            )

    print("[Validator] Schema validation passed.")
