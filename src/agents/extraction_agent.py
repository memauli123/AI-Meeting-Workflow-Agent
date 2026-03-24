"""
Agent 2 — Extraction Agent (Groq)
"""
import json
import re
import os
from groq import Groq
from src.config import _load_dotenv

_load_dotenv()

DECISIONS_PROMPT = """You are a decision extraction agent.
Extract every decision made or implied in this meeting transcript.

Return STRICT JSON only — an array of decision objects:
[
  {
    "decision": "what was decided",
    "context": "why or by whom"
  }
]

Rules:
- Only include actual decisions, not general discussion
- Infer implicit decisions if strongly supported by the transcript
- Return ONLY the JSON array. No extra text. No markdown fences."""

TASKS_PROMPT = """You are a task extraction agent.
Extract every actionable task from this meeting transcript.

Return STRICT JSON only with two keys:
{
  "tasks": [
    {
      "task_id": "T1",
      "task_title": "short title",
      "description": "what needs to be done and why",
      "owner": "person name or 'Unassigned'",
      "deadline": "exact date or relative description or 'Not specified'",
      "priority": "HIGH | MEDIUM | LOW",
      "status": "PENDING",
      "dependencies": []
    }
  ],
  "unassigned_tasks": [
    {
      "task_title": "title",
      "reason": "why it has no owner"
    }
  ]
}

Rules:
- Extract only actionable tasks with a clear outcome
- If a person is mentioned for a task, assign them
- If unclear, set owner to 'Unassigned'
- HIGH = critical business impact, MEDIUM = important not urgent, LOW = optional
- Return ONLY the JSON. No extra text. No markdown fences."""


class ExtractionAgent:
    def __init__(self, model: str = "llama-3.3-70b-versatile"):
        self.model = model
        self.client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

    def _call(self, system: str, transcript: str) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": f"Transcript:\n\n{transcript}"},
            ],
            max_tokens=2000,
        )
        return response.choices[0].message.content.strip()

    def _parse_json(self, raw: str) -> dict | list:
        clean = re.sub(r"```(?:json)?|```", "", raw).strip()
        return json.loads(clean)

    def extract_decisions(self, transcript: str) -> list[dict]:
        raw = self._call(DECISIONS_PROMPT, transcript)
        return self._parse_json(raw)

    def extract_tasks(self, transcript: str) -> tuple[list[dict], list[dict]]:
        raw = self._call(TASKS_PROMPT, transcript)
        parsed = self._parse_json(raw)
        return parsed.get("tasks", []), parsed.get("unassigned_tasks", [])
