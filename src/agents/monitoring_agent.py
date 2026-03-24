"""
Agent 5 — Monitoring Agent (Groq)
"""
import json
import re
import os
from groq import Groq
from src.config import _load_dotenv

_load_dotenv()

SYSTEM_PROMPT = """You are an enterprise monitoring and prediction agent.

Given a list of tasks and risks, produce monitoring intelligence.

Return STRICT JSON:
{
  "overdue_risk_tasks": ["T1", "T3"],
  "potential_delays": [
    "T1 — reason why this task may be delayed"
  ],
  "recommended_actions": [
    {
      "task_id": "T1",
      "action": "REMINDER | ESCALATION | REASSIGN",
      "reason": "why this action is needed"
    }
  ]
}

Action type guide:
- REMINDER    → task is at risk of being forgotten or has a very near deadline
- ESCALATION  → task is blocking others or has missed/will miss a hard deadline
- REASSIGN    → single owner overloaded, no backup, or wrong person assigned

Return ONLY the JSON object. No extra text. No markdown fences."""


class MonitoringAgent:
    def __init__(self, model: str = "llama-3.3-70b-versatile"):
        self.model = model
        self.client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

    def generate_insights(self, tasks: list, risks: list) -> dict:
        payload = json.dumps({"tasks": tasks, "risks": risks}, ensure_ascii=False)
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": payload},
            ],
            max_tokens=1500,
        )
        raw = response.choices[0].message.content.strip()
        clean = re.sub(r"```(?:json)?|```", "", raw).strip()
        return json.loads(clean)
