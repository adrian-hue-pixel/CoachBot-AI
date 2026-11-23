"""Load the shared photograph on CoachBot's tool pages."""

from base64 import b64encode
from functools import cache
from pathlib import Path

import streamlit as st


@cache
def _track_uri():
    asset = Path(__file__).with_name("assets") / "training-track.webp"
    return "data:image/webp;base64," + b64encode(asset.read_bytes()).decode("ascii")


def inject_tool_backdrop():
    st.html(f'<style>.stApp:has(.cb-pagehead){{--cb-tool-track:url("{_track_uri()}");}}</style>')
