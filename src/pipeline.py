"""
Meeting Agent Pipeline — Orchestrator
Coordinates all agents and returns final structured JSON output.
"""

import json
from src.config import get_config, _load_dotenv
_load_dotenv()  # Load .env before any agent initialises the Anthropic client
from src.agents.comprehension_agent import ComprehensionAgent
from src.agents.extraction_agent import ExtractionAgent
from src.agents.classification_agent import ClassificationAgent
from src.agents.risk_agent import RiskAgent
from src.agents.monitoring_agent import MonitoringAgent
from src.utils.date_normalizer import normalize_dates
from src.utils.schema_validator import validate_output


def run_pipeline(transcript: str, meeting_date: str = None) -> dict:
    """
    Run the full multi-agent pipeline on a raw meeting transcript.

    Args:
        transcript: Raw meeting transcript text.
        meeting_date: ISO date string (YYYY-MM-DD) of the meeting.
                      Used to resolve relative deadlines like 'Friday' or 'tomorrow'.
                      Defaults to today if not provided.

    Returns:
        Validated structured JSON dict matching the pipeline output schema.
    """
    print("[Pipeline] Starting multi-agent processing...")

    # Agent 1 — Comprehension
    print("[Agent 1] Comprehension...")
    comprehension = ComprehensionAgent()
    summary = comprehension.summarize(transcript)

    # Agent 2 — Extraction
    print("[Agent 2] Extraction...")
    extractor = ExtractionAgent()
    decisions = extractor.extract_decisions(transcript)
    tasks, unassigned = extractor.extract_tasks(transcript)

    # Agent 3 — Classification
    print("[Agent 3] Classification + RBAC...")
    classifier = ClassificationAgent()
    decisions = classifier.classify_decisions(decisions)
    tasks = classifier.classify_tasks(tasks)

    # Agent 4 — Risk Detection
    print("[Agent 4] Risk detection...")
    risk_agent = RiskAgent()
    risks = risk_agent.detect_risks(tasks, decisions)

    # Agent 5 — Monitoring Intelligence
    print("[Agent 5] Monitoring intelligence...")
    monitor = MonitoringAgent()
    insights = monitor.generate_insights(tasks, risks)

    # Date normalization pass
    if meeting_date:
        tasks = normalize_dates(tasks, meeting_date)

    output = {
        "meeting_summary": summary,
        "decisions": decisions,
        "tasks": tasks,
        "unassigned_tasks": unassigned,
        "risks_or_blockers": risks,
        "monitoring_insights": insights,
    }

    # Schema validation
    validate_output(output)

    print("[Pipeline] Complete.")
    return output


def run_pipeline_from_file(transcript_path: str, meeting_date: str = None) -> dict:
    """Load a transcript from a .txt file and run the pipeline."""
    with open(transcript_path, "r", encoding="utf-8") as f:
        transcript = f.read()
    return run_pipeline(transcript, meeting_date)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m src.pipeline <transcript_file> [meeting_date YYYY-MM-DD]")
        sys.exit(1)

    path = sys.argv[1]
    date = sys.argv[2] if len(sys.argv) > 2 else None
    result = run_pipeline_from_file(path, date)
    print(json.dumps(result, indent=2, ensure_ascii=False))
