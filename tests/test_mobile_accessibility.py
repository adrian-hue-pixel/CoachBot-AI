"""Released app reflow, keyboard order, labels, and contrast checks."""

from pathlib import Path
import os
import re

import pytest

from browser_server import server

CSS = Path(__file__).resolve().parents[1] / "ui" / "theme.css"


def contrast(first, second):
    def luminance(rgb):
        linear = [x / 12.92 if x <= .04045 else ((x + .055) / 1.055) ** 2.4
                  for x in (value / 255 for value in rgb)]
        return sum(x * w for x, w in zip(linear, (.2126, .7152, .0722), strict=True))

    a, b = sorted((luminance(first), luminance(second)), reverse=True)
    return (a + .05) / (b + .05)


def _hex(value):
    return tuple(bytes.fromhex(value.lstrip("#")))


def test_dark_palette_contrast():
    text = CSS.read_text(encoding="utf-8")
    tokens = dict(re.findall(r"--cb-([\w-]+):\s*(#[0-9a-fA-F]{6})\b", text))
    for foreground, background in (
        ("ink", tokens["bg"]), ("muted", "#101C17"), ("ink", "#121D18"),
        ("football", "#101C17"), ("cricket", "#101C17"), ("basketball", "#101C17"),
        ("accent", "#151C1A"),
    ):
        assert contrast(_hex(tokens[foreground]), _hex(background)) >= 4.5
    assert contrast(_hex("#FFFFFF"), _hex(tokens["primary"])) >= 4.5
    assert contrast(_hex("#B8E9D1"), _hex("#20362A")) >= 4.5
    assert contrast(_hex("#FFDA93"), _hex("#382F1F")) >= 4.5
    assert contrast(_hex("#FFEDB9"), _hex("#584823")) >= 4.5


OVERFLOW = """
() => [document.documentElement, document.body,
       document.querySelector('[data-testid="stMain"]'),
       document.querySelector('[data-testid="stMainBlockContainer"]'),
       ...document.querySelectorAll('[role="tabpanel"]:not([hidden])')]
    .filter(el => el && el.clientWidth && getComputedStyle(el).display !== 'none')
    .map(el => ({name: el.dataset.testid || el.getAttribute('role') || el.tagName,
                 overflow: el.scrollWidth - el.clientWidth}))
    .filter(result => result.overflow > 1)
"""

COMPUTED_COLORS = r"""
(el) => {
    const rgb = value => (value.match(/[\d.]+/g) || []).map(Number);
    let bg = [255, 255, 255];
    const backgrounds = [];
    for (let node = el; node; node = node.parentElement) {
        const color = rgb(getComputedStyle(node).backgroundColor);
        if (color.length >= 3) backgrounds.push(color);
    }
    for (const color of backgrounds.reverse()) {
        const alpha = color.length === 4 ? color[3] : 1;
        bg = bg.map((value, i) => color[i] * alpha + value * (1 - alpha));
    }
    const style = getComputedStyle(el);
    const text = rgb(style.color);
    const alpha = text.length === 4 ? text[3] : 1;
    return {text: bg.map((value, i) => text[i] * alpha + value * (1 - alpha)), bg,
            outline: rgb(style.outlineColor).slice(0, 3), width: parseFloat(style.outlineWidth),
            outlineStyle: style.outlineStyle};
}
"""


@pytest.mark.skipif(os.getenv("COACHBOT_BROWSER_TEST") != "1", reason="browser test runs in the Python 3.12 CI job")
def test_mobile_wizard_and_tab_accessibility(tmp_path):
    from playwright.sync_api import expect, sync_playwright

    with server(tmp_path, "app.py") as url, sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 360, "height": 800}, reduced_motion="reduce")
        page.goto(url)
        expect(page.get_by_role("heading", name="CoachBot AI")).to_be_visible()
        assert page.evaluate("innerWidth") == 360
        wizard = page.locator(".st-key-cb_wizard")
        continue_button = wizard.get_by_role("button", name="Continue")

        for target in (page.locator(".cb-hero-note"), page.locator(".cb-hero h1 span"), continue_button):
            colors = target.evaluate(COMPUTED_COLORS)
            assert contrast(colors["text"], colors["bg"]) >= 4.5

        focus_order = [wizard.get_by_role("combobox", name=name, exact=True)
                       for name in ("Sport", "Position", "Coaching module")]
        focus_order.append(continue_button)
        focus_order[0].focus()
        for index, target in enumerate(focus_order):
            expect(target).to_be_focused()
            colors = target.evaluate(COMPUTED_COLORS)
            assert colors["outlineStyle"] != "none" and colors["width"] >= 1
            assert contrast(colors["outline"], colors["bg"]) >= 3
            if index < len(focus_order) - 1:
                page.keyboard.press("Tab")

        steps = [
            ("Sport & position", (("combobox", "Sport"), ("combobox", "Position"), ("combobox", "Coaching module"))),
            ("Goal & equipment", (("textbox", "Goal or skill"), ("combobox", "Equipment"), ("combobox", "Preferred intensity"))),
            ("Safety check-in", (("spinbutton", "Age"), ("combobox", "Injury status"),
                                  ("textbox", "Clinician instructions or movements to avoid"), ("combobox", "This week"))),
            ("Diet & language", (("combobox", "Diet"), ("textbox", "Food allergies (leave blank if none)"),
                                  ("combobox", "Plan language"))),
        ]
        for index, (title, fields) in enumerate(steps):
            expect(wizard.locator('[aria-current="step"]')).to_contain_text(title)
            for role, name in fields:
                expect(wizard.get_by_role(role, name=name, exact=True)).to_be_visible()
            assert not (problems := page.evaluate(OVERFLOW)), (title, problems)
            if index < len(steps) - 1:
                continue_button.click()

        wizard.get_by_role("button", name="Generate coaching plan").click()
        expect(page.get_by_role("heading", name="Weekly timeline")).to_be_visible()
        assert not (problems := page.evaluate(OVERFLOW)), problems

        for tab_name, heading in (
            ("Check-ins", "Daily check-ins"), ("Match prep", "Hydration planner"),
            ("Coach chat", "Coach chat"), ("Prompt Lab", "Prompt Lab"), ("Plan", "Athlete profile"),
        ):
            tab = page.get_by_role("tab", name=tab_name, exact=True)
            tab.click()
            expect(tab).to_have_attribute("aria-selected", "true")
            expect(page.get_by_role("heading", name=heading, exact=True)).to_be_visible()
            assert not (problems := page.evaluate(OVERFLOW)), (tab_name, problems)
        browser.close()
