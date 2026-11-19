"""Apply explicit teacher approvals to the exercise bank. Run as a module from the repository root."""

import argparse
import csv
import json
from pathlib import Path
from tempfile import NamedTemporaryFile

from exercise_bank import BANK_PATH, parse_bank
from tools.export_review_sheet import COLUMNS, review_fields

YES = {"yes", "y", "true", "1", "x"}
NO = {"", "no", "n", "false", "0"}


def _marked(cell):
    value = cell.strip().casefold()
    if value not in YES | NO:
        raise ValueError("Use an explicit yes or x to mark an approval or rejection.")
    return value in YES


def _bank_json(rows):
    records = []
    for row in rows:
        fields = [f"    {json.dumps(field)}: {json.dumps(value, ensure_ascii=False)}" for field, value in row.items()]
        records.append("  {\n" + ",\n".join(fields) + "\n  }")
    return ("[\n" + ",\n".join(records) + "\n]\n").encode()


def apply_review(path, reviewer, bank_path=BANK_PATH):
    reviewer = reviewer.strip()
    if not reviewer or len(reviewer) > 120 or not reviewer.isprintable():
        raise ValueError("Provide the teacher's agreed display name or role.")
    raw = bank_path.read_bytes()
    bank = parse_bank(raw)
    entries = {entry.id: review_fields(entry) for entry in bank.entries}
    approved, rejected, seen = set(), [], set()
    with path.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        if tuple(reader.fieldnames or ()) != COLUMNS:
            raise ValueError("Use the columns from the exported review sheet.")
        for row in reader:
            id_ = row["id"]
            if id_ not in entries or id_ in seen or None in row or any(value is None for value in row.values()):
                raise ValueError("The sheet has an unknown, duplicate or incomplete record.")
            seen.add(id_)
            if any(row[field] != value for field, value in entries[id_].items()):
                raise ValueError(f"Exercise details changed for {id_}. Export a fresh sheet and review it again.")
            approve, reject = _marked(row["approve"]), _marked(row["reject"])
            if approve and reject:
                raise ValueError(f"Mark only one decision for {id_}.")
            if approve:
                approved.add(id_)
            elif reject:
                rejected.append(id_)
    if not approved:
        return approved, rejected, bank.fingerprint
    data = json.loads(raw)
    for row in data:
        if row["id"] in approved:
            row.update(reviewer=reviewer, reviewed=True)
    updated = _bank_json(data)
    fingerprint = parse_bank(updated).fingerprint
    with NamedTemporaryFile(dir=bank_path.parent, delete=False) as temp:
        staging = Path(temp.name)
        temp.write(updated)
    try:
        if bank_path.read_bytes() != raw:
            raise ValueError("Exercise bank changed during review. Export a fresh review sheet.")
        staging.chmod(bank_path.stat().st_mode & 0o777)
        staging.replace(bank_path)
    finally:
        staging.unlink(missing_ok=True)
    return approved, rejected, fingerprint


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path)
    parser.add_argument("--reviewer", required=True)
    args = parser.parse_args()
    try:
        approved, rejected, fingerprint = apply_review(args.csv, args.reviewer)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(f"Approvals applied: {len(approved)}")
    if rejected:
        print("Edit or remove these rejected entries manually: " + ", ".join(rejected))
    print(f"Bank SHA-256: {fingerprint}")


if __name__ == "__main__":
    main()
