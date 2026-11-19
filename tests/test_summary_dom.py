"""Browser checks for one exposed plan summary per frame."""

import os

import pytest

from browser_server import server
FULL = "Summary fixture text is complete."
PREFIX = "Summary fixture"
pytestmark = pytest.mark.skipif(
    os.getenv("COACHBOT_BROWSER_TEST") != "1", reason="browser test runs in the Python 3.12 CI job"
)
EXPOSED = """
(text) => [...document.querySelectorAll('.st-key-cb_summary_probe p')].filter(node => {
    if (!(node.textContent || '').includes(text) || node.closest('[aria-hidden="true"], [hidden]')) return false;
    for (let parent = node; parent; parent = parent.parentElement) {
        const style = getComputedStyle(parent);
        if (style.display === 'none' || ['hidden', 'collapse'].includes(style.visibility)) return false;
    }
    return node.getClientRects().length > 0;
}).length
"""




def test_one_visible_and_accessible_summary(tmp_path):
    from playwright.sync_api import expect, sync_playwright

    with server(tmp_path, "tests/summary_probe.py") as url, sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 360, "height": 800})
        page.goto(url)
        page.get_by_role("button", name="Show summary").click()
        stream = page.locator(".st-key-cb_summary_stream p")
        expect(stream).to_have_text(PREFIX)
        assert page.evaluate(EXPOSED, PREFIX) == 1
        assert page.locator(".st-key-cb_summary_probe").aria_snapshot().count(PREFIX) == 1
        expect(stream).to_have_text(FULL)
        assert page.evaluate(EXPOSED, FULL) == 1
        expect(stream).to_have_count(0)
        assert page.evaluate(EXPOSED, FULL) == 1
        assert page.locator(".st-key-cb_summary_probe").aria_snapshot().count(FULL) == 1

        page.get_by_text("Reduce motion", exact=True).click()
        page.get_by_role("button", name="Show summary").click()
        expect(page.get_by_text(FULL, exact=True)).to_be_visible()
        expect(stream).to_have_count(0)
        assert page.evaluate(EXPOSED, FULL) == 1
        assert page.locator(".st-key-cb_summary_probe").aria_snapshot().count(FULL) == 1

        page.emulate_media(reduced_motion="reduce")
        page.get_by_text("Reduce motion", exact=True).click()
        page.get_by_role("button", name="Show summary").click()
        expect(stream).to_have_text(PREFIX)
        assert page.evaluate(EXPOSED, FULL) == 1
        assert page.locator(".st-key-cb_summary_probe").aria_snapshot().count(FULL) == 1
        expect(stream).to_have_count(0)
        assert page.evaluate(EXPOSED, FULL) == 1
        browser.close()
