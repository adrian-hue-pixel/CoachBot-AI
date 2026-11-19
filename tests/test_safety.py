from dataclasses import replace

import pytest

from coach import FEATURES, Profile
from i18n import GATE_MESSAGES


athlete = Profile(15, "Football", "Striker", "Improve positioning", "Ball and cones")

PAUSE = "Pause training and tell a trusted adult. Seek advice from a qualified clinician before resuming."
CLEARANCE = "Ask a qualified clinician about return to sport. Review their approved plan with your coach before training."
GUIDANCE = "This feature needs clinician clearance and written guidance. Enter only the relevant movement restrictions or instructions."
ALLERGY = "Ask a caregiver or dietitian to help choose meals and check labels and cross-contact. This module pauses personalized meal ideas when allergies are reported."


@pytest.mark.parametrize("feature", FEATURES)
@pytest.mark.parametrize("changes", [{"concern": True}, {"check_in": "Pain or worsening symptoms"}])
def test_concerning_symptoms_or_pain_block_every_module(feature, changes):
    assert replace(athlete, **changes).block(feature) == PAUSE


@pytest.mark.parametrize(
    "feature, expected",
    [
        ("Full-body training", CLEARANCE),
        ("Return-to-sport schedule", CLEARANCE),
        ("Warm-up and cooldown", CLEARANCE),
        ("Weekly nutrition ideas", ""),
        ("Tactical coaching", ""),
        ("Pre-match mental focus", ""),
        ("Hydration and electrolytes", ""),
        ("Positional drills", CLEARANCE),
        ("Post-injury mobility check-in", CLEARANCE),
        ("No-equipment training", CLEARANCE),
        ("Weekly progress adaptation", CLEARANCE),
    ],
)
def test_active_injury_blocks_physical_modules(feature, expected):
    profile = replace(athlete, injury_status="Active injury or awaiting clearance")
    assert profile.block(feature) == expected


@pytest.mark.parametrize("feature", ["Return-to-sport schedule", "Post-injury mobility check-in"])
def test_recovery_requires_clearance_and_guidance(feature):
    assert athlete.block(feature) == GUIDANCE
    cleared = replace(athlete, injury_status="Clinician cleared")
    assert replace(cleared, restrictions="  ").block(feature) == GUIDANCE
    assert replace(cleared, restrictions="No jumping.").block(feature) == ""
    assert replace(athlete, restrictions="No jumping.").block(feature) == GUIDANCE


def test_allergies_block_nutrition_only():
    profile = replace(athlete, allergies=" Peanuts ")
    assert profile.block("Weekly nutrition ideas") == ALLERGY
    assert profile.block("Hydration and electrolytes") == ""
    assert replace(athlete, allergies="  ").block("Weekly nutrition ideas") == ""


def test_concerning_symptoms_take_precedence():
    profile = replace(athlete, concern=True, allergies="Peanuts",
                      injury_status="Active injury or awaiting clearance")
    assert profile.block("Weekly nutrition ideas") == PAUSE
    assert profile.block("Return-to-sport schedule") == PAUSE


def test_mild_soreness_is_not_an_existing_gate():
    profile = replace(athlete, check_in="Mild muscle soreness")
    assert profile.block("Full-body training") == ""


def test_static_gate_translations_have_matching_nonempty_keys():
    assert set(GATE_MESSAGES) == {"en", "ta", "hi"}
    english_keys = set(GATE_MESSAGES["en"])
    assert english_keys
    for translations in GATE_MESSAGES.values():
        assert set(translations) == english_keys
        assert all(message.strip() for message in translations.values())
