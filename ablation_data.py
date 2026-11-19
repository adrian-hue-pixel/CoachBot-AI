"""Read and summarize completed, blinded fictional ablation runs for Prompt Lab."""

import csv
from dataclasses import dataclass
from hashlib import sha256
import io
import json
import math
from pathlib import Path
import re
from statistics import mean

from lab_stats import bootstrap_ci
from verifier import CATEGORIES, LINTER_CATEGORIES

ARMS = ("Raw V1", "V3 prompt", "V3 + linter", "V3 + linter + verifier", "Constrained bank")
SCORE_COLUMNS = ("response_id", "positional_specificity_1_to_5", *CATEGORIES, "notes")
AB_ID = re.compile(r"AB[0-9]{3}")
NUMBERS = ("latency_ms", "input_tokens", "output_tokens", "estimated_usd")
FLAGS = ("fallback", "gated", "verifier_unavailable")
METADATA = {"fixture", "arm", "response_id", "proxy_flags", "role_named", *NUMBERS, *FLAGS}


@dataclass(frozen=True)
class AblationRun:
    source: str
    model: str | None
    fixture_count: int
    bank_sha256: str
    fingerprint: str
    conditions: tuple
    scores: dict

    @property
    def ready(self):
        return len(self.scores) == len(self.conditions)


def available_ablation_runs(root):
    return sorted((path.parent for path in Path(root).glob("*/scores.csv")
                   if (path.parent / "conditions.json").is_file()), reverse=True)


def read_blind_scores(data, ids):
    reader = csv.DictReader(io.StringIO(data.decode("utf-8-sig"), newline=""))
    if tuple(reader.fieldnames or ()) != SCORE_COLUMNS:
        raise ValueError("Invalid ablation score sheet columns.")
    complete, seen = {}, set()
    for row in reader:
        id_ = row["response_id"]
        if id_ not in ids or id_ in seen or None in row or any(value is None for value in row.values()):
            raise ValueError("Unknown, duplicate or incomplete ablation score row.")
        seen.add(id_)
        result = {}
        for key in SCORE_COLUMNS[1:-1]:
            cell = row[key].strip().upper()
            possible = {"1", "2", "3", "4", "5"} if key == "positional_specificity_1_to_5" else {"0", "1"}
            if cell == "N/A":
                result[key] = None
            elif cell in possible:
                result[key] = int(cell)
            elif cell:
                raise ValueError("Invalid ablation rating.")
        if len(result) == len(SCORE_COLUMNS) - 2:
            complete[id_] = result
    return complete


def _number(value):
    return type(value) in (float, int) and math.isfinite(value) and value >= 0


def load_ablation_run(path):
    meta_raw = (path / "conditions.json").read_bytes()
    sheet = (path / "scores.csv").read_bytes()
    document = json.loads(meta_raw)
    model, source, count = document["model"], document["source"], document["fixture_count"]
    bank_hash, conditions = document["bank_sha256"], document["conditions"]
    valid_model = model is None if source == "replay" else (
        isinstance(model, str) and re.fullmatch(r"[A-Za-z0-9._/-]{1,100}", model))
    if (document.get("schema") != 1 or source not in ("live", "replay") or not valid_model
            or type(count) is not int or not 1 <= count <= 10
            or not isinstance(bank_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", bank_hash)
            or not isinstance(conditions, list) or len(conditions) != count * len(ARMS)):
        raise ValueError("Invalid ablation manifest.")
    ids, designs = set(), set()
    for row in conditions:
        id_, arm, fixture = row["response_id"], row["arm"], row["fixture"]
        flags = row["proxy_flags"]
        design = (arm, fixture)
        if (set(row) != METADATA or not isinstance(id_, str) or not AB_ID.fullmatch(id_) or id_ in ids
                or arm not in ARMS or type(fixture) is not int or not 1 <= fixture <= count or design in designs
                or not isinstance(flags, list) or any(item not in LINTER_CATEGORIES for item in flags)
                or any(type(row[field]) is not bool for field in FLAGS)
                or (row["role_named"] is not None and type(row["role_named"]) is not bool)
                or any(row[field] is not None and not _number(row[field]) for field in NUMBERS)
                or (source == "replay" and any(row[field] is not None for field in NUMBERS))
                or (row["gated"] and not row["fallback"])):
            raise ValueError("Invalid or duplicate ablation observation.")
        ids.add(id_)
        designs.add(design)
    scores = read_blind_scores(sheet, ids)
    fingerprint = sha256(meta_raw + b"\0" + sheet).hexdigest()
    return AblationRun(source, model, count, bank_hash, fingerprint, tuple(conditions), scores)


def _estimate(arm, metric, source, values):
    return {"arm": arm, "metric": metric, "source": source, "n": len(values),
            "mean": mean(values) if values else None, "ci": bootstrap_ci(values)}


def summarize_ablation(run):
    if not run.ready:
        raise ValueError("Complete the blind ablation sheet first.")
    outcomes, violations = [], []
    for arm in ARMS:
        group = [row for row in run.conditions if row["arm"] == arm]
        ratings = [run.scores[row["response_id"]] for row in group]
        outcomes.extend([
            _estimate(arm, "Any violation", "Human",
                      [int(any(row[category] for category in CATEGORIES)) for row in ratings
                       if all(row[category] is not None for category in CATEGORIES)]),
            _estimate(arm, "Any violation", "Linter proxy", [int(bool(row["proxy_flags"])) for row in group]),
            _estimate(arm, "Fallback rate", "Pipeline", [int(row["fallback"]) for row in group]),
            _estimate(arm, "Pre-call pause rate", "Pipeline", [int(row["gated"]) for row in group]),
            _estimate(arm, "Verifier unavailable rate", "Pipeline", [int(row["verifier_unavailable"]) for row in group]),
            _estimate(arm, "Positional specificity (1–5)", "Human",
                      [row["positional_specificity_1_to_5"] for row in ratings
                       if row["positional_specificity_1_to_5"] is not None]),
            _estimate(arm, "Role named", "Literal-match proxy",
                      [int(row["role_named"]) for row in group if row["role_named"] is not None]),
        ])
        for field in NUMBERS:
            outcomes.append(_estimate(arm, field, "Measured" if field != "estimated_usd" else "Price estimate",
                                      [row[field] for row in group if row[field] is not None]))
        for category in CATEGORIES:
            observations = [row[category] for row in ratings if row[category] is not None]
            violations.append(_estimate(arm, category, "Human", observations))
            # Keep the full proxy denominator visible next to any available human labels.
            if category in LINTER_CATEGORIES:
                violations.append(_estimate(arm, category, "Linter proxy",
                                            [int(category in row["proxy_flags"]) for row in group]))
    return outcomes, violations
