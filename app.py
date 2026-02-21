import os
import re
import time
import uuid
import sys
import subprocess
from pathlib import Path

import streamlit as st

from capture import capture_pdp
from analyze import analyze
from report_pdf import build_pdf
from regions import REGIONS

APP_TITLE = "PDP Readiness Auditor"
URL_RE = re.compile(r"^https?://", re.IGNORECASE)

DEFAULT_BROWSERS_PATH = ".playwright"


def is_valid_url(url: str) -> bool:
    return bool(url and URL_RE.match(url.strip()))


def ensure_playwright_chromium():
    """
    Ensure Playwright Chromium is downloaded in the Streamlit environment.

    Important: Use sys.executable (Streamlit's venv python), NOT /usr/local/bin/python.
    """
    browsers_path = os.environ.get("PLAYWRIGHT_BROWSERS_PATH", DEFAULT_BROWSERS_PATH)

    # If the chrome-headless-shell exists anywhere under browsers_path, assume installed.
    root = Path(browsers_path)
    if root.exists():
        matches = list(root.rglob("chrome-headless-shell"))
        if matches:
            return  # installed

    env = os.environ.copy()
    env["PLAYWRIGHT_BROWSERS_PATH"] = browsers_path

    # Use the *current* Python interpreter (Streamlit venv)
    cmd = [sys.executable, "-m", "playwright", "install", "chromium"]
    proc = subprocess.run(cmd, capture_output=True, text=True, env=env)

    if proc.returncode != 0:
        raise RuntimeError(
            "Playwright install failed.\n\n"
            f"Python: {sys.executable}\n"
            f"Command: {' '.join(cmd)}\n\n"
            f"STDOUT:\n{proc.stdout}\n\n"
            f"STDERR:\n{proc.stderr}\n"
        )


def run_audit(url: str, region_key: str) -> str:
    region = REGIONS.get(region_key, REGIONS["UK"])

    run_root = Path("runs") / f"{int(time.time())}_{uuid.uuid4().hex[:8]}"
    run_root.mkdir(parents=True, exist_ok=True)

    _, payload = capture_pdp(
        url,
        out_root=str(run_root),
        locale=region["playwright_locale"],
    )

    payload["region_key"] = region_key
    payload["region_label"] = region["label"]
    payload["report_title"] = f"{region['label']} PDP Readiness Audit"

    analysis = analyze(payload, region=region)  # if OpenAI fails, do not generate PDF
    analysis["report_title"] = payload["report_title"]

    pdf_path = build_pdf(payload, analysis)
    return pdf_path


st.set_page_config(page_title=APP_TITLE, layout="centered")
st.title(APP_TITLE)
st.caption(
    "Paste a Quince PDP URL → generates a PDF with screenshots + localization/compliance findings for the selected region."
)

with st.sidebar:
    st.subheader("Settings")
    region_key = st.selectbox(
        "Audit region",
        options=list(REGIONS.keys()),
        index=0,  # default UK
        format_func=lambda k: f"{k} — {REGIONS[k]['label']}",
    )

    st.subheader("Notes")
    st.write(
        "- Uses Playwright to render the page and capture screenshots.\n"
        "- Expands Details before the baseline screenshot.\n"
        "- Captures Care section and Size Chart/Guide (if present).\n"
        "- Generates a PDF report with findings."
    )

# Ensure Chromium exists before any audit run
try:
    ensure_playwright_chromium()
except Exception as e:
    st.error("Chromium is not installed (or could not be installed) in this Streamlit environment.")
    st.exception(e)
    st.stop()

url = st.text_input("PDP URL", placeholder="https://www.quince.com/…")
run_btn = st.button("Run audit", type="primary", disabled=not is_valid_url(url))

if run_btn:
    url = url.strip()
    if not is_valid_url(url):
        st.error("Please enter a valid URL starting with http:// or https://")
        st.stop()

    try:
        with st.spinner("Running audit… (capturing screenshots, analyzing, generating PDF)"):
            pdf_path = run_audit(url, region_key)

        st.success("Report ready!")
        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()

        filename = f"{region_key.lower()}_pdp_audit_{uuid.uuid4().hex[:8]}.pdf"
        st.download_button(
            label="Download PDF report",
            data=pdf_bytes,
            file_name=filename,
            mime="application/pdf",
        )
        st.caption(f"Server file: {pdf_path}")

    except Exception as e:
        st.error("Audit failed.")
        st.exception(e)