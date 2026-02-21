import os
import json
import base64
from typing import Dict, Any, List

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()


def data_url_png(path: str) -> str:
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    return f"data:image/png;base64,{b64}"


def analyze(payload: Dict[str, Any]) -> Dict[str, Any]:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("Missing OPENAI_API_KEY. Add it to your .env file.")

    client = OpenAI(api_key=api_key)

    image_keys = ["full_page", "details_view", "care_view", "size_chart_view"]
    images: List[Dict[str, Any]] = []
    for k in image_keys:
        path = payload["paths"].get(k)
        if path and os.path.exists(path):
            images.append({"type": "input_image", "image_url": data_url_png(path)})

    schema = {
        "summary": "string",
        "findings": [
            {
                "category": "Localization|Compliance",
                "severity": "High|Medium|Low",
                "owner": "Merch|Design|Eng|Legal|CX",
                "issue": "string",
                "why_it_matters_uk": "string",
                "where": "string (describe location + reference screenshot key)",
                "recommendation": "string (exact copy/UX change; can be long)",
                "evidence_screenshot": "one of: full_page, details_view, care_view, size_chart_view",
            }
        ],
    }

    system = (
        "You are an e-commerce PDP auditor for UK launch readiness. "
        "You produce actionable findings for Merch and Design with exact copy/UX recommendations. "
        "You are not a lawyer; flag potential compliance issues for Legal review when appropriate. "
        "Return valid JSON only."
    )

    user_text = f"""
Audit this product page for UK readiness.

Focus on TWO areas:
1) Localization quality for UK shoppers (tone, wording, units, sizing conventions, UK terminology).
2) Compliance readiness signals (price transparency, VAT/taxes clarity, delivery charges clarity, fibre/material composition disclosure).

You will be given screenshots:
- full_page: baseline PDP (full page)
- details_view: clipped screenshot around the Details section (expanded)
- care_view: clipped screenshot around the Care section (expanded)
- size_chart_view: clipped screenshot of the Size Chart/Guide modal (if present) or top sizing area

Return JSON in this schema:
{json.dumps(schema, indent=2)}

Visible text excerpt (may be incomplete):
{payload["visible_text"]}
""".strip()

    content = [{"type": "input_text", "text": user_text}] + images

    resp = client.responses.create(
        model="gpt-4.1",
        input=[
            {"role": "system", "content": system},
            {"role": "user", "content": content},
        ],
        text={"format": {"type": "json_object"}},
    )

    return json.loads(resp.output_text)