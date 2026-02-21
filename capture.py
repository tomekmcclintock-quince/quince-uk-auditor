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


def _shot_viewport(page, path: str) -> None:
    page.screenshot(path=path, full_page=False)


def _clip_to_bbox(page, bbox: Dict[str, float], path: str) -> bool:
    try:
        clip = {
            "x": max(0, float(bbox["x"])),
            "y": max(0, float(bbox["y"])),
            "width": max(50, float(bbox["width"])),
            "height": max(50, float(bbox["height"])),
        }
        page.screenshot(path=path, full_page=False, clip=clip)
        return True
    except Exception:
        return False


def _clip_locator_bbox(page, locator, path: str, pad: int = 24, min_h: int = 520, max_h: int = 980) -> bool:
    """
    Clip around a locator's bounding box with padding.
    This is a fallback; preferred is clipping the *container* (see below).
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

        h = max(h, min_h)
        h = min(h, max_h)

        return _clip_to_bbox(page, {"x": x, "y": y, "width": w, "height": h}, path)
    except Exception:
        return False


def _section_container_from_trigger(trigger) -> Optional[object]:
    """
    Given an accordion trigger, return a locator for a reasonable container
    that likely includes the expanded content.
    We walk up a few ancestors and pick the first "big enough" box.
    """
    try:
        # Try a few likely container levels
        candidates = [
            trigger.locator("xpath=ancestor-or-self::section[1]"),
            trigger.locator("xpath=ancestor-or-self::div[contains(@class,'accordion')][1]"),
            trigger.locator("xpath=ancestor-or-self::div[contains(@class,'Accordion')][1]"),
            trigger.locator("xpath=ancestor-or-self::div[1]"),
            trigger.locator("xpath=ancestor-or-self::div[2]"),
            trigger.locator("xpath=ancestor-or-self::div[3]"),
        ]
        for c in candidates:
            if c.count() == 0:
                continue
            bbox = c.first.bounding_box()
            if not bbox:
                continue
            # If it's reasonably wide, it's probably a real container (not a skinny label column)
            if bbox["width"] >= 600:
                return c.first
        # Fallback: just return the trigger itself
        return trigger
    except Exception:
        return None


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


def _best_trigger(page, name: str):
    # Common accordion trigger patterns
    return page.locator(
        f"button:has-text('{name}'), summary:has-text('{name}'), [role='button']:has-text('{name}'), text=/^{name}$/i"
    ).first


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

        # Expand Details accordion if present
        details_trigger = _best_trigger(page, "Details")
        try:
            if details_trigger.count() > 0:
                details_trigger.scroll_into_view_if_needed(timeout=4000)
                details_trigger.click(timeout=2500)
        except Exception:
            pass

        dismiss_overlays(page)
        try:
            page.wait_for_timeout(400)
        except Exception:
            pass

        # Baseline full page
        page.screenshot(path=paths["full_page"], full_page=True)

        # Visible text excerpt
        try:
            visible_text = page.inner_text("body")
        except Exception:
            visible_text = ""
        visible_text = (visible_text or "").strip()[:12000]

        # -------- Details clipped view: clip the CONTAINER, not the trigger --------
        dismiss_overlays(page)
        details_ok = False
        try:
            if details_trigger.count() > 0:
                container = _section_container_from_trigger(details_trigger)
                if container and container.count() > 0:
                    details_ok = _clip_locator_bbox(page, container, paths["details_view"], pad=24, min_h=650, max_h=980)
        except Exception:
            details_ok = False
        if not details_ok:
            # fallback: viewport screenshot near the trigger
            try:
                if details_trigger.count() > 0:
                    details_trigger.scroll_into_view_if_needed(timeout=4000)
            except Exception:
                pass
            _shot_viewport(page, paths["details_view"])

        # -------- Care clipped view: clip CONTAINER around Care --------
        dismiss_overlays(page)
        care_trigger = _best_trigger(page, "Care")

        care_ok = False
        try:
            if care_trigger.count() > 0:
                care_trigger.scroll_into_view_if_needed(timeout=4000)
                try:
                    care_trigger.click(timeout=2500)
                except Exception:
                    pass

                try:
                    page.wait_for_timeout(300)
                except Exception:
                    pass

                dismiss_overlays(page)

                container = _section_container_from_trigger(care_trigger)
                if container and container.count() > 0:
                    care_ok = _clip_locator_bbox(page, container, paths["care_view"], pad=24, min_h=650, max_h=980)
        except Exception:
            care_ok = False

        if not care_ok:
            # fallback: scroll down and take viewport (always produces an image)
            try:
                page.mouse.wheel(0, int(VIEWPORT["height"] * 1.5))
            except Exception:
                pass
            _shot_viewport(page, paths["care_view"])

        # -------- Size chart view: modal bbox if present, else top viewport --------
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

            dialog = page.locator("[role='dialog'], [aria-modal='true'], .modal, .Modal").first
            if dialog.count() > 0:
                if not _clip_locator_bbox(page, dialog, paths["size_chart_view"], pad=18, min_h=520, max_h=980):
                    _shot_viewport(page, paths["size_chart_view"])
            else:
                _shot_viewport(page, paths["size_chart_view"])
        else:
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