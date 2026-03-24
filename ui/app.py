"""
Web UI — Meeting Agent Pipeline
Streamlit interface for running the pipeline in a browser.

Start with:
    streamlit run ui/app.py
"""

import json
import os
import sys
from datetime import date

# Allow imports from project root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
from src.pipeline import run_pipeline

st.set_page_config(
    page_title="Meeting Agent Pipeline",
    page_icon="🔐",
    layout="wide",
)

# ── Styling ───────────────────────────────────────────────────────────────────

SENSITIVITY_COLORS = {
    "PUBLIC":       "#1D9E75",
    "INTERNAL":     "#185FA5",
    "CONFIDENTIAL": "#BA7517",
    "RESTRICTED":   "#A32D2D",
}

PRIORITY_COLORS = {
    "HIGH":   "#A32D2D",
    "MEDIUM": "#BA7517",
    "LOW":    "#3B6D11",
}

SEVERITY_COLORS = {
    "HIGH":   "#A32D2D",
    "MEDIUM": "#BA7517",
    "LOW":    "#3B6D11",
}

ACTION_COLORS = {
    "ESCALATION": "#A32D2D",
    "REMINDER":   "#BA7517",
    "REASSIGN":   "#534AB7",
}

def badge(text: str, color: str) -> str:
    return (
        f'<span style="background:{color}22;color:{color};'
        f'border-radius:4px;padding:2px 8px;font-size:12px;'
        f'font-weight:500;">{text}</span>'
    )


# ── Header ────────────────────────────────────────────────────────────────────

st.title("Meeting Agent Pipeline")
st.caption("Enterprise multi-agent system — transcript → structured secure workflow JSON")

# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.header("Settings")
    meeting_date = st.date_input(
        "Meeting date",
        value=date.today(),
        help="Used to resolve relative deadlines like 'Friday' or 'tomorrow'",
    )
    show_json = st.toggle("Show raw JSON output", value=False)
    st.divider()
    st.markdown("**Agents**")
    st.markdown("1. Comprehension\n2. Extraction\n3. Classification + RBAC\n4. Risk detection\n5. Monitoring")
    st.divider()
    st.markdown("**Sensitivity levels**")
    for level, color in SENSITIVITY_COLORS.items():
        st.markdown(badge(level, color), unsafe_allow_html=True)

# ── Input ─────────────────────────────────────────────────────────────────────

col1, col2 = st.columns([3, 1])
with col1:
    transcript = st.text_area(
        "Paste your meeting transcript",
        height=220,
        placeholder="[Meeting: Q3 Sync — July 14, 2025]\nSarah: We need to finalize the client proposal by Friday...",
    )
with col2:
    uploaded = st.file_uploader("Or upload a .txt file", type=["txt"])
    if uploaded:
        transcript = uploaded.read().decode("utf-8")
        st.success(f"Loaded: {uploaded.name}")

run_btn = st.button("Run pipeline", type="primary", use_container_width=True)

# ── Pipeline execution ────────────────────────────────────────────────────────

if run_btn:
    if not transcript or not transcript.strip():
        st.error("Please paste a transcript or upload a .txt file.")
        st.stop()

    with st.spinner("Running 5-agent pipeline..."):
        try:
            result = run_pipeline(transcript, meeting_date.isoformat())
        except Exception as e:
            st.error(f"Pipeline error: {e}")
            st.stop()

    st.success("Pipeline complete.")

    # ── Metrics ───────────────────────────────────────────────────────────────
    tasks = result["tasks"]
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Tasks", len(tasks))
    m2.metric("High priority", sum(1 for t in tasks if t["priority"] == "HIGH"))
    m3.metric("Restricted items", sum(1 for t in tasks if t["sensitivity"] == "RESTRICTED"))
    m4.metric("Unassigned gaps", len(result["unassigned_tasks"]))

    # ── Summary ───────────────────────────────────────────────────────────────
    st.subheader("Summary")
    st.info(result["meeting_summary"])

    # ── Decisions ─────────────────────────────────────────────────────────────
    st.subheader("Decisions")
    for d in result["decisions"]:
        color = SENSITIVITY_COLORS.get(d["sensitivity"], "#888")
        st.markdown(
            f'{badge(d["sensitivity"], color)} &nbsp; **{d["decision"]}**<br>'
            f'<span style="color:#888;font-size:13px">{d["context"]}</span>',
            unsafe_allow_html=True,
        )
        st.divider()

    # ── Tasks ─────────────────────────────────────────────────────────────────
    st.subheader("Tasks")
    for t in tasks:
        pc = PRIORITY_COLORS.get(t["priority"], "#888")
        sc = SENSITIVITY_COLORS.get(t["sensitivity"], "#888")
        with st.expander(f"{t['task_id']} — {t['task_title']}"):
            col_a, col_b = st.columns(2)
            with col_a:
                st.markdown(f"**Owner:** {t['owner']}")
                st.markdown(f"**Deadline:** {t['deadline']}")
                st.markdown(
                    f"**Priority:** {badge(t['priority'], pc)} &nbsp; "
                    f"**Sensitivity:** {badge(t['sensitivity'], sc)}",
                    unsafe_allow_html=True,
                )
                st.markdown(f"**Allowed roles:** `{'`, `'.join(t['allowed_roles'])}`")
            with col_b:
                st.markdown(f"**Description:** {t['description']}")
                st.markdown(f"**Masked preview:** _{t['masked_preview']}_")
                if t["dependencies"]:
                    st.markdown(f"**Dependencies:** {', '.join(t['dependencies'])}")
                if t["risk_flags"]:
                    for flag in t["risk_flags"]:
                        st.warning(flag, icon="⚠️")

    # ── Unassigned ────────────────────────────────────────────────────────────
    if result["unassigned_tasks"]:
        st.subheader("Unassigned gaps")
        for u in result["unassigned_tasks"]:
            st.warning(f"**{u['task_title']}** — {u['reason']}", icon="⚠️")

    # ── Risks ─────────────────────────────────────────────────────────────────
    st.subheader("Risks and blockers")
    for r in result["risks_or_blockers"]:
        sc = SEVERITY_COLORS.get(r["severity"], "#888")
        with st.expander(
            f"{badge(r['severity'], sc)} &emsp; {r['issue']}",
            expanded=(r["severity"] == "HIGH"),
        ):
            st.markdown(f"**Suggested solution:** {r['suggested_solution']}", unsafe_allow_html=True)

    # ── Monitoring ────────────────────────────────────────────────────────────
    st.subheader("Monitoring insights")
    insights = result["monitoring_insights"]
    if insights["overdue_risk_tasks"]:
        st.error(f"Overdue-risk tasks: {', '.join(insights['overdue_risk_tasks'])}")
    for action in insights["recommended_actions"]:
        ac = ACTION_COLORS.get(action["action"], "#888")
        st.markdown(
            f"{badge(action['action'], ac)} &nbsp; **{action['task_id']}** — {action['reason']}",
            unsafe_allow_html=True,
        )

    # ── Raw JSON ──────────────────────────────────────────────────────────────
    if show_json:
        st.subheader("Raw JSON output")
        st.json(result)

    # ── Download ──────────────────────────────────────────────────────────────
    st.download_button(
        label="Download JSON output",
        data=json.dumps(result, indent=2, ensure_ascii=False),
        file_name="pipeline_output.json",
        mime="application/json",
    )
