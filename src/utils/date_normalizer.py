"""
Utility — Date Normalizer
Resolves relative deadline strings (e.g. 'Friday', 'tomorrow', 'next week')
into absolute ISO 8601 dates (YYYY-MM-DD) given the meeting date.
"""

from datetime import date, timedelta
import re


WEEKDAY_MAP = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
}


def _next_weekday(from_date: date, weekday: int) -> date:
    """Return the next occurrence of a weekday on or after from_date."""
    days_ahead = weekday - from_date.weekday()
    if days_ahead <= 0:
        days_ahead += 7
    return from_date + timedelta(days=days_ahead)


def resolve_deadline(deadline_str: str, meeting_date: date) -> str:
    """
    Try to resolve a relative deadline string to an ISO date.
    Returns the original string unchanged if it cannot be resolved.
    """
    if not deadline_str or deadline_str.lower() in ("not specified", "tbd", ""):
        return deadline_str

    lower = deadline_str.lower().strip()

    # Already an ISO date
    if re.match(r"\d{4}-\d{2}-\d{2}", lower):
        return deadline_str

    # tomorrow
    if "tomorrow" in lower:
        return (meeting_date + timedelta(days=1)).isoformat()

    # today / same day
    if "today" in lower or "same day" in lower:
        return meeting_date.isoformat()

    # next week — Monday of the calendar week after the meeting's week
    if "next week" in lower:
        days_since_monday = meeting_date.weekday()  # 0=Mon … 6=Sun
        this_monday = meeting_date - timedelta(days=days_since_monday)
        next_monday = this_monday + timedelta(days=7)
        return next_monday.isoformat()

    # named weekday: "Friday", "by Friday", "this Friday"
    for day_name, day_num in WEEKDAY_MAP.items():
        if day_name in lower:
            return _next_weekday(meeting_date, day_num).isoformat()

    # N days: "in 3 days", "within 2 days"
    m = re.search(r"(\d+)\s+days?", lower)
    if m:
        return (meeting_date + timedelta(days=int(m.group(1)))).isoformat()

    # Could not resolve — return as-is
    return deadline_str


def normalize_dates(tasks: list, meeting_date_str: str) -> list:
    """
    Walk through all tasks and resolve relative deadline strings
    to absolute ISO dates using the provided meeting date.

    Args:
        tasks: List of task dicts (each with a 'deadline' field).
        meeting_date_str: The meeting date as 'YYYY-MM-DD'.

    Returns:
        Tasks with deadlines updated where resolution was possible.
    """
    try:
        meeting_date = date.fromisoformat(meeting_date_str)
    except ValueError:
        return tasks  # If date string is invalid, skip normalization

    for task in tasks:
        raw = task.get("deadline", "")
        task["deadline"] = resolve_deadline(raw, meeting_date)

    return tasks
