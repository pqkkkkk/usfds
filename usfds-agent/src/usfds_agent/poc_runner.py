"""Proof of Concept (PoC) Runner for USFDS AI Fraud Investigation Agent.
Demonstrates automated investigation and SAR reporting on real True Positive and False Positive cases.
"""

import os
from pathlib import Path

from usfds_agent.agent import FraudInvestigationRunner
from usfds_agent.config import (
    GOOGLE_API_KEY,
    REPO_ROOT,
)

OUTPUT_DIR = REPO_ROOT / "usfds-agent" / "poc_outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def find_sample_cases() -> tuple[int, int]:
    """Returns representative True Positive and False Positive cases from evaluation artifacts."""
    # TP 3298: Extreme shipping distance (3,401 km), Amount $2,136.78, y_prob=0.95, Actual Fraud (y_true=1)
    # FP 197021: Benign transaction flagged high risk (y_prob=0.70, Actual Normal y_true=0)
    return 3298, 197021


def main():
    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY") or GOOGLE_API_KEY
    if not api_key:
        print("[!] Warning: GOOGLE_API_KEY or GEMINI_API_KEY is not set.")
        print("    Please export GEMINI_API_KEY=your_key or add it to usfds-agent/.env")
        return

    print("================================================================================")
    print("      USFDS AI AGENT PROOF OF CONCEPT (PoC) - FRAUD INVESTIGATION & SAR        ")
    print("================================================================================")

    tp_event_id, fp_event_id = find_sample_cases()
    print(f"[*] Selected Test Cases from storage_output:")
    print(f"    - True Positive Case (Actual Fraud): event_id = {tp_event_id}")
    print(f"    - False Positive Case (Benign Alert): event_id = {fp_event_id}")

    runner = FraudInvestigationRunner(model_name="gemini-3.8-flash")

    # --- Run Case 1: True Positive ---
    print(f"\n[>>>] RUNNING INVESTIGATION 1: TRUE POSITIVE (event_id={tp_event_id})")
    tp_report = runner.run_investigation(event_id=tp_event_id, verbose=True)

    tp_out_path = OUTPUT_DIR / f"investigation_report_TP_{tp_event_id}.md"
    tp_out_path.write_text(tp_report, encoding="utf-8")
    print(f"\n[+] True Positive Report saved to: {tp_out_path}")
    print("\n--- REPORT PREVIEW ---")
    print(tp_report[:800] + "...\n")

    # --- Run Case 2: False Positive ---
    print(f"\n[>>>] RUNNING INVESTIGATION 2: FALSE POSITIVE (event_id={fp_event_id})")
    fp_report = runner.run_investigation(event_id=fp_event_id, verbose=True)

    fp_out_path = OUTPUT_DIR / f"investigation_report_FP_{fp_event_id}.md"
    fp_out_path.write_text(fp_report, encoding="utf-8")
    print(f"\n[+] False Positive Report saved to: {fp_out_path}")
    print("\n--- REPORT PREVIEW ---")
    print(fp_report[:800] + "...\n")

    print("================================================================================")
    print("                    PoC INVESTIGATION COMPLETED SUCCESSFULLY                     ")
    print("================================================================================")


if __name__ == "__main__":
    main()
