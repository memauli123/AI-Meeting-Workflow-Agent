"""
Extended tests — Meeting Agent Pipeline
Covers schema validator edge cases, date normalizer edge cases,
and pipeline output structure contracts.

Run with: pytest tests/ -v
"""

import pytest
from src.utils.date_normalizer import normalize_dates, resolve_deadline
from src.utils.schema_validator import validate_output
from datetime import date
import copy


# ─── Shared fixture ───────────────────────────────────────────────────────────

def make_valid_output():
    return {
        "meeting_summary": "Test summary covering key decisions and blockers.",
        "decisions": [
            {"decision": "Ship v2.4 by Friday", "context": "Agreed by Raj", "sensitivity": "INTERNAL"},
            {"decision": "Salary bands approved", "context": "Keep confidential", "sensitivity": "RESTRICTED"},
        ],
        "tasks": [
            {
                "task_id": "T1",
                "task_title": "Follow up with vendor",
                "description": "Contact vendor for audit report",
                "owner": "James",
                "deadline": "2025-07-14",
                "priority": "HIGH",
                "status": "PENDING",
                "dependencies": [],
                "sensitivity": "CONFIDENTIAL",
                "allowed_roles": ["MANAGER", "ADMIN"],
                "risk_flags": ["Vendor is external", "Blocks staging"],
                "masked_preview": "Follow up with [REDACTED] vendor",
            },
            {
                "task_id": "T2",
                "task_title": "Send revised salary bands",
                "description": "HR sends compensation letters",
                "owner": "Priya",
                "deadline": "2025-07-16",
                "priority": "HIGH",
                "status": "PENDING",
                "dependencies": [],
                "sensitivity": "RESTRICTED",
                "allowed_roles": ["ADMIN", "HR"],
                "risk_flags": [],
                "masked_preview": "Send [REDACTED] salary bands to [REDACTED]",
            },
        ],
        "unassigned_tasks": [
            {"task_title": "QA cycle ownership", "reason": "Never assigned in meeting"}
        ],
        "risks_or_blockers": [
            {"issue": "Vendor audit overdue", "severity": "HIGH", "suggested_solution": "Escalate today"},
            {"issue": "QA unassigned", "severity": "HIGH", "suggested_solution": "Assign in 24h"},
        ],
        "monitoring_insights": {
            "overdue_risk_tasks": ["T1"],
            "potential_delays": ["T1 may delay staging"],
            "recommended_actions": [
                {"task_id": "T1", "action": "ESCALATION", "reason": "Vendor overdue"},
                {"task_id": "T2", "action": "REMINDER", "reason": "Restricted data task"},
            ],
        },
    }


# ─── Date Normalizer ──────────────────────────────────────────────────────────

class TestDateNormalizerExtended:
    MEETING = date(2025, 7, 14)  # Monday

    def test_today(self):
        assert resolve_deadline("today", self.MEETING) == "2025-07-14"

    def test_same_day(self):
        assert resolve_deadline("same day", self.MEETING) == "2025-07-14"

    def test_tomorrow(self):
        assert resolve_deadline("tomorrow", self.MEETING) == "2025-07-15"

    def test_friday_from_monday(self):
        assert resolve_deadline("Friday", self.MEETING) == "2025-07-18"

    def test_monday_wraps_to_next_week(self):
        # Meeting is Monday July 14 — next Monday is July 21
        assert resolve_deadline("Monday", self.MEETING) == "2025-07-21"

    def test_next_week(self):
        assert resolve_deadline("next week", self.MEETING) == "2025-07-21"

    def test_n_days(self):
        assert resolve_deadline("in 3 days", self.MEETING) == "2025-07-17"

    def test_within_n_days(self):
        assert resolve_deadline("within 2 days", self.MEETING) == "2025-07-16"

    def test_already_iso_passthrough(self):
        assert resolve_deadline("2025-07-22", self.MEETING) == "2025-07-22"

    def test_not_specified_passthrough(self):
        assert resolve_deadline("Not specified", self.MEETING) == "Not specified"

    def test_tbd_passthrough(self):
        assert resolve_deadline("TBD", self.MEETING) == "TBD"

    def test_empty_string_passthrough(self):
        assert resolve_deadline("", self.MEETING) == ""

    def test_invalid_meeting_date_returns_unchanged(self):
        tasks = [{"task_id": "T1", "deadline": "Friday"}]
        result = normalize_dates(tasks, "not-a-date")
        assert result[0]["deadline"] == "Friday"

    def test_normalize_tasks_list_multiple(self):
        tasks = [
            {"task_id": "T1", "deadline": "tomorrow"},
            {"task_id": "T2", "deadline": "2025-07-22"},
            {"task_id": "T3", "deadline": "Friday"},
            {"task_id": "T4", "deadline": "Not specified"},
        ]
        result = normalize_dates(tasks, "2025-07-14")
        assert result[0]["deadline"] == "2025-07-15"
        assert result[1]["deadline"] == "2025-07-22"
        assert result[2]["deadline"] == "2025-07-18"
        assert result[3]["deadline"] == "Not specified"


# ─── Schema Validator — Pass Cases ───────────────────────────────────────────

class TestSchemaValidatorPass:
    def test_full_valid_output(self):
        validate_output(make_valid_output())

    def test_empty_unassigned_tasks(self):
        o = make_valid_output()
        o["unassigned_tasks"] = []
        validate_output(o)

    def test_empty_risk_flags_on_task(self):
        o = make_valid_output()
        o["tasks"][0]["risk_flags"] = []
        validate_output(o)

    def test_empty_dependencies(self):
        o = make_valid_output()
        o["tasks"][0]["dependencies"] = []
        validate_output(o)

    def test_all_sensitivity_levels(self):
        for level in ("PUBLIC", "INTERNAL", "CONFIDENTIAL", "RESTRICTED"):
            o = make_valid_output()
            o["tasks"][0]["sensitivity"] = level
            o["decisions"][0]["sensitivity"] = level
            validate_output(o)

    def test_all_priority_levels(self):
        for level in ("HIGH", "MEDIUM", "LOW"):
            o = make_valid_output()
            o["tasks"][0]["priority"] = level
            validate_output(o)

    def test_all_action_types(self):
        for action in ("REMINDER", "ESCALATION", "REASSIGN"):
            o = make_valid_output()
            o["monitoring_insights"]["recommended_actions"][0]["action"] = action
            validate_output(o)


# ─── Schema Validator — Fail Cases ───────────────────────────────────────────

class TestSchemaValidatorFail:
    @pytest.mark.parametrize("key", [
        "meeting_summary", "decisions", "tasks",
        "unassigned_tasks", "risks_or_blockers", "monitoring_insights",
    ])
    def test_missing_top_level_key(self, key):
        o = make_valid_output()
        del o[key]
        with pytest.raises(ValueError, match="Missing top-level key"):
            validate_output(o)

    @pytest.mark.parametrize("field", [
        "task_id", "task_title", "description", "owner",
        "deadline", "priority", "status", "dependencies",
        "sensitivity", "allowed_roles", "risk_flags", "masked_preview",
    ])
    def test_missing_task_field(self, field):
        o = make_valid_output()
        del o["tasks"][0][field]
        with pytest.raises(ValueError, match=f"missing field: '{field}'"):
            validate_output(o)

    @pytest.mark.parametrize("field", ["decision", "context", "sensitivity"])
    def test_missing_decision_field(self, field):
        o = make_valid_output()
        del o["decisions"][0][field]
        with pytest.raises(ValueError, match=f"missing field: '{field}'"):
            validate_output(o)

    @pytest.mark.parametrize("field", ["issue", "severity", "suggested_solution"])
    def test_missing_risk_field(self, field):
        o = make_valid_output()
        del o["risks_or_blockers"][0][field]
        with pytest.raises(ValueError, match=f"missing field: '{field}'"):
            validate_output(o)

    def test_invalid_task_sensitivity(self):
        o = make_valid_output()
        o["tasks"][0]["sensitivity"] = "TOP_SECRET"
        with pytest.raises(ValueError, match="invalid sensitivity"):
            validate_output(o)

    def test_invalid_decision_sensitivity(self):
        o = make_valid_output()
        o["decisions"][0]["sensitivity"] = "CLASSIFIED"
        with pytest.raises(ValueError, match="invalid sensitivity"):
            validate_output(o)

    def test_invalid_priority(self):
        o = make_valid_output()
        o["tasks"][0]["priority"] = "CRITICAL"
        with pytest.raises(ValueError, match="invalid priority"):
            validate_output(o)

    def test_invalid_action_type(self):
        o = make_valid_output()
        o["monitoring_insights"]["recommended_actions"][0]["action"] = "DELETE"
        with pytest.raises(ValueError, match="invalid action type"):
            validate_output(o)

    def test_allowed_roles_not_list(self):
        o = make_valid_output()
        o["tasks"][0]["allowed_roles"] = "ADMIN"
        with pytest.raises(ValueError, match="allowed_roles must be a list"):
            validate_output(o)

    def test_risk_flags_not_list(self):
        o = make_valid_output()
        o["tasks"][0]["risk_flags"] = "some flag"
        with pytest.raises(ValueError, match="risk_flags must be a list"):
            validate_output(o)

    @pytest.mark.parametrize("field", [
        "overdue_risk_tasks", "potential_delays", "recommended_actions"
    ])
    def test_missing_monitoring_field(self, field):
        o = make_valid_output()
        del o["monitoring_insights"][field]
        with pytest.raises(ValueError, match=f"missing field: '{field}'"):
            validate_output(o)


# ─── RBAC mapping contract ────────────────────────────────────────────────────

class TestRBACContract:
    """Verify the RBAC_MAP in classification_agent is correctly structured."""

    def test_rbac_map_keys(self):
        from src.agents.classification_agent import RBAC_MAP
        assert set(RBAC_MAP.keys()) == {"PUBLIC", "INTERNAL", "CONFIDENTIAL", "RESTRICTED"}

    def test_rbac_map_values_are_lists(self):
        from src.agents.classification_agent import RBAC_MAP
        for level, roles in RBAC_MAP.items():
            assert isinstance(roles, list), f"{level} roles should be a list"

    def test_restricted_has_no_team(self):
        from src.agents.classification_agent import RBAC_MAP
        assert "TEAM" not in RBAC_MAP["RESTRICTED"]

    def test_public_allows_all(self):
        from src.agents.classification_agent import RBAC_MAP
        assert RBAC_MAP["PUBLIC"] == ["ALL"]
