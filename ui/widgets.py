"""Session-only athlete profile wizard."""

import streamlit as st

from coach import FEATURES, SPORTS, Profile
from i18n import LANGUAGES
from ui.components import render_stepper

STEPS = ("Sport & position", "Goal & equipment", "Safety check-in", "Diet & language")
DRAFT = "cb_profile_draft"
DEFAULTS = {
    "sport": next(iter(SPORTS)),
    "position": SPORTS[next(iter(SPORTS))][0],
    "feature": next(iter(FEATURES)),
    "age": 15,
    "goal": "",
    "equipment": "None",
    "intensity": "Easy",
    "injury_status": "No injury reported",
    "restrictions": "",
    "check_in": "No pain or unusual soreness",
    "concern": False,
    "diet": "Vegetarian",
    "allergies": "",
    "language": "English",
}


def init_wizard():
    if DRAFT not in st.session_state:
        st.session_state[DRAFT] = DEFAULTS.copy()
        st.session_state.cb_step = 0
        st.session_state.cb_previous_step = 0
    draft = st.session_state[DRAFT]
    return draft["sport"], draft["position"], draft["feature"]


def _save_field(field):
    draft = st.session_state[DRAFT]
    value = st.session_state[f"_cb_{field}"]
    if draft[field] == value:
        return
    draft[field] = value
    st.session_state.pop("cb_outcome", None)
    st.session_state.pop("cb_chat", None)
    if field == "sport":
        draft["position"] = SPORTS[value][0]
        st.session_state["_cb_position"] = draft["position"]


def _field(widget, field, label, *args, **kwargs):
    key = f"_cb_{field}"
    if key not in st.session_state:
        st.session_state[key] = st.session_state[DRAFT][field]
    return widget(label, *args, key=key, on_change=_save_field, args=(field,), **kwargs)


def _move_step(step):
    current = st.session_state.cb_step
    st.session_state.cb_previous_step = current
    st.session_state.cb_step = step


def profile_wizard(demo):
    step = st.session_state.cb_step
    st.subheader("Athlete profile")
    render_stepper(STEPS, step, st.session_state.cb_previous_step)

    with st.container(key="cb_wizard_step"):
        if step == 0:
            _field(st.selectbox, "sport", "Sport", list(SPORTS))
            sport = st.session_state[DRAFT]["sport"]
            _field(st.selectbox, "position", "Position", SPORTS[sport])
            _field(st.selectbox, "feature", "Coaching module", list(FEATURES))
        elif step == 1:
            _field(st.text_input, "goal", "Goal or skill", max_chars=150, placeholder="Example: improve first touch under pressure")
            _field(st.selectbox, "equipment", "Equipment", ["None", "Ball and cones", "Resistance bands", "School gym"])
            _field(st.selectbox, "intensity", "Preferred intensity", ["Easy", "Moderate"])
        elif step == 2:
            _field(st.number_input, "age", "Age", 10, 19)
            _field(st.selectbox, "injury_status", "Injury status", [
                "No injury reported", "Active injury or awaiting clearance", "Clinician cleared",
            ])
            _field(st.text_input, "restrictions", "Clinician instructions or movements to avoid", max_chars=250)
            _field(st.selectbox, "check_in", "This week", [
                "No pain or unusual soreness", "Mild muscle soreness", "Pain or worsening symptoms",
            ])
            _field(st.checkbox, "concern", "Concerning symptoms, such as suspected concussion or inability to bear weight")
        else:
            _field(st.selectbox, "diet", "Diet", ["Vegetarian", "Non-vegetarian", "Vegan"])
            _field(st.text_input, "allergies", "Food allergies (leave blank if none)", max_chars=120)
            _field(st.selectbox, "language", "Plan language", list(LANGUAGES))
            if demo:
                st.caption("Demo data stays in this session. Leave out names and medical records.")
            else:
                st.caption("Submitted profile fields go to Gemini. Leave out names and medical records.")

    with st.container(key="cb_wizard_actions", horizontal=True, horizontal_alignment="right"):
        if step:
            st.button("Back", on_click=_move_step, args=(step - 1,))
        if step < len(STEPS) - 1:
            st.button("Continue", type="primary", on_click=_move_step, args=(step + 1,))
            return None
        if st.button("Generate coaching plan", type="primary"):
            return profile_from_draft()
    return None


def profile_from_draft():
    values = {key: value for key, value in st.session_state[DRAFT].items() if key not in ("feature", "language")}
    values["goal"] = values["goal"].strip() or "Build sport fundamentals"
    values["restrictions"] = values["restrictions"].strip()
    if st.session_state[DRAFT]["feature"] == "No-equipment training":
        values["equipment"] = "None"
    return Profile(**values)
