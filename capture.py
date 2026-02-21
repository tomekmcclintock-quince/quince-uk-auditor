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


def dismiss_overlays(page) -> None:
    """
    Dismiss common overlays/popups:
    - Email capture modal (your $40 off modal)
    - Cookie banners
    - Generic dialogs
    Runs "best effort" and never raises.
    """
    try:
        # Try a few times; some overlays appear slightly after load.
        for _ in range(3):
            dismissed = False

            # 1) If there's a dialog/modal, try clicking an X/close button inside it.
            dismissed |= _click_first(
                page,
                selectors=[
                    # Common "X" close buttons within dialogs/modals
                    "[role='dialog'] button[aria-label='Close']",
                    "[role='dialog'] [aria-label='Close']",
                    "[role='dialog'] button:has-text('Close')",
                    "[role='dialog'] button:has-text('No Thanks')",
                    "[role='dialog'] button:has-text('No thanks')",
                    "[role='dialog'] button:has-text('Not now')",
                    "[role='dialog'] button:has-text('Dismiss')",
                    # Sometimes it's just a generic modal container
                    ".modal button[aria-label='Close']",
                    ".modal [aria-label='Close']",
                    ".modal button:has-text('Close')",
                    # Icon-only close buttons
                    "button[aria-label='Close']",
                    "[aria-label='Close']",
                    "button[title='Close']",
                    "[title='Close']",
                ],
            )

            # 2) Click common text CTAs that dismiss marketing popups / cookie prompts
            dismissed |= _click_first(
                page,
                selectors=[
                    "button:has-text('No thanks')",
                    "button:has-text('No Thanks')",
                    "button:has-text('Not now')",
                    "button:has-text('Continue without')",
                    "button:has-text('Reject all')",
                    "button:has-text('Reject All')",
                    "button:has-text('Decline')",
                    "button:has-text('Got it')",
                    "button:has-text('Accept')",
                    "button:has-text('Accept all')",
                    "button:has-text('Accept All')",
                ],
            )

            # 3) Press Escape (often closes the email capture modal)
            try:
                page.keyboard.press("Escape")
            except Exception:
                pass

            # Small wait for UI to update
            try:
                page.wait_for_timeout(250)
            except Exception:
                pass

            # If we clicked something, do one more loop to catch stacked overlays
            if dismissed:
                continue

            # 4) If a dialog still exists, last-resort: remove overlay layers
            # (This is safe for screenshot capture; it doesn't affect server state.)
            try:
                has_dialog = page.locator("[role='dialog']").count() > 0
            except Exception:
                has_dialog = False

            if has_dialog:
                try:
                    page.evaluate(
                        """
                        () => {
                          const selectors = [
                            '[role="dialog"]',
                            '[aria-modal="true"]',
                            '.modal',
                            '.Modal',
                            '.overlay',
                            '.Overlay',
                            '#attentive_overlay',
                            '#attentive_creative',
                            'iframe[title*="Attentive"]'
                          ];
                          for (const sel of selectors) {
                            document.querySelectorAll(sel).forEach(el => el.remove());
                          }
                        }
                        """
                    )
                except Exception:
                    pass

            # Done
            break
    except Exception:
        # Never block the run
        return


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

        # Important: dismiss any popups before doing anything else
        dismiss_overlays(page)

        # -------- Expand Details BEFORE baseline full-page screenshot --------
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
        _click_first(
            page,
            selectors=[
                "button:has-text('Details')",
                "text=/^details$/i",
                "[aria-controls*='details']",
                "[data-testid*='details']",
            ],
        )

        # Dismiss again (some sites trigger popups after interaction)
        dismiss_overlays(page)

        try:
            page.wait_for_timeout(400)
        except Exception:
            pass

        page.screenshot(path=paths["full_page"], full_page=True)

        # Visible text for analysis/debugging (capped)
        try:
            visible_text = page.inner_text("body")
        except Exception:
            visible_text = ""
        visible_text = (visible_text or "").strip()[:12000]

        # -------- Care view: scroll to a reliable anchor --------
        dismiss_overlays(page)

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

        # Scroll precisely to a Care header/button if present; else fallback scroll
        try:
            care_loc = page.locator(
                "button:has-text('Care'), summary:has-text('Care'), [role='button']:has-text('Care'), text=/^care$/i"
            ).first
            if care_loc.count() > 0:
                care_loc.scroll_into_view_if_needed(timeout=4000)
            else:
                page.mouse.wheel(0, int(VIEWPORT["height"] * 1.5))
        except Exception:
            pass

        if care_clicked:
            try:
                page.wait_for_timeout(300)
            except Exception:
                pass

        dismiss_overlays(page)
        _shot_viewport(page, paths["care_view"])

        # -------- Size chart view: top-of-page modal or link --------
        try:
            page.evaluate("window.scrollTo(0, 0)")
        except Exception:
            pass

        dismiss_overlays(page)

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
                page.wait_for_timeout(600)
            except Exception:
                pass

        dismiss_overlays(page)
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