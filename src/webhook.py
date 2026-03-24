"""
Webhook Notifier — Meeting Agent Pipeline
Sends structured event payloads to a configured webhook URL after pipeline runs.

Supported events:
  - pipeline_complete    Fires after every successful pipeline run
  - high_risk_detected   Fires when any HIGH severity risk is present
  - unassigned_detected  Fires when unassigned tasks exist
  - restricted_detected  Fires when RESTRICTED sensitivity tasks are present

Configure via environment variables:
  WEBHOOK_ENABLED=true
  WEBHOOK_URL=https://hooks.example.com/your-endpoint
  WEBHOOK_SECRET=your-hmac-secret          (optional — adds X-Signature-256 header)
  WEBHOOK_ON_EVENTS=pipeline_complete,high_risk_detected

Compatible with:
  - Slack incoming webhooks
  - Discord webhooks
  - n8n / Make / Zapier webhook triggers
  - Custom HTTP endpoints
"""

import hashlib
import hmac
import json
import os
import urllib.request
import urllib.error
from datetime import datetime, timezone


# ── Event builder ─────────────────────────────────────────────────────────────

def _build_payload(event: str, result: dict, meta: dict = None) -> dict:
    tasks = result.get("tasks", [])
    risks = result.get("risks_or_blockers", [])

    return {
        "event": event,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "meta": meta or {},
        "summary": result.get("meeting_summary", ""),
        "stats": {
            "task_count": len(tasks),
            "high_priority": sum(1 for t in tasks if t.get("priority") == "HIGH"),
            "restricted_count": sum(1 for t in tasks if t.get("sensitivity") == "RESTRICTED"),
            "unassigned_count": len(result.get("unassigned_tasks", [])),
            "risk_count": len(risks),
            "high_risk_count": sum(1 for r in risks if r.get("severity") == "HIGH"),
        },
        "escalations": [
            a for a in result.get("monitoring_insights", {}).get("recommended_actions", [])
            if a.get("action") == "ESCALATION"
        ],
        "high_risks": [r for r in risks if r.get("severity") == "HIGH"],
        "unassigned_tasks": result.get("unassigned_tasks", []),
    }


# ── HTTP sender ───────────────────────────────────────────────────────────────

def _sign(payload_bytes: bytes, secret: str) -> str:
    """Generate HMAC-SHA256 signature for webhook verification."""
    sig = hmac.new(secret.encode(), payload_bytes, hashlib.sha256).hexdigest()
    return f"sha256={sig}"


def _send(url: str, payload: dict, secret: str = "") -> dict:
    """
    POST JSON payload to the webhook URL.
    Returns dict with {status_code, ok, error}.
    """
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "MeetingAgentPipeline/1.0",
    }
    if secret:
        headers["X-Signature-256"] = _sign(body, secret)

    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return {"status_code": resp.status, "ok": True, "error": None}
    except urllib.error.HTTPError as e:
        return {"status_code": e.code, "ok": False, "error": str(e)}
    except Exception as e:
        return {"status_code": None, "ok": False, "error": str(e)}


# ── Public interface ──────────────────────────────────────────────────────────

def notify(
    result: dict,
    url: str = None,
    secret: str = None,
    enabled_events: list = None,
    meta: dict = None,
) -> list[dict]:
    """
    Fire webhook notifications for all applicable events from a pipeline result.

    Args:
        result:         Pipeline output dict.
        url:            Webhook URL. Falls back to WEBHOOK_URL env var.
        secret:         HMAC secret. Falls back to WEBHOOK_SECRET env var.
        enabled_events: List of event names to fire. Falls back to WEBHOOK_ON_EVENTS env var.
        meta:           Extra metadata to include in every payload (e.g. meeting_id, source).

    Returns:
        List of dicts, one per fired event: {event, status_code, ok, error}.
    """
    url = url or os.environ.get("WEBHOOK_URL", "")
    secret = secret or os.environ.get("WEBHOOK_SECRET", "")
    if not enabled_events:
        raw = os.environ.get("WEBHOOK_ON_EVENTS", "pipeline_complete,high_risk_detected")
        enabled_events = [e.strip() for e in raw.split(",")]

    if not url:
        return []

    tasks = result.get("tasks", [])
    risks = result.get("risks_or_blockers", [])

    # Determine which events to fire
    events_to_fire = []

    if "pipeline_complete" in enabled_events:
        events_to_fire.append("pipeline_complete")

    if "high_risk_detected" in enabled_events:
        if any(r.get("severity") == "HIGH" for r in risks):
            events_to_fire.append("high_risk_detected")

    if "unassigned_detected" in enabled_events:
        if result.get("unassigned_tasks"):
            events_to_fire.append("unassigned_detected")

    if "restricted_detected" in enabled_events:
        if any(t.get("sensitivity") == "RESTRICTED" for t in tasks):
            events_to_fire.append("restricted_detected")

    # Fire
    fired = []
    for event in events_to_fire:
        payload = _build_payload(event, result, meta)
        response = _send(url, payload, secret)
        response["event"] = event
        fired.append(response)
        status = "✓" if response["ok"] else f"✗ ({response['error']})"
        print(f"[Webhook] {event} → {status}")

    return fired


def notify_from_env(result: dict, meta: dict = None) -> list[dict]:
    """
    Fire webhooks using configuration entirely from environment variables.
    Use this in production — no hardcoded values.
    """
    if os.environ.get("WEBHOOK_ENABLED", "").lower() not in ("1", "true", "yes"):
        return []
    return notify(result, meta=meta)


# ── Slack-specific formatter ──────────────────────────────────────────────────

def to_slack_blocks(result: dict) -> dict:
    """
    Format pipeline output as a Slack Block Kit message.
    POST this directly to a Slack incoming webhook URL.
    """
    tasks = result.get("tasks", [])
    risks = result.get("risks_or_blockers", [])
    high_risks = [r for r in risks if r["severity"] == "HIGH"]
    unassigned = result.get("unassigned_tasks", [])
    escalations = [
        a for a in result.get("monitoring_insights", {}).get("recommended_actions", [])
        if a["action"] == "ESCALATION"
    ]

    blocks = [
        {"type": "header", "text": {"type": "plain_text", "text": "Meeting pipeline report"}},
        {"type": "section", "text": {"type": "mrkdwn", "text": result.get("meeting_summary", "")}},
        {"type": "divider"},
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Tasks:* {len(tasks)}"},
                {"type": "mrkdwn", "text": f"*High priority:* {sum(1 for t in tasks if t.get('priority')=='HIGH')}"},
                {"type": "mrkdwn", "text": f"*Unassigned gaps:* {len(unassigned)}"},
                {"type": "mrkdwn", "text": f"*High risks:* {len(high_risks)}"},
            ],
        },
    ]

    if high_risks:
        blocks.append({"type": "divider"})
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": "*🔴 High risks*"}})
        for r in high_risks[:3]:
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"• {r['issue']}\n  _→ {r['suggested_solution']}_"},
            })

    if escalations:
        blocks.append({"type": "divider"})
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": "*🚨 Escalations needed*"}})
        for a in escalations[:3]:
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"• `{a['task_id']}` — {a['reason']}"},
            })

    return {"blocks": blocks}
