"""Download formats for a checked plan. Files are generated in memory."""

import csv
from datetime import timedelta
from hashlib import sha256
from html import escape
import io

COLUMNS = ("when", "action", "why", "load", "carbs", "protein", "fats")


def _value(row, key):
    value = row.get(key)
    return value if isinstance(value, str) else ""


def csv_plan(rows):
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(("When", "Action", "Why", "Load", "Carbs", "Protein", "Fats"))
    for row in rows:
        values = [_value(row, key) for key in COLUMNS]
        writer.writerow(["'" + value if value.lstrip().startswith(("=", "+", "-", "@"))
                         or value.startswith(("\r", "\n", "\t")) else value for value in values])
    return buffer.getvalue().encode("utf-8-sig")


def _ical_value(value):
    return (value.replace("\\", "\\\\").replace("\r\n", "\n").replace("\r", "\n")
            .replace("\n", "\\n").replace(";", "\\;").replace(",", "\\,"))


def _fold(line):
    pieces = []
    start, size = 0, 0
    for index, char in enumerate(line):
        width = len(char.encode("utf-8"))
        if size + width > 75:
            pieces.append(line[start:index])
            start, size = index, 1
        size += width
    pieces.append(line[start:])
    return "\r\n ".join(pieces)


def calendar_plan(rows, start, now, plan_key):
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//CoachBot AI//Coaching plan//EN", "CALSCALE:GREGORIAN"]
    for index, row in enumerate(rows):
        day = start + timedelta(days=index)
        uid = sha256(f"{plan_key}:{day.isoformat()}".encode()).hexdigest()
        description = " ".join(filter(None, (_value(row, "action"), _value(row, "why"))))
        lines.extend((
            "BEGIN:VEVENT", f"UID:{uid}@coachbot.invalid", f"DTSTAMP:{now:%Y%m%dT%H%M%SZ}",
            f"DTSTART;VALUE=DATE:{day:%Y%m%d}", f"DTEND;VALUE=DATE:{day+timedelta(days=1):%Y%m%d}",
            f"SUMMARY:{_ical_value(_value(row, 'when'))}", f"DESCRIPTION:{_ical_value(description)}",
            "TRANSP:TRANSPARENT", "END:VEVENT",
        ))
    lines.append("END:VCALENDAR")
    return ("\r\n".join(_fold(line) for line in lines) + "\r\n").encode()


def printable_plan(plan, feature, demo, locale):
    articles = []
    for row in plan["rows"]:
        fields = "".join(
            f"<li><strong>{key.capitalize()}</strong> {escape(_value(row, key))}</li>"
            for key in COLUMNS[3:] if _value(row, key)
        )
        articles.append(
            f"<article><h2>{escape(row['when'])}</h2><p>{escape(row['action'])}</p>"
            f"<p>{escape(row['why'])}</p>" + (f"<ul>{fields}</ul>" if fields else "") + "</article>"
        )
    notice = "<p>Demo data</p>" if demo else ""
    return f"""<!doctype html>
<html lang="{locale}"><meta charset="utf-8">
<title>CoachBot AI coaching plan</title>
<style>body{{font:16px/1.5 system-ui;max-width:42rem;margin:2rem auto;padding:0 1rem}}
article{{break-inside:avoid;border-top:1px solid #666}} h2{{font-size:1.1rem}}
p,li{{overflow-wrap:anywhere}} @media print{{body{{margin:0}}}}</style>
<h1>{escape(feature)}</h1>{notice}<p>{escape(plan['summary'])}</p>
{"".join(articles)}
<p>{escape(plan['review'])}</p></html>""".encode()
