"""Cinematic introduction for the CoachBot home page."""

from base64 import b64encode
from functools import cache
from pathlib import Path

import streamlit as st

from ui.field import SPORT_STYLES


@cache
def _arena_image():
    asset = Path(__file__).with_name("assets") / "arena.webp"
    return b64encode(asset.read_bytes()).decode("ascii")


def render_home_hero(sport, reduce_motion):
    motion = "reduced" if reduce_motion else "full"
    attributes = f'data-cb-sport="{SPORT_STYLES[sport]}" data-cb-motion="{motion}"'
    st.html(f"""
    <section class="cb-hero" {attributes}>
        <img class="cb-hero-pitch" alt="" src="data:image/webp;base64,{_arena_image()}">
        <div class="cb-arena-effects" aria-hidden="true">
            <i class="cb-arena-beam"></i><i class="cb-arena-beam"></i>
            <i class="cb-arena-grain"></i><i class="cb-arena-sparks"></i>
        </div>
        <div class="cb-arena-turf" aria-hidden="true"></div>
        <div class="cb-hero-meta">
            <span class="cb-eyebrow"><span aria-hidden="true">🏅</span> CoachBot AI</span>
            <ul class="cb-chips" aria-label="Supported sports">
                <li>Football</li><li>Cricket</li><li>Basketball</li>
            </ul>
        </div>
        <div class="cb-hero-copy">
            <h1><span class="cb-hero-lead">Training plans</span>
                <span class="cb-hero-accent">for the way you play.</span></h1>
            <p class="cb-hero-note">Review your plan with a coach or trusted adult. For pain or injury, ask a clinician.</p>
        </div>
    </section>
    """)
