"""Entry point for the public CoachBot AI app."""

import os

import streamlit as st

from coach import DEFAULT_MODEL, FEATURES, SPORTS
from exercise_bank import FREE_TEXT, SUPPORTED, load_bank, plan_mode
from i18n import LANGUAGES, gate_copy
from planning import Cooldown, ProfileInputTooLong, ProfileInstructionsRejected, public_gate, run_plan
from ui.components import (render_brand, render_header, render_plan, render_plan_preview, render_shield,
                           render_skeleton, render_tool_card)
from ui.theme import inject_css
from ui.tools import (COOLDOWN_MESSAGE, VERDICTS, current_entries, render_chat, render_checkins,
                      render_exports, render_preparation, safety_badge)
from ui.widgets import DRAFT, init_wizard, profile_from_draft, profile_wizard

GENERATION_ERRORS = {
    400: "The configured model rejected the request. Check model support and settings.",
    401: "Gemini rejected the API key.",
    403: "The API key does not have permission to use this model.",
    404: "The configured model is unavailable to this key. Check GEMINI_MODEL in settings.",
    429: "The Gemini quota was reached. Try again when quota is available.",
}
PAGES = {
    "Home": ("home", ""),
    "Plan": ("assignment", "Build a coaching plan around your sport, position, and goals."),
    "Check-ins": ("event_available", "Track soreness and effort on practice and rest days."),
    "Match prep": ("timer", "Set water reminders and practise pre-match breathing."),
    "Coach chat": ("chat_bubble_outline", "Ask about decisions and match preparation for your sport."),
    "Prompt Lab": ("science", "Explore the prompt comparisons and safety evaluation."),
}


def gemini_settings():
    try:
        settings = dict(st.secrets)
    except FileNotFoundError:
        settings = {}
    key = settings.get("GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY")
    model = settings.get("GEMINI_MODEL") or os.getenv("GEMINI_MODEL", DEFAULT_MODEL)
    return key, model


def submit_profile(profile, feature, locale, entries, key, model, mode=FREE_TEXT, verify=False):
    status = st.status("Preparing your plan…", expanded=True)
    status.write("Reading profile")
    rule = public_gate(profile, feature, entries)
    status.write("Applying profile safety rules")
    if rule:
        if rule != "food_allergies":
            st.session_state.cb_training_paused = True
        status.update(label="Plan paused by profile rules", state="complete", expanded=False)
        return "blocked", rule

    loading = st.empty()

    status.write("Getting coaching draft" if key else "Getting demo example")
    with loading.container():
        render_skeleton()

    try:
        verdict, result, evaluated = run_plan(profile, feature, locale, entries, key, model, mode=mode, verify=verify)
    except Cooldown:
        status.update(label="Request cooldown", state="complete", expanded=False)
        return "info", COOLDOWN_MESSAGE
    except ProfileInputTooLong:
        status.update(label="Profile needs a shorter answer", state="complete", expanded=False)
        return "info", "Shorten the free-text answers in your athlete profile and try again."
    except ProfileInstructionsRejected:
        status.update(label="Profile needs a sport goal", state="complete", expanded=False)
        return "info", "Enter a sport goal or relevant restrictions in your athlete profile and try again."
    except Exception as error:
        status.update(label="Plan unavailable", state="error", expanded=False)
        code = getattr(error, "code", None)
        return "error", GENERATION_ERRORS.get(code, "CoachBot could not return a complete plan. Please try again.")
    else:
        if evaluated:
            status.write(f"Safety check · {VERDICTS[verdict]}")
        label = "Plan ready to review" if evaluated else "Saved plan ready"
        if mode != FREE_TEXT and verdict == "fallback":
            label = "Safe fallback ready"
        status.update(label=label, state="complete", expanded=False)
        return "plan", (verdict, result)
    finally:
        loading.empty()


def show_outcome(outcome, profile, feature, locale, demo, submitted, reduce_motion):
    if outcome is None:
        render_plan_preview(profile, feature)
        return
    kind, content = outcome
    if kind == "blocked":
        render_shield(*gate_copy(locale, content))
    elif kind == "plan":
        verdict, plan = content
        safety_badge(verdict)
        render_plan(plan, feature, stream=submitted, reduce_motion=reduce_motion)
        if plan["rows"]:
            render_exports(plan, feature, demo, locale)
    elif kind == "info":
        st.info(content)
    else:
        st.error(content)


def go_to(page):
    st.session_state.cb_page = page


def render_sidebar(key):
    with st.sidebar:
        render_brand()
        with st.expander("Appearance"):
            reduce_motion = st.toggle("Reduce motion", key="cb_reduce_motion")
        if not key:
            st.info("Demo mode · Sample responses")
        else:
            st.caption("Live mode · Gemini generation")
    return reduce_motion


def render_home(sport, position, reduce_motion):
    with st.container(key="cb_home_hero"):
        render_header(sport, position, reduce_motion)
        with st.container(key="cb_home_actions", horizontal=True, gap="small"):
            st.button("Build a plan", type="primary", on_click=go_to, args=("Plan",))
            st.button("Log a check-in", on_click=go_to, args=("Check-ins",))
    stats = ((len(SPORTS), "Sports"), (sum(map(len, SPORTS.values())), "Positions"),
             (len(FEATURES), "Coaching modules"), (len(LANGUAGES), "Plan languages"))
    st.html('<dl class="cb-home-stats">' + "".join(
        f"<div><dt>{label}</dt><dd>{count}</dd></div>" for count, label in stats
    ) + "</dl>")
    with st.container(key="cb_home_tools"):
        st.subheader("Coaching tools")
        tools = tuple(PAGES.items())[1:]
        for start in range(0, len(tools), 3):
            for column, (page, (icon, description)) in zip(st.columns(3, gap="medium"), tools[start:start + 3]):
                with column, st.container(key=f"cb_tool_{icon}"):
                    render_tool_card(page, icon, description)
                    st.button("Open ›", key=f"cb_open_{icon}", on_click=go_to, args=(page,), help=f"Open {page}")


def render_plan_page(feature, locale, entries, key, model, reduce_motion):
    mode = plan_mode(feature, st.session_state[DRAFT]["plan_mode"])
    with st.container(key="cb_workbench"):
        profile_col, output_col = st.columns([1.8, 1], gap="large")
        with profile_col, st.container(key="cb_wizard"):
            submitted = profile_wizard(demo=not key)
        with output_col, st.container(key="cb_output"):
            st.subheader("Coaching plan")
            if feature in SUPPORTED:
                try:
                    if not load_bank().reviewed:
                        st.warning("Exercise bank not yet reviewed by a teacher.")
                except (OSError, ValueError):
                    st.warning("Exercise bank unavailable. Constrained plans are paused.")
                st.caption(f"Plan mode · {mode}")
            if submitted is not None:
                st.session_state.cb_outcome = submit_profile(
                    submitted, feature, locale, entries, key, model, mode=mode,
                    verify=st.session_state[DRAFT]["verify_plan"],
                )
            show_outcome(st.session_state.get("cb_outcome"), profile_from_draft(), feature, locale, not key,
                         submitted is not None, reduce_motion)


def main():
    st.set_page_config(page_title="CoachBot AI", page_icon="🏅", layout="wide", initial_sidebar_state="collapsed")
    inject_css()
    sport, position, feature = init_wizard()
    key, model = gemini_settings()
    reduce_motion = render_sidebar(key)
    with st.container(key="cb_navigation"):
        page = st.radio("Menu", tuple(PAGES), key="cb_page", horizontal=True, label_visibility="collapsed")
    if page == "Home":
        render_home(sport, position, reduce_motion)
        return
    icon, description = PAGES[page]
    render_header(sport, position, reduce_motion, page, icon, description)
    locale = LANGUAGES[st.session_state[DRAFT]["language"]]
    entries = current_entries()
    if page == "Plan":
        render_plan_page(feature, locale, entries, key, model, reduce_motion)
    elif page == "Check-ins":
        with st.container(key="cb_checkins_panel"):
            render_checkins(profile_from_draft(), locale, reduce_motion)
    elif page == "Match prep":
        with st.container(key="cb_preparation_panel"):
            render_preparation(reduce_motion)
    elif page == "Coach chat":
        with st.container(key="cb_chat_panel"):
            render_chat(profile_from_draft(), locale, entries, key, model, reduce_motion)
    else:
        from lab import render_lab

        render_lab(reduce_motion)

if __name__ == "__main__":
    main()
