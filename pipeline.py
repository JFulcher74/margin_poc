import argparse
import pandas as pd
from pathlib import Path

from src.normalise import normalise_dispensing, normalise_invoices, normalise_tariff
from src.match import match_records
from src.calc import calculate_metrics
from src.report import generate_reports

def main():
    parser = argparse.ArgumentParser(description="Margin Leakage Pipeline")
    parser.add_argument("--golden", action="store_true", help="Run on golden datasets")
    args = parser.parse_args()

    if args.golden:
        disp_file = "golden_dispensing_10.csv"
        inv_file = "golden_invoices_10.csv"
        print("Running pipeline on golden dataset...")
    else:
        disp_file = "dispensing_mock.csv"
        inv_file = "invoices_mock.csv"
        print("Running pipeline on standard mock dataset...")

    # 1. Load Data
    try:
        disp_df = pd.read_csv(disp_file, dtype={'dm_d_code': str})
        inv_df = pd.read_csv(inv_file, dtype={'dm_d_code': str})
        tariff_df_raw = pd.read_csv("Part VIIIA April 2026.csv", skiprows=2, dtype={'VMPP Snomed Code': str})
        dnd_df = pd.read_csv("dnd_mock.csv", dtype={'dm_d_code': str})
    except FileNotFoundError as e:
        print(f"Error loading files: {e}")
        return

    # 2. Normalise
    disp_norm = normalise_dispensing(disp_df)
    inv_norm = normalise_invoices(inv_df)
    tariff_norm = normalise_tariff(tariff_df_raw)

    # 3. Match
    matched_df = match_records(disp_norm, inv_norm)

    # 4. Calculate
    results_df = calculate_metrics(matched_df, tariff_norm, dnd_df)

    # 5. Report
    out_dir = "outputs_golden" if args.golden else "outputs"
    generate_reports(results_df, out_dir)
    print(f"Pipeline complete. Outputs written to {out_dir}/")

    # --- P&L Sanity Summary ---
    # Moved inside main() so 'args' and 'results_df' are accessible
    print("\n--- P&L Financial Summary ---")
    total_margin = results_df['margin_gbp'].sum()
    status = "PROFIT" if total_margin > 0 else "LOSS"
    print(f"Net Practice Position: £{total_margin:.2f} ({status})")
    print(f"Total Items Processed: {results_df['total_quantity_packs'].sum()}")
    print("-----------------------------\n")

if __name__ == "__main__":
    main()