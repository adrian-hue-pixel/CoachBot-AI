"""Read aggregate counts from the offline safety regression suite."""

import json
from pathlib import Path

REPORT = Path(__file__).with_name("benchmarks") / "redteam_offline.json"
CATEGORIES = {
    "instruction": "Instruction and data handling",
    "nutrition": "Nutrition requests",
    "medical": "Medical requests",
    "privacy": "Personal data requests",
    "language": "Language switching",
    "length": "Input length",
    "unicode": "Unicode text handling",
}


def load_redteam_report(path=REPORT):
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = data["categories"]
    if data["schema"] != 1 or data["scope"] != "offline_policy" or set(rows) != set(CATEGORIES):
        raise ValueError("Invalid offline safety report.")
    report = []
    for key, label in CATEGORIES.items():
        row = rows[key]
        n, misses = row["cases"], row["mismatches"]
        if set(row) != {"cases", "mismatches"} or type(n) is not int or type(misses) is not int or not 0 <= misses <= n or not n:
            raise ValueError("Invalid offline safety counts.")
        report.append({"Category": label, "Cases": n, "Mismatches": misses, "Attack success (offline proxy)": f"{misses / n:.1%}"})
    return report
