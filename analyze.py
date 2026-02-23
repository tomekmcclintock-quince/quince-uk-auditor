import os
import json
import base64
from typing import Dict, Any, List, Optional

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()


def data_url_png(path: str) -> str:
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    return f"data:image/png;base64,{b64}"


def _default_region() -> Dict[str, Any]:
    # Safe fallback if caller doesn't pass a region
    return {
        "label": "United Kingdom",
        "playwright_locale": "en-GB",
        "analysis_language": "English (UK)",
        "focus": [
            "UK localization (spelling, tone, terminology, sizing conventions, units)",
            "UK compliance signals (VAT/taxes clarity, delivery charges clarity, fibre/material composition disclosure)",
        ],
    }


def analyze(payload: Dict[str, Any], region: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("Missing OPENAI_API_KEY. Add it to your .env file.")

    region = region or _default_region()
    client = OpenAI(api_key=api_key)

    image_keys = ["full_page", "care_view", "size_fit_view", "size_chart_view"]
    images: List[Dict[str, Any]] = []
    for k in image_keys:
        path = payload["paths"].get(k)
        if path and os.path.exists(path):
            images.append({"type": "input_image", "image_url": data_url_png(path)})

    schema = {
        "findings": [
            {
                "category": "Localization|Compliance",
                "severity": "High|Medium|Low",
                "owner": "Merch|Design|Eng|Legal|CX",
                "issue": "string",
                "why_it_matters": "string",
                "where": "string (describe location + reference screenshot key)",
                "recommendation": "string (exact copy/UX change; can be long)",
                "evidence_screenshot": "one of: full_page, care_view, size_fit_view, size_chart_view",
            }
        ],
    }

    system = (
        f"You are an e-commerce PDP auditor for {region['label']} launch readiness. "
        "You produce actionable findings for Merch and Design with exact copy/UX recommendations. "
        "You are not a lawyer; flag potential compliance issues for Legal review when appropriate. "
        "CRITICAL: Write ALL output text in ENGLISH (you may quote short on-page strings as evidence). "
        "Return valid JSON only."
    )

    focus_loc = region.get("focus", ["Localization", "Compliance"])
    focus_1 = focus_loc[0] if len(focus_loc) > 0 else "Localization"
    focus_2 = focus_loc[1] if len(focus_loc) > 1 else "Compliance"

    user_text = f"""
Audit this product page for {region['label']} readiness.

Language expectation: {region.get("analysis_language", "English")}

OUTPUT LANGUAGE REQUIREMENT:
- You MUST write ALL findings in ENGLISH.
- Do NOT write French or German in any field values (except short quoted evidence).

Focus on TWO areas:
1) {focus_1}
2) {focus_2}

Region-specific checks to apply (non-exhaustive):
- Taxes / VAT / duties messaging should match {region['label']} expectations.
- Units & sizing conventions should match {region['label']} norms (metric vs imperial; naming conventions).
- Delivery pricing, thresholds, and timelines should be clear for {region['label']}.
- Fibre/material composition disclosure should be present and readable in the shopper language.

You will be given screenshots:
- full_page: baseline PDP (full page) with Details expanded if available
- care_view: viewport screenshot around the Care section (scrolled, expanded if available)
- size_fit_view: viewport screenshot around the Size & Fit section (scrolled, expanded if available)
- size_chart_view: screenshot showing Size Chart/Guide modal if opened, otherwise top sizing area

Return JSON in this schema:
{json.dumps(schema, indent=2)}

Visible text excerpt (may be incomplete):
{payload.get("visible_text", "")}
""".strip()

    content = [{"type": "input_text", "text": user_text}] + images

    resp = client.responses.create(
        model="gpt-5.2",
        input=[
            {"role": "system", "content": system},
            {"role": "user", "content": content},
        ],
        text={"format": {"type": "json_object"}},
    )

    return json.loads(resp.output_text)