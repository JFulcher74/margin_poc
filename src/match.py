import pandas as pd
import numpy as np

def match_records(disp_df: pd.DataFrame, inv_df: pd.DataFrame) -> pd.DataFrame:
    disp = disp_df.copy()
    inv = inv_df.copy()

    # Sort by cost ascending to ensure 'first' captures the cheapest supplier
    inv_sorted = inv.sort_values(by=['dm_d_code', 'unit_cost_gbp'])

    # Aggregate invoices
    inv_agg = inv_sorted.groupby('dm_d_code').agg(
        avg_unit_cost=('unit_cost_gbp', 'mean'),
        min_unit_cost=('unit_cost_gbp', 'min'),
        cheapest_supplier=('supplier_name', 'first'),
        supplier_variance=('supplier_name', 'nunique'),
        matched_supplier_description=('supplier_description', 'first'),
        invoice_pack_size=('pack_size', 'first')
    ).reset_index()

    inv_agg = inv_agg[inv_agg['dm_d_code'] != '']

    # Merge dispensing lines with the aggregated invoice costs
    matched = pd.merge(disp, inv_agg, on='dm_d_code', how='left')

    # Flag confidence
    matched['matched_dm_d_code'] = np.where(matched['avg_unit_cost'].notna(), matched['dm_d_code'], pd.NA)
    matched['confidence'] = np.where(matched['avg_unit_cost'].notna(), 'High', 'Low')

    # Fill defaults
    matched['avg_unit_cost'] = matched['avg_unit_cost'].fillna(0.0)
    matched['min_unit_cost'] = matched['min_unit_cost'].fillna(0.0)
    matched['cheapest_supplier'] = matched['cheapest_supplier'].fillna('Unknown')
    matched['supplier_variance'] = matched['supplier_variance'].fillna(1.0)
    matched['invoice_pack_size'] = matched['invoice_pack_size'].fillna(1.0)
    matched['matched_supplier_description'] = matched['matched_supplier_description'].fillna('Unmatched')

    return matched