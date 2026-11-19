"""Deterministic reminders using the selected local practice time."""

from datetime import date, datetime, timedelta


def hydration_schedule(start, duration):
    begins = datetime.combine(date(2000, 1, 2), start)
    end = begins + timedelta(minutes=duration)
    points = [("Before", begins - timedelta(minutes=15)), ("During", begins + timedelta(minutes=duration // 2)),
              ("After", end)]
    return [(label, moment.strftime("%H:%M") + (
        " (previous day)" if moment.date() < begins.date()
        else " (next day)" if moment.date() > begins.date() else ""
    )) for label, moment in points]
