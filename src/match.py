import pandas as pd
import numpy as np

def match_records(disp_df: pd.DataFrame, inv_df: pd.DataFrame) -> pd.DataFrame:
    disp = disp_df.copy()
    inv = inv_df.copy()

    # 1. Prepare quantities to enable weighted average calculations
    if 'quantity' not in inv.columns:
        inv['quantity'] = 1.0
    else:
        inv['quantity'] = pd.to_numeric(inv['quantity'], errors='coerce').fillna(1.0)
        
    # Calculate the total spend per line for weighting
    inv['total_line_cost'] = inv['unit_cost_gbp'] * inv['quantity']

    # 2. Sort by cost ascending to ensure 'first' strictly captures the cheapest supplier
    inv_sorted = inv.sort_values(by=['dm_d_code', 'unit_cost_gbp'])

    # 3. Aggregate invoices using weighted metrics
    inv_agg = inv_sorted.groupby('dm_d_code').agg(
        total_spent=('total_line_cost', 'sum'),
        total_quantity=('quantity', 'sum'),
        min_unit_cost=('unit_cost_gbp', 'min'),
        cheapest_supplier=('supplier_name', 'first'),
        supplier_variance=('supplier_name', 'nunique'),
        matched_supplier_description=('supplier_description', 'first'),
        invoice_pack_size=('pack_size', 'first')
    ).reset_index()

    # Remove empty dm_d_codes to prevent arbitrary blank matches
    inv_agg = inv_agg[inv_agg['dm_d_code'] != '']

    # 4. Calculate the true weighted average unit cost
    # .replace(0, 1) prevents a ZeroDivisionError if an invoice line has a 0 quantity anomaly
    inv_agg['avg_unit_cost'] = inv_agg['total_spent'] / inv_agg['total_quantity'].replace(0, 1)

    # 5. Merge dispensing lines with the aggregated invoice costs
    matched = pd.merge(disp, inv_agg, on='dm_d_code', how='left')

    # 6. Flag confidence based on successful match
    matched['matched_dm_d_code'] = np.where(matched['avg_unit_cost'].notna(), matched['dm_d_code'], pd.NA)
    matched['confidence'] = np.where(matched['avg_unit_cost'].notna(), 'High', 'Low')

    # 7. Fill defaults for unmatched lines to prevent downstream calculator crashes
    matched['avg_unit_cost'] = matched['avg_unit_cost'].fillna(0.0)
    matched['min_unit_cost'] = matched['min_unit_cost'].fillna(0.0)
    matched['cheapest_supplier'] = matched['cheapest_supplier'].fillna('Unknown')
    matched['supplier_variance'] = matched['supplier_variance'].fillna(1.0)
    matched['invoice_pack_size'] = matched['invoice_pack_size'].fillna(1.0)
    matched['matched_supplier_description'] = matched['matched_supplier_description'].fillna('Unmatched')

    # Clean up temporary aggregation columns that are no longer required
    matched = matched.drop(columns=['total_spent', 'total_quantity'], errors='ignore')

    return matched