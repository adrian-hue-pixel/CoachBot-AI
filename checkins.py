"""Session check-in rules shared by the planner, chat and progress display."""

from dataclasses import dataclass
from datetime import timedelta

LOADS = ("Rest", "Light", "Moderate")


@dataclass(frozen=True)
class CheckIn:
    soreness: int
    effort: int
    rest_day: bool


def recent_checkins(entries, today):
    return {day: entry for day, entry in entries.items() if 0 <= (today - day).days < 7}


def checkin_rule(entries):
    if any(entry.soreness >= 4 for entry in entries.values()):
        return "high_soreness"
    for day, current in entries.items():
        previous = entries.get(day - timedelta(days=1))
        earlier = entries.get(day - timedelta(days=2))
        if earlier and previous and earlier.soreness < previous.soreness < current.soreness:
            return "rising_soreness"
    return None


def workload_cap(preference, entries):
    return "Light" if preference == "Easy" or any(
        entry.soreness >= 3 or entry.effort >= 8 for entry in entries.values()
    ) else "Moderate"
