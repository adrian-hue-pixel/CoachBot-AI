"""Accessible hero, wizard progress, and coaching plan displays."""

from html import escape
import re
from string import punctuation
from time import sleep

import plotly.graph_objects as go
import streamlit as st

from checkins import LOADS

from ui.field import SPORT_STYLES, field_svg

WEEKLY_MODULES = {
    "Full-body training", "Return-to-sport schedule", "Weekly nutrition ideas",
    "No-equipment training", "Weekly progress adaptation",
}
LOAD_LEVELS = {"Rest": "rest", "Light": "light", "Moderate": "moderate"}
FOOD_GROUPS = {"carbs": "Carbs", "protein": "Protein", "fats": "Fats"}
MARKDOWN_LITERAL = str.maketrans({char: f"&#{ord(char)};" for char in punctuation})


def render_brand():
    st.html('<div class="cb-brand"><span aria-hidden="true">🏅</span><strong>CoachBot AI</strong></div>')


def render_header(sport, position, reduce_motion, page, icon, description):
    motion = "reduced" if reduce_motion else "full"
    attributes = f'data-cb-sport="{SPORT_STYLES[sport]}" data-cb-motion="{motion}"'
    header = f"""
    <header class="cb-pagehead" {attributes}>
        <div class="cb-page-title">
            <span class="cb-icon material-symbols-rounded" aria-hidden="true">{escape(icon)}</span>
            <div><span class="cb-eyebrow">CoachBot AI</span>
                <h1>{escape(page)}</h1><p>{escape(description)}</p>
                <p class="cb-page-note">Review your plan with a coach or trusted adult. For pain or injury, ask a clinician.</p>
            </div>
        </div>
        <figure class="cb-field">
            {field_svg(sport, position)}
            <figcaption><span>{escape(sport)}</span><strong>{escape(position)}</strong></figcaption>
        </figure>
    </header>
    """
    # The HTML widget strips SVG; this markup uses escaped labels and fixed SVG paths.
    st.markdown(" ".join(header.split()), unsafe_allow_html=True)


def render_tool_card(title, icon, description):
    st.html(f"""
        <span class="cb-icon material-symbols-rounded" aria-hidden="true">{escape(icon)}</span>
        <h3>{escape(title)}</h3><p>{escape(description)}</p>
    """)


def render_stepper(steps, current, previous):
    items = []
    for index, name in enumerate(steps):
        state = ' aria-current="step"' if index == current else ' class="cb-step-done"' if index < current else ""
        items.append(f'<li{state}><span aria-hidden="true">{index + 1:02d}</span>{escape(name)}</li>')
    st.html(f"""
    <ol class="cb-stepper" role="list" aria-label="Athlete profile steps"
        style="--cb-step-from:{previous * 100}%;--cb-step-to:{current * 100}%">
        {"".join(items)}
    </ol>
    """)


def render_plan_preview(profile, feature):
    """Show the current profile choices before a plan has been generated."""
    details = (("Sport", profile.sport), ("Position", profile.position), ("Module", feature))
    rows = "".join(f"<div><dt>{label}</dt><dd>{escape(value)}</dd></div>" for label, value in details)
    st.html(f"""
    <div class="cb-plan-preview">
        <div class="cb-preview-heading"><span aria-hidden="true">◎</span><h3>Your plan will appear here</h3></div>
        <p>Finish your athlete profile to generate a plan for these choices.</p>
        <dl>{rows}</dl>
    </div>
    """)


def _count_up(count):
    if count == 0:
        return '<span aria-hidden="true">0</span>'
    numbers = "".join(f"<span>{number}</span>" for number in range(count, -1, -1))
    return f"""
      <span class="cb-count" aria-hidden="true">
        <span class="cb-count-reel" style="--cb-count:{count}">{numbers}</span>
      </span>
    """


def render_check_in_ring(completed, total=7):
    remaining_stroke = 100 * (total - completed) / total
    st.html(f"""
    <div class="cb-check-in cb-enter">
      <svg viewBox="0 0 48 48" role="img" aria-label="{completed} of {total} weekly check-ins complete">
        <circle class="cb-ring-track" cx="24" cy="24" r="19"/>
        <circle class="cb-ring-value" cx="24" cy="24" r="19" pathLength="100"
                style="--cb-ring-offset:{remaining_stroke:.2f}" transform="rotate(-90 24 24)"/>
      </svg>
      <div><strong>{_count_up(completed)}<span aria-hidden="true"> / {total}</span></strong>
           <span class="cb-check-in-caption">Weekly check-ins</span></div>
    </div>
    """)


def render_skeleton():
    st.html("""
    <div class="cb-skeleton" aria-hidden="true">
      <span></span><span></span><span></span>
    </div>
    """)


def render_shield(title, rule_label, reason):
    st.html(f"""
    <section class="cb-shield cb-enter" role="alert">
      <svg viewBox="0 0 48 48" role="img" aria-label="Safety shield">
        <path class="cb-shield-outline" pathLength="100" d="M24 4 42 11v11c0 10-8 17-18 22C14 39 6 32 6 22V11z"/>
        <path d="M24 15v10m0 6v1"/>
      </svg>
      <div><h3>{escape(title)}</h3><p><strong>{escape(rule_label)}</strong></p><p>{escape(reason)}</p></div>
    </section>
    """)


def validate_plan(plan):
    if (
        not isinstance(plan, dict)
        or not all(isinstance(plan.get(key), str) for key in ("summary", "review"))
        or not isinstance(plan.get("rows"), list)
        or not 1 <= len(plan["rows"]) <= 7
        or any(
            not isinstance(row, dict) or not all(isinstance(row.get(key), str) for key in ("when", "action", "why"))
            for row in plan["rows"]
        )
    ):
        raise ValueError("Gemini returned an incomplete plan.")
    rows = []
    for original in plan["rows"]:
        row = {key: value for key, value in original.items()
               if key in ("when", "action", "why", *FOOD_GROUPS) and isinstance(value, str)}
        load = original.get("load")
        if isinstance(load, str) and load in LOADS:
            row["load"] = load
        rows.append(row)
    return {"summary": plan["summary"], "review": plan["review"], "rows": rows}


def _stream_plain_summary(summary):
    chunks = re.findall(r"\s+|\S+\s*", summary)
    size = max(1, (len(chunks) + 11) // 12)
    for offset in range(0, len(chunks), size):
        yield "".join(chunks[offset:offset + size]).translate(MARKDOWN_LITERAL)
        if offset + size < len(chunks):
            sleep(0.025)


def render_summary(summary, stream):
    plain = f'<p class="cb-summary">{escape(summary)}</p>'
    slot = st.empty()
    if stream:
        with slot.container():
            with st.container(key="cb_summary_live"):
                st.html(plain.replace('class="cb-summary"', 'class="cb-summary cb-summary-motion-copy"'))
                with st.container(key="cb_summary_stream"):
                    st.write_stream(_stream_plain_summary(summary))
    slot.html(plain)


def _plan_card(row, index, show_load):
    if row is None:
        contents = f'<h3>Day slot {index + 1}</h3><p class="cb-muted">Unfilled day</p>'
        return f'<li class="cb-day cb-day-empty cb-enter" style="--cb-index:{index}">{contents}</li>'

    load = row.get("load")
    level = LOAD_LEVELS.get(load) if isinstance(load, str) else None
    badge, bar = "", ""
    if level:
        badge = f'<span class="cb-load cb-load-{level}">{escape(load)}</span>'
        bar = f'<div class="cb-load-track cb-load-{level}" aria-hidden="true"><span></span></div>'
    elif show_load:
        badge = '<span class="cb-load cb-load-unspecified">Load unspecified</span>'

    foods = "".join(
        f'<span><strong>{label}</strong> {escape(row[key])}</span>'
        for key, label in FOOD_GROUPS.items() if isinstance(row.get(key), str) and row[key].strip()
    )
    foods = f'<div class="cb-foods">{foods}</div>' if foods else ""
    explanation = "Coaching cue" if "exercise_id" in row else "Why this is included"
    return f"""
    <li class="cb-day cb-enter" style="--cb-index:{index}">
      <div class="cb-day-title"><h3>{escape(row["when"])}</h3>{badge}</div>
      {bar}<p>{escape(row["action"])}</p>{foods}
      <details><summary>{explanation}</summary><p>{escape(row["why"])}</p></details>
    </li>
    """


def render_plan(result, feature, *, stream=False, reduce_motion=False):
    rows = result["rows"]
    render_summary(result["summary"], stream and not reduce_motion)
    slots = rows + [None] * (7 - len(rows)) if feature in WEEKLY_MODULES else rows
    show_load = feature in WEEKLY_MODULES and feature != "Weekly nutrition ideas"
    cards = "".join(_plan_card(row, index, show_load) for index, row in enumerate(slots))
    count = len(rows)
    filled = "day filled" if count == 1 else "days filled"
    metric = (
        f'<span class="cb-plan-count"><span class="cb-sr-only">{count} of 7 days filled</span>'
        f'{_count_up(count)}<span aria-hidden="true"> / 7 {filled}</span></span>'
    )
    if feature not in WEEKLY_MODULES:
        metric = ""
    label = "Weekly timeline" if feature in WEEKLY_MODULES else "Plan steps"
    st.html(f"""
    <section class="cb-plan">
      <div class="cb-plan-title"><h3>{label}</h3>{metric}</div>
      <ol class="cb-timeline" role="list" aria-label="{label}">{cards}</ol>
    </section>
    """)
    if feature == "Weekly nutrition ideas":
        render_nutrition_chart(rows, reduce_motion)
    st.html(f'<p class="cb-review">{escape(result["review"])}</p>')


def render_nutrition_chart(rows, reduce_motion):
    counts = [
        sum(isinstance(row.get(key), str) and bool(row[key].strip()) for row in rows)
        for key in FOOD_GROUPS
    ]
    figure = go.Figure(go.Bar(x=list(FOOD_GROUPS.values()), y=counts, marker_color="#57D69A"))
    figure.update_layout(
        title="Macronutrient food sources",
        xaxis_title="Macronutrient",
        yaxis_title="Plan rows with a food source",
        transition=dict(duration=0 if reduce_motion else 500, easing="cubic-in-out"),
        margin=dict(l=16, r=16, t=56, b=40),
        height=310,
    )
    figure.update_yaxes(range=[0, len(rows) + 0.5], dtick=1, automargin=True)
    st.plotly_chart(figure, width="stretch", config={"displayModeBar": False})
    st.caption("Counts show food sources listed in the plan.")
