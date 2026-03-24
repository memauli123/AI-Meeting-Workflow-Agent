"""
Agent 1 — Comprehension Agent (Groq)
"""
import os
from groq import Groq
from src.config import _load_dotenv

_load_dotenv()

SYSTEM_PROMPT = """You are a meeting comprehension agent.
Given a raw meeting transcript, produce a concise 3-4 line summary that covers:
- The main topic(s) discussed
- Key decisions made or pending
- Critical blockers or risks raised
- Any unresolved items

Return ONLY the summary as plain text. No bullet points. No headers."""


class ComprehensionAgent:
    def __init__(self, model: str = "llama-3.3-70b-versatile"):
        self.model = model
        self.client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

    def summarize(self, transcript: str) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Transcript:\n\n{transcript}"},
            ],
            max_tokens=300,
        )
        return response.choices[0].message.content.strip()
