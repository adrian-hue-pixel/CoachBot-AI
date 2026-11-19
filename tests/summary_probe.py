"""Streamlit browser fixture with a deliberately long intermediate frame."""

from time import sleep

import streamlit as st

from ui import components
from ui.theme import inject_css

SUMMARY = "Summary fixture text is complete."


def frames(_summary):
    yield "Summary fixture "
    sleep(1.5)
    yield "text is complete."
    sleep(0.8)


inject_css()
reduced = st.toggle("Reduce motion")
st.html('<span hidden data-cb-motion="reduced"></span>' if reduced else '<span hidden></span>')
if st.button("Show summary"):
    components._stream_plain_summary = frames
    with st.container(key="cb_summary_probe"):
        components.render_summary(SUMMARY, not reduced)
