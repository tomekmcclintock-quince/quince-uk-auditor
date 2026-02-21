import os
import hashlib
from typing import Dict, Tuple

from playwright.sync_api import sync_playwright

VIEWPORT = {"width": 1440, "height": 900}


def sha8(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:8]


def safe_mkdir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _click_first(page, selectors, timeout_ms: int = 2500) -> bool:
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
    page.screenshot(path=path, full_page=False)


def dismiss_overlays(page) -> None:
    """Best-effort dismiss for email capture / cookie / modal overlays."""
    try:
        for _ in range(3):
            dismissed = False

            dismissed |= _click_first(
                page,
                selectors=[
                    "[role='dialog'] button[aria-label='Close']",
                    "[role='dialog'] [aria-label='Close']",
                    "[role='dialog'] button:has-text('Close')",
                    "[role='dialog'] button:has-text('No Thanks')",
                    "[role='dialog'] button:has-text('No thanks')",
                    "[role='dialog'] button:has-text('Not now')",
                    ".modal button[aria-label='Close']",
                    ".modal [aria-label='Close']",
                    "button[aria-label='Close']",
                    "[aria-label='Close']",
                    "button[title='Close']",
                    "[title='Close']",
                ],
            )

            dismissed |= _click_first(
                page,
                selectors=[
                    "button:has-text('No thanks')",
                    "button:has-text('No Thanks')",
                    "button:has-text('Not now')",
                    "button:has-text('Reject all')",
                    "button:has-text('Reject All')",
                    "button:has-text('Decline')",
                    "button:has-text('Got it')",
                    "button:has-text('Accept')",
                    "button:has-text('Accept all')",
                    "button:has-text('Accept All')",
                ],
            )

            try:
                page.keyboard.press("Escape")
            except Exception:
                pass

            try:
                page.wait_for_timeout(250)
            except Exception:
                pass

            if dismissed:
                continue

            break
    except Exception:
        return


def _scroll_to_section_and_expand(page, section_name: str) -> bool:
    """
    Scroll to a section reliably and expand it if it's an accordion.
    Returns True if an anchor was found.
    """
    # Try common accordion trigger patterns first.
    selectors = [
        f"button:has-text('{section_name}')",
        f"summary:has-text('{section_name}')",
        f"[role='button']:has-text('{section_name}')",
        f"text=/^{section_name}$/i",
    ]

    # Find a locator we can scroll to
    for sel in selectors:
        try:
            loc = page.locator(sel).first
            if loc.count() == 0:
                continue
            loc.scroll_into_view_if_needed(timeout=6000)
            # Click to expand (safe even if not accordion)
            try:
                loc.click(timeout=2000)
            except Exception:
                pass
            try:
                page.wait_for_timeout(250)
            except Exception:
                pass
            return True
        except Exception:
            continue

    # Fallback: search for the text anywhere and scroll there
    try:
        loc = page.locator(f"text=/{section_name}/i").first
        if loc.count() > 0:
            loc.scroll_into_view_if_needed(timeout=6000)
            try:
                loc.click(timeout=2000)
            except Exception:
                pass
            return True
    except Exception:
        pass

    return False


def capture_pdp(url: str, out_root: str = "out") -> Tuple[str, Dict]:
    run_id = sha8(url)
    out_dir = os.path.join(out_root, run_id)
    shots_dir = os.path.join(out_dir, "screenshots")
    safe_mkdir(shots_dir)

    paths = {
        "full_page": os.path.join(shots_dir, "01_full_page.png"),
        "care_view": os.path.join(shots_dir, "02_care_view.png"),
        "size_fit_view": os.path.join(shots_dir, "03_size_fit_view.png"),
        "size_chart_view": os.path.join(shots_dir, "04_size_chart_view.png"),
    }

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport=VIEWPORT, locale="en-GB")
        page = context.new_page()

        page.goto(url, wait_until="networkidle", timeout=90_000)
        dismiss_overlays(page)

        # Expand "Show more / Read more" before baseline screenshot
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

        # Expand Details accordion if present (but we won't capture a separate details screenshot)
        _click_first(
            page,
            selectors=[
                "button:has-text('Details')",
                "summary:has-text('Details')",
                "[role='button']:has-text('Details')",
                "text=/^details$/i",
            ],
        )

        dismiss_overlays(page)
        try:
            page.wait_for_timeout(350)
        except Exception:
            pass

        # Baseline full-page screenshot (Details expanded if possible)
        page.screenshot(path=paths["full_page"], full_page=True)

        # Visible text excerpt
        try:
            visible_text = page.inner_text("body")
        except Exception:
            visible_text = ""
        visible_text = (visible_text or "").strip()[:12000]

        # --- Care (scroll + viewport screenshot) ---
        dismiss_overlays(page)
        found_care = _scroll_to_section_and_expand(page, "Care")
        dismiss_overlays(page)
        if not found_care:
            # fallback scroll down ~1.5 screens
            try:
                page.mouse.wheel(0, int(VIEWPORT["height"] * 1.5))
            except Exception:
                pass
        _shot_viewport(page, paths["care_view"])

        # --- Size & Fit (scroll + viewport screenshot) ---
        dismiss_overlays(page)
        # Some pages use "Size & Fit", others "Size and Fit"
        found_size_fit = (
            _scroll_to_section_and_expand(page, "Size & Fit")
            or _scroll_to_section_and_expand(page, "Size and Fit")
            or _scroll_to_section_and_expand(page, "Fit")
        )
        dismiss_overlays(page)
        if not found_size_fit:
            # fallback: don't move far; it might not exist for this product
            pass
        _shot_viewport(page, paths["size_fit_view"])

        # --- Size Chart modal (top of page) ---
        try:
            page.evaluate("window.scrollTo(0, 0)")
        except Exception:
            pass
        dismiss_overlays(page)

        opened = _click_first(
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

        if opened:
            try:
                page.wait_for_timeout(600)
            except Exception:
                pass
            dismiss_overlays(page)

            # Prefer a modal/dialog screenshot if present
            dialog = page.locator("[role='dialog'], [aria-modal='true'], .modal, .Modal").first
            if dialog.count() > 0:
                try:
                    dialog.screenshot(path=paths["size_chart_view"])
                except Exception:
                    _shot_viewport(page, paths["size_chart_view"])
            else:
                _shot_viewport(page, paths["size_chart_view"])
        else:
            # If no size chart, capture top viewport as evidence
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