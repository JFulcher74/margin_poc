import pandas as pd
from pathlib import Path

def generate_reports(df: pd.DataFrame, output_dir: str):
    schema_cols = [
        'key_drug', 
        'example_drug_description', 
        'example_supplier_description',
        'total_quantity_packs', 
        'gross_drug_reimbursed_gbp',
        'clawback_deduction_gbp',
        'net_drug_reimbursed_gbp',
        'vat_allowance_gbp',
        'dispensing_fees_earned_gbp',
        'net_income_gbp',
        'acquisition_cost_gbp', 
        'margin_gbp', 
        'confidence', 
        'reason_tag', 
        'suggested_action'
    ]

    df_sorted = df[schema_cols].sort_values('margin_gbp', ascending=False)

    # Enforce 2 decimal places on all GBP columns
    gbp_cols = [col for col in df_sorted.columns if 'gbp' in col]
    for col in gbp_cols:
        df_sorted[col] = df_sorted[col].round(2)

    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    df_sorted.to_csv(out_path / 'margin_analysis_all.csv', index=False)
    
    top_profits = df_sorted.head(10)
    top_losses = df_sorted.tail(10)
    
    focus_report = pd.concat([top_profits, top_losses]).drop_duplicates(subset=['key_drug'])
    focus_report.to_csv(out_path / 'margin_focus_report.csv', index=False)