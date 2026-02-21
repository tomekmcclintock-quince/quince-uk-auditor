import os
import hashlib
from typing import Dict, Tuple, Optional

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


def _clip_to_bbox(page, bbox: Dict[str, float], path: str) -> None:
    # Ensure clip is within page bounds and non-negative
    clip = {
        "x": max(0, float(bbox["x"])),
        "y": max(0, float(bbox["y"])),
        "width": max(1, float(bbox["width"])),
        "height": max(1, float(bbox["height"])),
    }
    page.screenshot(path=path, full_page=False, clip=clip)


def _clip_locator(page, locator, path: str, pad: int = 24, min_h: int = 360, max_h: int = 900) -> bool:
    """
    Take a clipped screenshot around a locator, with padding.
    Returns True if shot was taken.
    """
    try:
        if locator.count() == 0:
            return False

        locator.scroll_into_view_if_needed(timeout=4000)

        bbox = locator.bounding_box()
        if not bbox:
            return False

        x = max(0, bbox["x"] - pad)
        y = max(0, bbox["y"] - pad)
        w = bbox["width"] + pad * 2
        h = bbox["height"] + pad * 2

        # Normalize height so we capture content, not a tiny line
        h = max(h, min_h)
        h = min(h, max_h)

        _clip_to_bbox(page, {"x": x, "y": y, "width": w, "height": h}, path)
        return True
    except Exception:
        return False


def dismiss_overlays(page) -> None:
    """
    Best-effort dismiss for email capture / cookie / modal overlays.
    Never raises.
    """
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

            # last resort: remove dialog overlays if still present
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
            break
    except Exception:
        return


def _best_section_locator(page, names) -> Optional[object]:
    """
    Return a locator for the first matching section trigger among common patterns.
    names: list[str] like ["Details"] or ["Care"]
    """
    for name in names:
        # button/summary/role=button are common accordion triggers
        loc = page.locator(
            f"button:has-text('{name}'), summary:has-text('{name}'), [role='button']:has-text('{name}')"
        ).first
        try:
            if loc.count() > 0:
                return loc
        except Exception:
            continue
    return None


def capture_pdp(url: str, out_root: str = "out") -> Tuple[str, Dict]:
    run_id = sha8(url)
    out_dir = os.path.join(out_root, run_id)
    shots_dir = os.path.join(out_dir, "screenshots")
    safe_mkdir(shots_dir)

    paths = {
        "full_page": os.path.join(shots_dir, "01_full_page.png"),
        "details_view": os.path.join(shots_dir, "02_details_view.png"),
        "care_view": os.path.join(shots_dir, "03_care_view.png"),
        "size_chart_view": os.path.join(shots_dir, "04_size_chart_view.png"),
    }

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport=VIEWPORT, locale="en-GB")
        page = context.new_page()

        page.goto(url, wait_until="networkidle", timeout=90_000)
        dismiss_overlays(page)

        # -------- Expand Details before baseline screenshot --------
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

        details_trigger = _best_section_locator(page, ["Details"])
        if details_trigger:
            try:
                details_trigger.scroll_into_view_if_needed(timeout=4000)
                details_trigger.click(timeout=2500)
            except Exception:
                pass

        dismiss_overlays(page)
        try:
            page.wait_for_timeout(400)
        except Exception:
            pass

        # Baseline full page (expanded state if possible)
        page.screenshot(path=paths["full_page"], full_page=True)

        # Visible text for analysis/debugging (capped)
        try:
            visible_text = page.inner_text("body")
        except Exception:
            visible_text = ""
        visible_text = (visible_text or "").strip()[:12000]

        # -------- Details clipped view (readable evidence) --------
        # Try to clip around the Details trigger area or a nearby heading.
        dismiss_overlays(page)
        details_loc = None
        if details_trigger:
            details_loc = details_trigger
        else:
            # fallback: find "Details" text as anchor
            details_loc = page.locator("text=/^details$/i").first

        if details_loc and details_loc.count() > 0:
            _clip_locator(page, details_loc, paths["details_view"], pad=24, min_h=520, max_h=950)
        else:
            # fallback: top viewport
            page.evaluate("window.scrollTo(0, 0)")
            page.screenshot(path=paths["details_view"], full_page=False)

        # -------- Care clipped view (reliable anchor + expanded content) --------
        dismiss_overlays(page)
        care_trigger = _best_section_locator(page, ["Care"])

        if care_trigger and care_trigger.count() > 0:
            try:
                care_trigger.scroll_into_view_if_needed(timeout=4000)
                care_trigger.click(timeout=2500)
            except Exception:
                pass

            try:
                page.wait_for_timeout(300)
            except Exception:
                pass

            dismiss_overlays(page)
            _clip_locator(page, care_trigger, paths["care_view"], pad=24, min_h=620, max_h=1000)
        else:
            # fallback: scroll and try to anchor on "Care"
            try:
                page.mouse.wheel(0, int(VIEWPORT["height"] * 1.5))
            except Exception:
                pass
            care_text = page.locator("text=/^care$/i").first
            if care_text.count() > 0:
                _clip_locator(page, care_text, paths["care_view"], pad=24, min_h=620, max_h=1000)
            else:
                page.screenshot(path=paths["care_view"], full_page=False)

        # -------- Size chart view (modal clipped if present) --------
        # Go to top because size chart link is near top
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

            # Clip the modal/dialog itself for readable evidence
            dialog = page.locator("[role='dialog'], [aria-modal='true'], .modal, .Modal").first
            if dialog.count() > 0:
                _clip_locator(page, dialog, paths["size_chart_view"], pad=18, min_h=520, max_h=980)
            else:
                # fallback: viewport
                page.screenshot(path=paths["size_chart_view"], full_page=False)
        else:
            # If there is no size chart (common), capture top viewport as evidence
            page.screenshot(path=paths["size_chart_view"], full_page=False)

        browser.close()

    return run_id, {
        "url": url,
        "run_id": run_id,
        "out_dir": out_dir,
        "shots_dir": shots_dir,
        "paths": paths,
        "visible_text": visible_text,
    }