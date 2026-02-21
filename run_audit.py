import sys

from capture import capture_pdp
from analyze import analyze
from report_pdf import build_pdf


def main():
    if len(sys.argv) < 2:
        print('Usage: python3 run_audit.py "<PDP_URL>"')
        raise SystemExit(1)

    url = sys.argv[1]

    run_id, payload = capture_pdp(url)

    # If OpenAI fails, this will raise and the PDF will NOT be generated (as requested).
    analysis = analyze(payload)

    pdf_path = build_pdf(payload, analysis)

    print("\n✅ Done")
    print(f"Run ID: {run_id}")
    print(f"PDF report: {pdf_path}")
    print(f"Screenshots: {payload['shots_dir']}")


if __name__ == "__main__":
    main()