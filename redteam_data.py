"""Read checksum-pinned fixtures and aggregate offline policy counts."""

from hashlib import sha256
import json
from pathlib import Path

from lint_validation import wilson_interval

BENCHMARKS = Path(__file__).with_name("benchmarks")
REPORT = BENCHMARKS / "redteam_offline.json"
HELD_OUT = BENCHMARKS / "redteam_held_out_v1.json"
HELD_OUT_SHA256 = "2a6368d3d4614165cd03e2d52191d80aed0f7a70267dca68c5be52b80b081ae4"
CATEGORIES = {
    "instruction": "Instruction and data handling",
    "nutrition": "Nutrition requests",
    "medical": "Medical requests",
    "privacy": "Personal data requests",
    "language": "Language switching",
    "length": "Input length",
    "unicode": "Unicode text handling",
}
SETS = {"development": "Development", "held_out": "Frozen held-out"}


def read_held_out(path=None):
    data = (HELD_OUT if path is None else path).read_bytes()
    if sha256(data).hexdigest() != HELD_OUT_SHA256:
        raise ValueError("Held-out safety cases do not match the frozen SHA-256.")
    return json.loads(data)


def load_redteam_report(path=REPORT):
    data = json.loads(path.read_text(encoding="utf-8"))
    if (data["schema"] != 2 or data["scope"] != "authored_synthetic_policy_cases"
            or data["held_out_sha256"] != HELD_OUT_SHA256 or set(data["sets"]) != set(SETS)):
        raise ValueError("Invalid offline safety report.")
    read_held_out()
    report = []
    for set_name, label in SETS.items():
        rows = data["sets"][set_name]
        if set(rows) != set(CATEGORIES):
            raise ValueError("Invalid offline safety categories.")
        for key, category in CATEGORIES.items():
            row = rows[key]
            n, misses = row["cases"], row["mismatches"]
            if (set(row) != {"cases", "mismatches"} or type(n) is not int or type(misses) is not int
                    or not 0 <= misses <= n or not n):
                raise ValueError("Invalid offline safety counts.")
            matched = n - misses
            lower, upper = wilson_interval(matched, n)
            report.append({"Set": label, "Category": category, "Cases": n, "Matches": matched,
                           "Mismatches": misses, "Matched": f"{matched / n:.1%}", "Wilson 95% CI": f"{lower:.1%}–{upper:.1%}"})
    return report
