import os
import re
import time
import uuid
from pathlib import Path

import streamlit as st

from capture import capture_pdp
from analyze import analyze
from report_pdf import build_pdf


APP_TITLE = "UK PDP Readiness Auditor"
URL_RE = re.compile(r"^https?://", re.IGNORECASE)


def is_valid_url(url: str) -> bool:
    return bool(url and URL_RE.match(url.strip()))


def run_audit(url: str) -> str:
    """
    Runs the full pipeline:
    - capture screenshots
    - call OpenAI analysis
    - generate PDF
    Returns path to the generated PDF.
    """

    # Use a unique out_root per run so multiple users / same URL won't collide.
    run_root = Path("runs") / f"{int(time.time())}_{uuid.uuid4().hex[:8]}"
    run_root.mkdir(parents=True, exist_ok=True)

    _, payload = capture_pdp(url, out_root=str(run_root))
    analysis = analyze(payload)          # If OpenAI fails, we want the app to fail (as you requested)
    pdf_path = build_pdf(payload, analysis)
    return pdf_path


st.set_page_config(page_title=APP_TITLE, layout="centered")
st.title(APP_TITLE)
st.caption("Paste a Quince PDP URL → generates a PDF with screenshots + UK localization/compliance findings.")

# --- Sidebar (optional) ---
with st.sidebar:
    st.subheader("Notes")
    st.write(
        "- Uses Playwright to render the page and capture screenshots.\n"
        "- Expands Details before the baseline screenshot.\n"
        "- Captures Care section and Size Chart/Guide (if present).\n"
        "- Generates a PDF report with findings."
    )

# --- Main UI ---
url = st.text_input("PDP URL", placeholder="https://www.quince.com/…")

col1, col2 = st.columns([1, 2])
with col1:
    run_btn = st.button("Run audit", type="primary", disabled=not is_valid_url(url))

with col2:
    st.write("")

if run_btn:
    url = url.strip()
    if not is_valid_url(url):
        st.error("Please enter a valid URL starting with http:// or https://")
        st.stop()

    try:
        with st.spinner("Running audit… (capturing screenshots, analyzing, generating PDF)"):
            pdf_path = run_audit(url)

        st.success("Report ready!")

        # Streamlit download button needs bytes
        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()

        filename = f"uk_pdp_audit_{uuid.uuid4().hex[:8]}.pdf"
        st.download_button(
            label="Download PDF report",
            data=pdf_bytes,
            file_name=filename,
            mime="application/pdf",
        )

        # Show where it is on server (helpful for debugging)
        st.caption(f"Server file: {pdf_path}")

    except Exception as e:
        st.error("Audit failed.")
        st.exception(e)