"""
Agent 3 — Classification Agent (Groq)
"""
import json
import re
import os
from groq import Groq
from src.config import _load_dotenv

_load_dotenv()

RBAC_MAP = {
    "PUBLIC":       ["ALL"],
    "INTERNAL":     ["TEAM", "MANAGER"],
    "CONFIDENTIAL": ["MANAGER", "ADMIN"],
    "RESTRICTED":   ["ADMIN", "HR"],
}

CLASSIFY_PROMPT = """You are a data classification agent.

For each item in the provided JSON array, add:
  "sensitivity": one of PUBLIC | INTERNAL | CONFIDENTIAL | RESTRICTED

Classification rules:
- RESTRICTED  → salary, compensation, pay bands, HR disciplinary, legal matters
- CONFIDENTIAL → client names/deals, budget figures, vendor contracts, pricing
- INTERNAL    → team plans, sprint work, internal product decisions, onboarding
- PUBLIC      → anything safe for all audiences

Return the SAME JSON array with "sensitivity" added to each object.
Return ONLY the JSON array. No extra text. No markdown fences."""

MASK_PROMPT = """You are a data masking agent.

For each task object in the JSON array, add a "masked_preview" field.
The masked_preview is a safe version of the task_title where:
- Salary figures, compensation amounts, pay bands → [REDACTED]
- Client names, vendor names, contract values → [REDACTED]
- Personal employee details → [REDACTED]
- Budget numbers → [REDACTED]
- Everything else stays visible

Return the SAME JSON array with "masked_preview" added to each task.
Return ONLY the JSON array. No extra text. No markdown fences."""


class ClassificationAgent:
    def __init__(self, model: str = "llama-3.3-70b-versatile"):
        self.model = model
        self.client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

    def _call(self, system: str, payload: list) -> list:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            max_tokens=3000,
        )
        raw = response.choices[0].message.content.strip()
        clean = re.sub(r"```(?:json)?|```", "", raw).strip()
        return json.loads(clean)

    def _apply_rbac(self, items: list) -> list:
        for item in items:
            sensitivity = item.get("sensitivity", "INTERNAL")
            item["allowed_roles"] = RBAC_MAP.get(sensitivity, ["TEAM", "MANAGER"])
        return items

    def classify_decisions(self, decisions: list) -> list:
        classified = self._call(CLASSIFY_PROMPT, decisions)
        return self._apply_rbac(classified)

    def classify_tasks(self, tasks: list) -> list:
        classified = self._call(CLASSIFY_PROMPT, tasks)
        classified = self._apply_rbac(classified)
        classified = self._call(MASK_PROMPT, classified)
        for task in classified:
            task.setdefault("risk_flags", [])
        return classified
