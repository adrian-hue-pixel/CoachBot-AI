"""Export the bank to CSV for PE teacher review. Run as a module from the repository root."""

import argparse
import csv
from pathlib import Path

from exercise_bank import BANK_PATH, load_bank

DETAILS = ("id", "name", "sports", "load", "min_age", "equipment", "movement_patterns", "positions")
COLUMNS = (*DETAILS, "approve", "reject", "comment")


def review_fields(entry):
    fields = {}
    for field in DETAILS:
        value = getattr(entry, field)
        fields[field] = "; ".join(value) if isinstance(value, tuple) else str(value)
    return fields


def export_review_sheet(path, bank_path=BANK_PATH):
    bank = load_bank(bank_path)
    with path.open("x", newline="", encoding="utf-8-sig") as output:
        writer = csv.DictWriter(output, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(review_fields(entry) for entry in bank.entries)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path)
    args = parser.parse_args()
    try:
        export_review_sheet(args.csv)
    except (OSError, ValueError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
