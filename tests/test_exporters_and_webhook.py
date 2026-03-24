"""
Tests — Exporters, Config, Batch helpers, Webhook
No API calls — all logic tests only.
"""

import json
import os
import csv
import tempfile
import pytest
from unittest.mock import patch

from src.exporters import to_json, to_markdown, to_csv, export, export_all
from src.config import PipelineConfig, get_config, reset_config
from src.webhook import _build_payload, to_slack_blocks, _sign
from src.utils.date_normalizer import normalize_dates


# ── Shared fixture ────────────────────────────────────────────────────────────

def sample_result():
    return {
        "meeting_summary": "A test meeting summary covering key decisions.",
        "decisions": [
            {"decision": "Ship v2.4", "context": "By Raj", "sensitivity": "INTERNAL"},
            {"decision": "Salary bands approved", "context": "Confidential", "sensitivity": "RESTRICTED"},
        ],
        "tasks": [
            {
                "task_id": "T1",
                "task_title": "Follow up with vendor",
                "description": "Get the audit report",
                "owner": "James",
                "deadline": "2025-07-14",
                "priority": "HIGH",
                "status": "PENDING",
                "dependencies": ["T2"],
                "sensitivity": "CONFIDENTIAL",
                "allowed_roles": ["MANAGER", "ADMIN"],
                "risk_flags": ["Vendor is external"],
                "masked_preview": "Follow up with [REDACTED] vendor",
            },
            {
                "task_id": "T2",
                "task_title": "Send salary offer letters",
                "description": "Priya sends compensation docs",
                "owner": "Priya",
                "deadline": "2025-07-16",
                "priority": "HIGH",
                "status": "PENDING",
                "dependencies": [],
                "sensitivity": "RESTRICTED",
                "allowed_roles": ["ADMIN", "HR"],
                "risk_flags": [],
                "masked_preview": "Send [REDACTED] offer letters",
            },
        ],
        "unassigned_tasks": [
            {"task_title": "QA ownership", "reason": "Never assigned"}
        ],
        "risks_or_blockers": [
            {"issue": "Audit overdue", "severity": "HIGH", "suggested_solution": "Escalate"},
            {"issue": "QA unassigned", "severity": "HIGH", "suggested_solution": "Assign in 24h"},
            {"issue": "Tight deadline", "severity": "LOW",  "suggested_solution": "Monitor daily"},
        ],
        "monitoring_insights": {
            "overdue_risk_tasks": ["T1"],
            "potential_delays": ["T1 may block staging"],
            "recommended_actions": [
                {"task_id": "T1", "action": "ESCALATION", "reason": "Vendor overdue"},
                {"task_id": "T2", "action": "REMINDER",   "reason": "Restricted task"},
            ],
        },
    }


# ── Exporter — JSON ───────────────────────────────────────────────────────────

class TestJsonExporter:
    def test_to_json_is_valid_json(self):
        out = to_json(sample_result())
        parsed = json.loads(out)
        assert "meeting_summary" in parsed

    def test_to_json_indent(self):
        out = to_json(sample_result(), indent=4)
        assert "    " in out  # 4-space indent present

    def test_export_json_writes_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "out.json")
            result_path = export(sample_result(), "json", path)
            assert os.path.exists(result_path)
            with open(result_path) as f:
                parsed = json.load(f)
            assert parsed["meeting_summary"] == sample_result()["meeting_summary"]


# ── Exporter — Markdown ───────────────────────────────────────────────────────

class TestMarkdownExporter:
    def test_to_markdown_contains_summary(self):
        md = to_markdown(sample_result())
        assert "test meeting summary" in md.lower()

    def test_to_markdown_contains_task_table(self):
        md = to_markdown(sample_result())
        assert "T1" in md
        assert "T2" in md

    def test_to_markdown_contains_sensitivity(self):
        md = to_markdown(sample_result())
        assert "RESTRICTED" in md
        assert "CONFIDENTIAL" in md

    def test_to_markdown_contains_risks(self):
        md = to_markdown(sample_result())
        assert "Audit overdue" in md

    def test_to_markdown_contains_masked_preview(self):
        md = to_markdown(sample_result())
        assert "[REDACTED]" in md

    def test_export_markdown_writes_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "report.md")
            export(sample_result(), "markdown", path)
            assert os.path.exists(path)
            content = open(path, encoding='utf-8').read()
            assert "# Meeting pipeline report" in content

    def test_export_md_alias(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "report.md")
            export(sample_result(), "md", path)
            assert os.path.exists(path)


# ── Exporter — CSV ────────────────────────────────────────────────────────────

class TestCsvExporter:
    def test_to_csv_has_header(self):
        csv_str = to_csv(sample_result())
        reader = csv.DictReader(csv_str.splitlines())
        assert "task_id" in reader.fieldnames
        assert "masked_preview" in reader.fieldnames

    def test_to_csv_row_count(self):
        csv_str = to_csv(sample_result())
        rows = list(csv.DictReader(csv_str.splitlines()))
        assert len(rows) == 2  # T1 + T2

    def test_to_csv_dependencies_joined(self):
        csv_str = to_csv(sample_result())
        rows = list(csv.DictReader(csv_str.splitlines()))
        t1 = next(r for r in rows if r["task_id"] == "T1")
        assert "T2" in t1["dependencies"]

    def test_export_csv_writes_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "tasks.csv")
            export(sample_result(), "csv", path)
            assert os.path.exists(path)

    def test_invalid_format_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            with pytest.raises(ValueError, match="Unknown export format"):
                export(sample_result(), "xml", os.path.join(tmp, "out.xml"))


# ── Export all ────────────────────────────────────────────────────────────────

class TestExportAll:
    def test_export_all_creates_three_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = export_all(sample_result(), tmp, "test_output")
            assert "json"     in paths
            assert "markdown" in paths
            assert "csv"      in paths
            for path in paths.values():
                assert os.path.exists(path)

    def test_export_all_filenames(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = export_all(sample_result(), tmp, "my_meeting")
            assert "my_meeting.json" in paths["json"]
            assert "my_meeting.md"   in paths["markdown"]
            assert "my_meeting.csv"  in paths["csv"]


# ── Config ────────────────────────────────────────────────────────────────────

class TestConfig:
    def setup_method(self):
        reset_config()

    def teardown_method(self):
        reset_config()

    def test_defaults(self):
        cfg = PipelineConfig.__new__(PipelineConfig)
        cfg.__init__()
        assert cfg.model == "claude-sonnet-4-20250514"
        assert cfg.max_tokens == 2000
        assert cfg.validate_output is True
        assert cfg.batch_max_workers == 4

    def test_env_override_model(self):
        with patch.dict(os.environ, {"PIPELINE_MODEL": "claude-opus-4-20250514"}):
            reset_config()
            cfg = PipelineConfig()
            assert cfg.model == "claude-opus-4-20250514"

    def test_env_override_max_tokens(self):
        with patch.dict(os.environ, {"PIPELINE_MAX_TOKENS": "4000"}):
            cfg = PipelineConfig()
            assert cfg.max_tokens == 4000

    def test_env_override_bool(self):
        with patch.dict(os.environ, {"PIPELINE_VALIDATE": "false"}):
            cfg = PipelineConfig()
            assert cfg.validate_output is False

    def test_env_override_list(self):
        with patch.dict(os.environ, {"WEBHOOK_ON_EVENTS": "pipeline_complete,restricted_detected"}):
            cfg = PipelineConfig()
            assert "pipeline_complete" in cfg.webhook_on_events
            assert "restricted_detected" in cfg.webhook_on_events

    def test_validate_raises_without_api_key(self):
        with patch.dict(os.environ, {}, clear=True):
            cfg = PipelineConfig()
            cfg.anthropic_api_key = ""
            with pytest.raises(EnvironmentError, match="ANTHROPIC_API_KEY"):
                cfg.validate()

    def test_to_dict_masks_api_key(self):
        cfg = PipelineConfig()
        cfg.anthropic_api_key = "sk-ant-super-secret"
        d = cfg.to_dict()
        assert "super-secret" not in d["anthropic_api_key"]
        assert "***" in d["anthropic_api_key"]

    def test_singleton(self):
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test"}):
            c1 = get_config()
            c2 = get_config()
            assert c1 is c2


# ── Webhook ───────────────────────────────────────────────────────────────────

class TestWebhook:
    def test_build_payload_structure(self):
        payload = _build_payload("pipeline_complete", sample_result(), meta={"source": "test"})
        assert payload["event"] == "pipeline_complete"
        assert "timestamp" in payload
        assert payload["meta"]["source"] == "test"
        assert payload["stats"]["task_count"] == 2
        assert payload["stats"]["high_risk_count"] == 2

    def test_build_payload_escalations(self):
        payload = _build_payload("high_risk_detected", sample_result())
        assert len(payload["escalations"]) == 1
        assert payload["escalations"][0]["action"] == "ESCALATION"

    def test_build_payload_high_risks_only(self):
        payload = _build_payload("high_risk_detected", sample_result())
        for r in payload["high_risks"]:
            assert r["severity"] == "HIGH"

    def test_sign_produces_sha256(self):
        sig = _sign(b"test payload", "mysecret")
        assert sig.startswith("sha256=")
        assert len(sig) > 10

    def test_sign_deterministic(self):
        s1 = _sign(b"payload", "secret")
        s2 = _sign(b"payload", "secret")
        assert s1 == s2

    def test_sign_different_secrets_differ(self):
        s1 = _sign(b"payload", "secret1")
        s2 = _sign(b"payload", "secret2")
        assert s1 != s2

    def test_slack_blocks_structure(self):
        blocks = to_slack_blocks(sample_result())
        assert "blocks" in blocks
        assert isinstance(blocks["blocks"], list)
        assert blocks["blocks"][0]["type"] == "header"

    def test_slack_blocks_contains_escalation(self):
        blocks_json = json.dumps(to_slack_blocks(sample_result()))
        assert "Escalations needed" in blocks_json or "ESCALATION" in blocks_json or "T1" in blocks_json

    def test_notify_no_url_returns_empty(self):
        from src.webhook import notify
        result = notify(sample_result(), url="", enabled_events=["pipeline_complete"])
        assert result == []

    def test_notify_from_env_disabled(self):
        from src.webhook import notify_from_env
        with patch.dict(os.environ, {"WEBHOOK_ENABLED": "false"}):
            result = notify_from_env(sample_result())
            assert result == []
