"""Streamlit views for check-ins, preparation, safe chat and exports."""

from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import streamlit as st

from checkins import CheckIn, checkin_rule, recent_checkins
from exports import calendar_plan, csv_plan, printable_plan
from hydration import hydration_schedule
from i18n import CHAT_REFUSAL, CHAT_SCOPE, gate_copy
from planning import Cooldown, public_gate, run_chat
from safety import INPUT_LIMITS, chat_request_action
from ui.components import WEEKLY_MODULES, render_check_in_ring, render_shield, render_summary

COOLDOWN_MESSAGE = "Please wait five seconds between Gemini requests."
VERDICTS = {"passed": "Passed", "regenerated": "Regenerated", "fallback": "Fallback"}
CHAT_LIMIT = 10


def safety_badge(verdict):
    st.html(f'<p class="cb-safety-badge cb-enter" data-outcome="{verdict}">Safety check · {VERDICTS[verdict]}</p>')


def local_today():
    try:
        zone = ZoneInfo(st.context.timezone or "Europe/London")
    except ZoneInfoNotFoundError:
        zone = timezone.utc
    return datetime.now(zone).date()


def current_entries():
    return recent_checkins(st.session_state.get("cb_checkins", {}), local_today())


def _save_checkin():
    state = st.session_state
    entries = current_entries()
    previous = entries.get(state.cb_checkin_date)
    soreness = max(state.cb_soreness, previous.soreness) if previous else state.cb_soreness
    effort = max(state.cb_effort, previous.effort) if previous else state.cb_effort
    entries[state.cb_checkin_date] = CheckIn(soreness, effort, state.cb_day_type == "Rest day")
    state.cb_checkins = entries
    state.cb_checkin_saved = True
    state.pop("cb_outcome", None)
    state.pop("cb_chat", None)


def _celebrate():
    st.iframe("""<!doctype html><html lang="en"><meta charset="utf-8">
      <meta name="referrer" content="no-referrer"><body style="margin:0">
      <script src="https://cdn.jsdelivr.net/npm/canvas-confetti@1.9.4/dist/confetti.browser.min.js" referrerpolicy="no-referrer"></script>
      <script>
      if (typeof confetti === 'function' && !matchMedia('(prefers-reduced-motion: reduce)').matches) {
          confetti({particleCount: 28, ticks: 25, spread: 75, startVelocity: 13,
                    disableForReducedMotion: true, origin: {x: 0.5, y: 0.8}});
      }
      </script></body></html>""", height=90, tab_index=-1)


def render_checkins(profile, locale, reduce_motion):
    st.subheader("Daily check-ins")
    today = local_today()
    entries = current_entries()
    with st.form("cb_checkin_form"):
        st.date_input("Check-in date", today, min_value=today - timedelta(days=6),
                      max_value=today, key="cb_checkin_date")
        st.selectbox("Day type", ["Rest day", "Practice day"], key="cb_day_type")
        st.slider("Soreness", 1, 5, 1, key="cb_soreness")
        st.slider("Effort (RPE)", 1, 10, 1, key="cb_effort")
        st.caption("Repeat entries keep the highest soreness and effort recorded for that day.")
        st.form_submit_button("Save check-in", on_click=_save_checkin)
    saved = st.session_state.pop("cb_checkin_saved", False)
    if saved:
        st.success("Check-in saved for this session.")
    render_check_in_ring(len(entries))
    if entries:
        rest_days = sum(entry.rest_day for entry in entries.values())
        st.caption(f"{rest_days} rest-day entries · {len(entries) - rest_days} practice-day entries")
        st.caption("Rest and practice days count equally toward checking in consistently.")
    rule = checkin_rule(entries)
    if rule:
        st.session_state.cb_training_paused = True
        render_shield(*gate_copy(locale, rule))
    if 3 <= len(entries) < 7:
        st.success("Consistency badge · Three daily check-ins")
    if len(entries) == 7:
        st.success("Consistency badge · Seven daily check-ins")
        if saved and not st.session_state.get("cb_celebrated") and not st.session_state.get("cb_training_paused"):
            st.session_state.cb_celebrated = True
            if not reduce_motion and not public_gate(profile, "Full-body training", entries):
                _celebrate()


def render_preparation(reduce_motion):
    st.subheader("Hydration planner")
    with st.form("cb_hydration"):
        start = st.time_input("Practice start time", time(16, 0))
        duration = st.number_input("Practice duration (minutes)", min_value=1, max_value=360, value=60)
        submitted = st.form_submit_button("Show water reminders")
    if submitted and start is not None:
        st.session_state.cb_hydration_schedule = hydration_schedule(start, duration)
    for label, clock in st.session_state.get("cb_hydration_schedule", []):
        st.text(f"{label} · {clock}")
    if st.session_state.get("cb_hydration_schedule"):
        st.caption("Agree water breaks with your coach.")
    st.subheader("Pre-match breathing")
    document = Path(__file__).with_name("breathing.html").read_text(encoding="utf-8")
    st.iframe(document.replace("__REDUCE_MOTION__", str(reduce_motion).lower()), height=310)


def _chat_message(answer, verdict=None, stream=False):
    with st.chat_message("assistant"):
        if verdict:
            safety_badge(verdict)
        render_summary(answer, stream)


def render_chat(profile, locale, entries, key, model, reduce_motion):
    st.subheader("Coach chat")
    st.caption(f"Ask about {profile.sport} decisions or match preparation. Keep questions general and leave out personal details.")
    if st.session_state.cb_step < 3:
        st.info("Complete the athlete safety step to start chatting.")
        return
    rule = public_gate(profile, "Tactical coaching", entries)
    if rule:
        st.session_state.cb_training_paused = True
        render_shield(*gate_copy(locale, rule))
        return
    history = st.session_state.setdefault("cb_chat", [])
    log = st.container(key="cb_chat_log")
    with log:
        for question, verdict, answer in history:
            with st.chat_message("user"):
                st.text(question)
            _chat_message(answer, verdict)
    turns = st.session_state.get("cb_chat_turns", 0)
    limit = turns >= CHAT_LIMIT
    question = st.chat_input("Ask about your sport", disabled=limit, max_chars=INPUT_LIMITS["chat"])
    if limit:
        st.info("This session has reached the ten-turn chat limit.")
        return
    if not question or not question.strip():
        return
    action = chat_request_action(question, profile, any(entry[1] for entry in history))
    question = question.strip()
    if action == "block":
        st.info(f"Shorten your question to {INPUT_LIMITS['chat']} characters or fewer.")
        return
    if action == "refuse":
        question, verdict, answer = "Question withheld", None, CHAT_REFUSAL[locale]
    elif action == "redirect":
        question, verdict, answer = "Question withheld", None, CHAT_SCOPE[locale]
    else:
        try:
            verdict, answer = run_chat(profile, locale, question, history, key, model)
        except Cooldown:
            st.info(COOLDOWN_MESSAGE)
            return
        except Exception:
            st.error("Coach chat is unavailable. Try again in a moment.")
            return
    history.append((question, verdict, answer))
    st.session_state.cb_chat_turns = turns + 1
    with log:
        with st.chat_message("user"):
            st.text(question)
        _chat_message(answer, verdict, stream=bool(verdict) and not reduce_motion)
    if turns + 1 == CHAT_LIMIT:
        st.info("This session has reached the ten-turn chat limit.")


def render_exports(plan, feature, demo, locale):
    rows = plan["rows"]
    if feature in WEEKLY_MODULES:
        start = st.date_input("Calendar start date", local_today(), key="cb_calendar_start")
        st.download_button("Download calendar", calendar_plan(
            rows, start, datetime.now(timezone.utc), repr((feature, rows))
        ), "coachbot-plan.ics", "text/calendar", on_click="ignore")
    with st.container(horizontal=True):
        st.download_button("Download CSV", csv_plan(rows), "coachbot-plan.csv", "text/csv", on_click="ignore")
        st.download_button("Printable HTML", printable_plan(plan, feature, demo, locale),
                           "coachbot-plan.html", "text/html", on_click="ignore")
