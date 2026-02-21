import os
import hashlib
from typing import Dict, Tuple

from playwright.sync_api import sync_playwright

VIEWPORT = {"width": 1440, "height": 900}


def sha8(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:8]


def safe_mkdir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _click_first(page, selectors, timeout_ms: int = 4000) -> bool:
    """Try a list of selectors; click the first that appears/can be clicked."""
    for sel in selectors:
        try:
            loc = page.locator(sel).first
            if loc.count() == 0:
                continue
            loc.scroll_into_view_if_needed(timeout=timeout_ms)
            loc.click(timeout=timeout_ms)
            return True
        except Exception:
            continue
    return False


def _shot_viewport(page, path: str) -> None:
    """Viewport-only screenshot (no full_page) to keep PDFs compact."""
    page.screenshot(path=path, full_page=False)


def capture_pdp(url: str, out_root: str = "out") -> Tuple[str, Dict]:
    run_id = sha8(url)
    out_dir = os.path.join(out_root, run_id)
    shots_dir = os.path.join(out_dir, "screenshots")
    safe_mkdir(shots_dir)

    paths = {
        "full_page": os.path.join(shots_dir, "01_full_page.png"),
        "care_view": os.path.join(shots_dir, "02_care_view.png"),
        "size_chart_view": os.path.join(shots_dir, "03_size_chart_view.png"),
    }

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport=VIEWPORT, locale="en-GB")
        page = context.new_page()

        page.goto(url, wait_until="networkidle", timeout=90_000)

        # -------- Ensure Details is expanded BEFORE baseline full-page screenshot --------
        # Try common "Show more / Read more" patterns first
        _click_first(
            page,
            selectors=[
                "button:has-text('Show more')",
                "button:has-text('Show More')",
                "button:has-text('Read more')",
                "button:has-text('Read More')",
                "text=/show more/i",
                "text=/read more/i",
                "text=/more details/i",
            ],
        )

        # Some PDPs use an accordion for Details — click it too (idempotent if already open)
        _click_first(
            page,
            selectors=[
                "button:has-text('Details')",
                "text=/^details$/i",
                "[aria-controls*='details']",
                "[data-testid*='details']",
            ],
        )

        # Give UI a beat to reflow after expansion
        try:
            page.wait_for_timeout(400)
        except Exception:
            pass

        # Baseline: full page screenshot (now includes expanded Details where possible)
        page.screenshot(path=paths["full_page"], full_page=True)

        # Visible text for analysis/debugging (capped)
        try:
            visible_text = page.inner_text("body")
        except Exception:
            visible_text = ""
        visible_text = (visible_text or "").strip()[:12000]

        # -------- Care view: scroll to a reliable anchor --------
        # Approach:
        # 1) Click the Care accordion/button (most reliable)
        # 2) Scroll to that exact element
        # 3) Take a viewport screenshot

        care_clicked = _click_first(
            page,
            selectors=[
                "button:has-text('Care')",
                "summary:has-text('Care')",
                "[role='button']:has-text('Care')",
                "[aria-controls*='care']",
                "text=/^care$/i",
            ],
        )

        # If we clicked something, re-find it and scroll precisely to it.
        # Even if click failed, try to locate a "Care" header and scroll to it.
        try:
            care_loc = page.locator(
                "button:has-text('Care'), summary:has-text('Care'), [role='button']:has-text('Care'), text=/^care$/i"
            ).first
            if care_loc.count() > 0:
                care_loc.scroll_into_view_if_needed(timeout=4000)
            else:
                # fallback: scroll ~1.5 viewports
                page.mouse.wheel(0, int(VIEWPORT["height"] * 1.5))
        except Exception:
            pass

        # Small pause for accordion animation
        if care_clicked:
            try:
                page.wait_for_timeout(300)
            except Exception:
                pass

        _shot_viewport(page, paths["care_view"])

        # -------- Size chart view: top-of-page modal or link --------
        # Usually near top; ensure top then open and screenshot viewport
        try:
            page.evaluate("window.scrollTo(0, 0)")
        except Exception:
            pass

        opened_size_chart = _click_first(
            page,
            selectors=[
                "a:has-text('Size Chart')",
                "button:has-text('Size Chart')",
                "text=/size chart/i",
                "a:has-text('Size Guide')",
                "button:has-text('Size Guide')",
                "text=/size guide/i",
            ],
        )

        if opened_size_chart:
            try:
                page.wait_for_timeout(600)  # allow modal animation
            except Exception:
                pass

        _shot_viewport(page, paths["size_chart_view"])

        browser.close()

    return run_id, {
        "url": url,
        "run_id": run_id,
        "out_dir": out_dir,
        "shots_dir": shots_dir,
        "paths": paths,
        "visible_text": visible_text,
    }