"""
Agent 4 — Risk Agent (Groq)
"""
import json
import re
import os
from groq import Groq
from src.config import _load_dotenv

_load_dotenv()

SYSTEM_PROMPT = """You are an enterprise risk detection agent.

Given a list of tasks and decisions from a meeting, identify all risks and blockers.

Look for:
- Missing task owners
- Tight or ambiguous deadlines
- Task dependency chains that could cascade
- Single points of failure (one person owns too much)
- Unclear instructions or undefined scope
- Sensitive data handling risks
- External dependencies outside team control

Return STRICT JSON — an array:
[
  {
    "issue": "clear description of the risk or blocker",
    "severity": "HIGH | MEDIUM | LOW",
    "suggested_solution": "concrete recommended action"
  }
]

Return ONLY the JSON array. No extra text. No markdown fences."""


class RiskAgent:
    def __init__(self, model: str = "llama-3.3-70b-versatile"):
        self.model = model
        self.client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

    def detect_risks(self, tasks: list, decisions: list) -> list:
        payload = json.dumps({"tasks": tasks, "decisions": decisions}, ensure_ascii=False)
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": payload},
            ],
            max_tokens=2000,
        )
        raw = response.choices[0].message.content.strip()
        clean = re.sub(r"```(?:json)?|```", "", raw).strip()
        return json.loads(clean)
