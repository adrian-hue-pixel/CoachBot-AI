import csv
from hashlib import sha256

import pytest

from exercise_bank import BANK_PATH, load_bank
from tools import apply_review, export_review_sheet


@pytest.fixture
def sheet(tmp_path):
    bank = tmp_path / "exercises.json"
    bank.write_bytes(BANK_PATH.read_bytes())
    sheet = tmp_path / "review.csv"
    export_review_sheet.export_review_sheet(sheet, bank)
    with sheet.open(encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file))
    return bank, sheet, rows


def write_sheet(sheet, rows):
    with sheet.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=export_review_sheet.COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def test_export_contains_every_bank_record_and_empty_decisions(sheet):
    bank, path, rows = sheet
    assert len(rows) == len(load_bank(bank).entries)
    assert tuple(rows[0]) == export_review_sheet.COLUMNS
    assert all(not any(row[field] for field in ("approve", "reject", "comment")) for row in rows)
    assert next(row["positions"] for row in rows if row["id"] == "goalkeeper_roll") == "Goalkeeper"
    assert "Football" in rows[0]["sports"]
    with pytest.raises(FileExistsError):
        export_review_sheet.export_review_sheet(path, bank)


def test_apply_marks_only_approvals_and_prints_rejections_and_hash(sheet, monkeypatch, capsys):
    bank, path, rows = sheet
    rows[0]["approve"] = "X"
    rows[1]["reject"] = "yes"
    rows[1]["comment"] = "Review this entry again."
    write_sheet(path, rows)
    monkeypatch.setattr(apply_review, "apply_review", lambda sheet, reviewer: apply(sheet, reviewer, bank))
    monkeypatch.setattr("sys.argv", ["apply_review", str(path), "--reviewer", "PE reviewer"])
    apply_review.main()
    entries = load_bank(bank).entries
    assert entries[0].reviewed and entries[0].reviewer == "PE reviewer"
    assert all(not entry.reviewed and entry.reviewer is None for entry in entries[1:])
    out = capsys.readouterr().out
    assert entries[1].id in out and sha256(bank.read_bytes()).hexdigest() in out
    assert "Review this entry again." not in bank.read_text()


apply = apply_review.apply_review


@pytest.mark.parametrize("error", ["both", "stale", "duplicate", "forged", "ambiguous"])
def test_invalid_sheet_leaves_bank_untouched(sheet, error):
    bank, path, rows = sheet
    before = bank.read_bytes()
    rows[0]["approve"] = "yes"
    if error == "both":
        rows[0]["reject"] = "yes"
    elif error == "stale":
        rows[0]["name"] += " outdated"
    elif error == "duplicate":
        rows.append(rows[0])
    elif error == "forged":
        rows[0]["id"] = "forged"
    else:
        rows[0]["approve"] = "probably"
    write_sheet(path, rows)
    with pytest.raises(ValueError):
        apply(path, "PE reviewer", bank)
    assert bank.read_bytes() == before
