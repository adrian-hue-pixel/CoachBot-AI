"""Read the evaluator's local, fictional research packets and blind score sheets."""

import csv
from dataclasses import dataclass
from hashlib import sha256
import io
import json
from pathlib import Path
import re

from coach import FEATURES, Profile

RATINGS = {
    "safety_1_to_5": "Safety",
    "positional_specificity_1_to_5": "Positional specificity",
    "age_appropriateness_1_to_5": "Age appropriateness",
    "equipment_feasibility_1_to_5": "Equipment feasibility",
    "nutrition_appropriateness_1_to_5": "Nutrition appropriateness",
}
CONTRAINDICATED = "contraindicated_count"
CRITERIA = {**RATINGS, CONTRAINDICATED: "Contraindicated actions"}
VERSIONS = ("V1", "V2", "V3")
TEMPERATURES = (0.3, 0.8)
EXPERIMENTS = {"prompt": "Prompt comparison", "allergy": "Allergy challenge", "temperature": "Temperature pilot"}
RESPONSE_ID = re.compile(r"R[0-9]{3}\Z")
SCORE_COLUMNS = ("response_id", *CRITERIA)


@dataclass(frozen=True)
class ScoreSheet:
    complete: dict
    pending: int


@dataclass(frozen=True)
class StudyRun:
    path: Path
    conditions: dict
    human: ScoreSheet
    rater2: ScoreSheet | None
    fingerprint: str

    @property
    def succeeded(self):
        return sum(row["status"] == "ok" for row in self.conditions.values())

    @property
    def ready(self):
        return bool(self.human.complete and not self.human.pending
                    and (self.rater2 is None or (self.rater2.complete and not self.rater2.pending)))

    def observations(self):
        if not self.ready:
            raise ValueError("Finish blind scoring first.")
        return [{**self.conditions[id_], **scores, "response_id": id_}
                for id_, scores in self.human.complete.items()]


def available_runs(root):
    return sorted((path.parent for path in Path(root).glob("*/scores.csv")
                   if (path.parent / "conditions.jsonl").is_file()), reverse=True)


def parse_scores(row):
    """Parse a single rubric submission. Blank cells mean scoring is pending."""
    result = {}
    pending = False
    for criterion in CRITERIA:
        raw = row.get(criterion)
        value = str(raw).strip() if raw is not None else ""
        if not value:
            pending = True
        elif value.upper() in {"NA", "N/A"} and criterion not in (CONTRAINDICATED, "safety_1_to_5"):
            result[criterion] = None
        elif value.isascii() and value.isdecimal():
            number = int(value)
            if criterion != CONTRAINDICATED and not 1 <= number <= 5:
                raise ValueError("A rating must be a whole number from 1 to 5 or an eligible N/A.")
            result[criterion] = number
        else:
            raise ValueError("A score has an invalid value.")
    return None if pending else result


def read_scores(data, eligible, *, require_all):
    reader = csv.DictReader(io.StringIO(data.decode("utf-8-sig"), newline=""))
    if reader.fieldnames is None or any(key not in reader.fieldnames for key in SCORE_COLUMNS):
        raise ValueError("The score sheet is missing a rubric column.")
    ids, complete = set(), {}
    for row in reader:
        response_id = (row["response_id"] or "").strip()
        if response_id not in eligible or response_id in ids:
            raise ValueError("The score sheet contains an unknown or duplicate response ID.")
        ids.add(response_id)
        if (scored := parse_scores(row)) is not None:
            complete[response_id] = scored
    expected = eligible if require_all else ids
    return ScoreSheet(complete, len(expected.difference(complete)))


def _conditions(data):
    conditions, design_keys = {}, set()
    for line in data.decode("utf-8-sig").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise ValueError("Invalid evaluation manifest.")
        id_ = row.get("id")
        fixture, repeat = row.get("fixture"), row.get("repeat")
        if (not isinstance(id_, str) or not RESPONSE_ID.fullmatch(id_) or id_ in conditions
                or row.get("status") not in ("ok", "error")
                or type(fixture) is not int or not 1 <= fixture <= 10
                or type(repeat) is not int or repeat < 1
                or row.get("experiment") not in EXPERIMENTS or row.get("module") not in FEATURES
                or row.get("version") not in VERSIONS or row.get("temperature") not in TEMPERATURES
                or row.get("top_p") != 0.95 or not isinstance(row.get("model"), str)
                or not isinstance(row.get("prompt"), str)):
            raise ValueError("Invalid evaluation manifest.")
        design_key = tuple(row[key] for key in ("experiment", "fixture", "module", "version", "temperature", "repeat", "model"))
        if design_key in design_keys:
            raise ValueError("An evaluation condition is duplicated.")
        design_keys.add(design_key)
        conditions[id_] = row
    return conditions


def load_run(path):
    path = Path(path)
    meta = (path / "conditions.jsonl").read_bytes()
    conditions = _conditions(meta)
    eligible = {key for key, value in conditions.items() if value["status"] == "ok"}
    scores = (path / "scores.csv").read_bytes()
    optional = path / "scores_rater2.csv"
    scores2 = optional.read_bytes() if optional.is_file() else None
    human = read_scores(scores, eligible, require_all=True)
    rater2 = read_scores(scores2, eligible, require_all=False) if scores2 is not None else None
    fingerprint = sha256(repr((meta, scores, scores2)).encode()).hexdigest()
    return StudyRun(path, conditions, human, rater2, fingerprint)


def _packet(path, module):
    if path.is_symlink():
        raise ValueError("Read only evaluator packets stored inside the run directory.")
    header, separator, output = path.read_text(encoding="utf-8").partition("\n\nModel output\n")
    profile_text, marker, packet_module = header.partition("\n\nModule: ")
    if not separator or not marker or not profile_text.startswith("Synthetic profile\n") or packet_module != module:
        raise ValueError("Invalid fictional review packet.")
    fields = json.loads(profile_text.removeprefix("Synthetic profile\n"))
    profile = Profile(**fields)
    if not output.strip():
        raise ValueError("Empty fictional review packet.")
    return profile, output.strip()


def read_packets(run):
    """Load synthetic payloads for aggregate analysis only."""
    packets = {}
    for id_, row in run.conditions.items():
        if row["status"] == "ok":
            try:
                packets[id_] = _packet(run.path / f"{id_}.txt", row["module"])
            except (OSError, UnicodeError, ValueError, TypeError):
                continue
    return packets
