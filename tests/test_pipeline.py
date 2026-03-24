"""
Tests for the Meeting Agent Pipeline.
Run with: pytest tests/
"""

import pytest
from src.utils.date_normalizer import normalize_dates, resolve_deadline
from src.utils.schema_validator import validate_output
from datetime import date


# ─── Date Normalizer Tests ────────────────────────────────────────────────────

class TestDateNormalizer:
    MEETING_DATE = date(2025, 7, 14)  # Monday

    def test_tomorrow(self):
        result = resolve_deadline("tomorrow", self.MEETING_DATE)
        assert result == "2025-07-15"

    def test_friday(self):
        result = resolve_deadline("Friday", self.MEETING_DATE)
        assert result == "2025-07-18"

    def test_next_week(self):
        result = resolve_deadline("next week", self.MEETING_DATE)
        assert result == "2025-07-21"

    def test_already_iso(self):
        result = resolve_deadline("2025-07-22", self.MEETING_DATE)
        assert result == "2025-07-22"

    def test_not_specified(self):
        result = resolve_deadline("Not specified", self.MEETING_DATE)
        assert result == "Not specified"

    def test_n_days(self):
        result = resolve_deadline("in 3 days", self.MEETING_DATE)
        assert result == "2025-07-17"

    def test_normalize_tasks_list(self):
        tasks = [
            {"task_id": "T1", "deadline": "Friday"},
            {"task_id": "T2", "deadline": "2025-07-22"},
            {"task_id": "T3", "deadline": "tomorrow"},
        ]
        result = normalize_dates(tasks, "2025-07-14")
        assert result[0]["deadline"] == "2025-07-18"
        assert result[1]["deadline"] == "2025-07-22"
        assert result[2]["deadline"] == "2025-07-15"


# ─── Schema Validator Tests ───────────────────────────────────────────────────

def _make_valid_output():
    return {
        "meeting_summary": "Test summary.",
        "decisions": [
            {"decision": "Do X", "context": "Because Y", "sensitivity": "INTERNAL"}
        ],
        "tasks": [
            {
                "task_id": "T1",
                "task_title": "Test task",
                "description": "Do the thing",
                "owner": "Alice",
                "deadline": "2025-07-18",
                "priority": "HIGH",
                "status": "PENDING",
                "dependencies": [],
                "sensitivity": "INTERNAL",
                "allowed_roles": ["TEAM", "MANAGER"],
                "risk_flags": [],
                "masked_preview": "Test task",
            }
        ],
        "unassigned_tasks": [],
        "risks_or_blockers": [
            {"issue": "Some risk", "severity": "MEDIUM", "suggested_solution": "Fix it"}
        ],
        "monitoring_insights": {
            "overdue_risk_tasks": [],
            "potential_delays": [],
            "recommended_actions": [
                {"task_id": "T1", "action": "REMINDER", "reason": "Deadline soon"}
            ],
        },
    }


class TestSchemaValidator:
    def test_valid_output_passes(self):
        validate_output(_make_valid_output())  # should not raise

    def test_missing_top_level_key_raises(self):
        output = _make_valid_output()
        del output["decisions"]
        with pytest.raises(ValueError, match="Missing top-level key"):
            validate_output(output)

    def test_invalid_sensitivity_raises(self):
        output = _make_valid_output()
        output["tasks"][0]["sensitivity"] = "TOP_SECRET"
        with pytest.raises(ValueError, match="invalid sensitivity"):
            validate_output(output)

    def test_invalid_priority_raises(self):
        output = _make_valid_output()
        output["tasks"][0]["priority"] = "URGENT"
        with pytest.raises(ValueError, match="invalid priority"):
            validate_output(output)

    def test_invalid_action_type_raises(self):
        output = _make_valid_output()
        output["monitoring_insights"]["recommended_actions"][0]["action"] = "FIRE"
        with pytest.raises(ValueError, match="invalid action type"):
            validate_output(output)

    def test_missing_task_field_raises(self):
        output = _make_valid_output()
        del output["tasks"][0]["masked_preview"]
        with pytest.raises(ValueError, match="missing field: 'masked_preview'"):
            validate_output(output)
