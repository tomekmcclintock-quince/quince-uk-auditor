import sys

from capture import capture_pdp
from analyze import analyze
from report_pdf import build_pdf
from regions import REGIONS


def main():
    if len(sys.argv) < 2:
        print('Usage: python3 run_audit.py "<PDP_URL>" [REGION_KEY]')
        print("REGION_KEY options:", ", ".join(REGIONS.keys()))
        raise SystemExit(1)

    url = sys.argv[1]
    region_key = sys.argv[2] if len(sys.argv) >= 3 else "UK"
    region = REGIONS.get(region_key, REGIONS["UK"])

    run_id, payload = capture_pdp(url, locale=region["playwright_locale"])

    payload["region_key"] = region_key
    payload["region_label"] = region["label"]
    payload["report_title"] = f"{region['label']} PDP Readiness Audit"

    # If OpenAI fails, this will raise and the PDF will NOT be generated (as requested).
    analysis = analyze(payload, region=region)
    analysis["report_title"] = payload["report_title"]

    pdf_path = build_pdf(payload, analysis)

    print("\n✅ Done")
    print(f"Run ID: {run_id}")
    print(f"Region: {region_key} — {region['label']}")
    print(f"PDF report: {pdf_path}")
    print(f"Screenshots: {payload['shots_dir']}")


if __name__ == "__main__":
    main()