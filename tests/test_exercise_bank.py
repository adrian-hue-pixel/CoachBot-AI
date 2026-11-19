from dataclasses import replace
from itertools import product
import json
import re

import pytest

from checkins import LOADS
from coach import Profile, SPORTS
from exercise_bank import (BANK_PATH, CUES, EQUIPMENT, CONSTRAINED, FREE_TEXT, SUPPORTED, demo_draft,
                           drafting_prompt, drafting_schema, eligible_exercises, load_bank, plan_mode, resolve_draft)
from safety import MOVEMENT_PATTERNS, lint_output, normalized

ATHLETE = Profile(15, "Football", "Striker", "SENTINEL personal detail", "None")
FEATURE = "Full-body training"


@pytest.fixture(scope="module")
def bank():
    return load_bank()


def choice(id_, cue=CUES["en"][0]):
    return {"exercise_id": id_, "cue": cue}


def test_bank_has_valid_pending_reviews_and_teacher_notice_policy(bank, tmp_path):
    assert len(bank.entries) == 48
    assert all(not item.reviewed and item.reviewer is None for item in bank.entries)
    assert not bank.reviewed
    data = json.loads(BANK_PATH.read_bytes())
    for entry in data:
        entry.update(reviewed=True, reviewer="PE reviewer")
    path = tmp_path / "bank.json"
    path.write_text(json.dumps(data))
    assert load_bank(path).reviewed
    data[-1]["reviewer"] = None
    path.write_text(json.dumps(data))
    assert not load_bank(path).reviewed
    data[-1]["movement_patterns"] = ["fabricated"]
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        load_bank(path)


@pytest.mark.parametrize("age", [9, 10, 12, 13, 14, 19, 20])
def test_bank_cross_product_never_displays_restricted_or_over_cap_entries(bank, age):
    examples = {
        "": (),
        "No jumping.": ("jump",),
        "No jogging or overhead work.": ("run", "overhead"),
        "Avoid pivots, squats and lunges.": ("cut", "squat", "lunge"),
        "No contact.": ("contact",),
        "Avoid lifting.": ("lift",),
        "No jumping or wrist extension.": ("jump",),
    }
    assert set(key for subset in examples.values() for key in subset) == set(MOVEMENT_PATTERNS)
    for sport, equipment, restriction, cap in product(SPORTS, sorted(EQUIPMENT | {"None"}), examples, LOADS):
        profile = replace(ATHLETE, age=age, sport=sport, position=SPORTS[sport][0],
                          equipment=equipment, restrictions=restriction)
        eligible = eligible_exercises(bank, profile, FEATURE, cap)
        if not 10 <= age <= 19:
            assert not eligible
            continue

        # Send the entire bank through the same resolver in drafts of at most seven rows.
        for start in range(0, len(bank.entries), 7):
            batch = bank.entries[start:start + 7]
            plan, flags = resolve_draft({"rows": [choice(entry.id) for entry in batch]}, bank, eligible, profile, "en", cap)
            expected = [entry for entry in batch if entry.id in eligible]
            if not expected:
                assert plan is None and flags == ("no_eligible_exercise",)
                continue
            assert not flags
            assert [row["exercise_id"] for row in plan["rows"]] == [entry.id for entry in expected]
            for row, entry in zip(plan["rows"], expected, strict=True):
                assert row["action"] == entry.name and row["load"] == entry.load
                assert LOADS.index(row["load"]) <= LOADS.index(cap)
                assert entry.min_age <= age and sport in entry.sports
                assert not entry.equipment or equipment in entry.equipment
                assert set(examples[restriction]).isdisjoint(entry.movement_patterns)
                assert not lint_output(row["action"], profile, cap=cap)
                for tag in examples[restriction]:
                    assert not re.search(rf"(?<!\w)(?:{MOVEMENT_PATTERNS[tag]})(?!\w)", normalized(row["action"]))
                if "wrist extension" in restriction:
                    assert row["load"] == "Rest"


def test_properties_make_restriction_age_and_equipment_checks_nonvacuous(bank):
    standard = replace(ATHLETE, equipment="Ball and cones")
    eligible = eligible_exercises(bank, standard, FEATURE, "Moderate")
    assert {"small_hops", "straight_jog", "inside_pass", "rest_break"} <= set(eligible)
    restricted = eligible_exercises(bank, replace(standard, restrictions="No jumping."), FEATURE, "Moderate")
    assert "small_hops" not in restricted and {"straight_jog", "inside_pass"} <= set(restricted)
    assert "straight_jog" not in eligible_exercises(bank, standard, FEATURE, "Light")
    assert "inside_pass" not in eligible_exercises(bank, standard, "No-equipment training", "Light")
    assert "small_hops" not in eligible_exercises(bank, replace(standard, age=11), FEATURE, "Moderate")


@pytest.mark.parametrize("unknown", ["unknown_x", "", "REST_BREAK", "rest_break ", "../../bank", "空", "REST_BREAK\x00"])
def test_unknown_ids_reject_entire_draft(bank, unknown):
    eligible = eligible_exercises(bank, ATHLETE, FEATURE, "Light")
    for rows in ([choice(unknown)], [choice("rest_break"), choice(unknown)], [choice(unknown), choice("rest_break")]):
        assert resolve_draft({"rows": rows}, bank, eligible, ATHLETE, "en", "Light") == (
            None, ("unknown_exercise_id",)
        )


def test_cues_are_linted_and_cannot_add_an_activity(bank):
    eligible = eligible_exercises(bank, ATHLETE, FEATURE, "Light")
    assert resolve_draft({"rows": [choice("rest_break", "Do a 20-minute jog.")]},
                         bank, eligible, ATHLETE, "en", "Light") == (None, ("workload_cap",))
    assert resolve_draft({"rows": [choice("rest_break", "Use a quiet spot.")]},
                         bank, eligible, ATHLETE, "en", "Light") == (None, ("unapproved_cue",))
    assert resolve_draft({"rows": [choice("rest_break", "Take creatine before practice.")]},
                         bank, eligible, ATHLETE, "en", "Light") == (None, ("supplements",))
    assert resolve_draft({"rows": [{"exercise_id": "rest_break", "cue": CUES["en"][0], "load": "Light"}]},
                         bank, eligible, ATHLETE, "en", "Light") == (None, ("constrained_shape",))


@pytest.mark.parametrize("locale", CUES)
def test_demo_and_sdk_menu_use_only_eligible_ids_and_approved_cues(bank, locale):
    profile = replace(ATHLETE, restrictions="No running.", allergies="SENTINEL sensitive note")
    eligible = eligible_exercises(bank, profile, FEATURE, "Light")
    message = drafting_prompt(profile, FEATURE, locale, eligible)
    assert "SENTINEL" not in message and "No running." not in message
    menu = json.loads(message.rsplit("\nMenu JSON:\n", 1)[1])
    assert set(menu) == {"sport", "position", "module", "choices", "approved_cues"}
    assert {entry["id"] for entry in menu["choices"]} == set(eligible)
    schema = drafting_schema(eligible, locale)["properties"]["rows"]["items"]["properties"]
    assert set(schema["exercise_id"]["enum"]) == set(eligible)
    assert tuple(schema["cue"]["enum"]) == CUES[locale]
    draft = demo_draft(eligible, FEATURE, locale)
    plan, flags = resolve_draft(draft, bank, eligible, profile, locale, "Light")
    assert len(plan["rows"]) == 7 and not flags
    assert any(row["load"] == "Rest" for row in plan["rows"])


def test_constrained_mode_does_not_offer_a_catalog_for_other_modules():
    for feature in ("Return-to-sport schedule", "Weekly nutrition ideas", "Post-injury mobility check-in"):
        assert feature not in SUPPORTED and plan_mode(feature, CONSTRAINED) == FREE_TEXT
