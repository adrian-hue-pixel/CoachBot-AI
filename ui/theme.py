"""Inject the shared CoachBot stylesheet once per app render."""

from pathlib import Path

import streamlit as st


def inject_css():
    st.html(Path(__file__).with_suffix(".css"))
