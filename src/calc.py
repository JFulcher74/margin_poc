import pandas as pd
import numpy as np
from src.utils import get_worst_confidence

BNF_MAPPING = {
    '01': 'Gastro-Intestinal System', '02': 'Cardiovascular System', '03': 'Respiratory System',
    '04': 'Central Nervous System', '05': 'Infections', '06': 'Endocrine System',
    '07': 'Obstetrics, Gynaecology & Urinary', '08': 'Malignant Disease & Immunosuppression',
    '09': 'Nutrition & Blood', '10': 'Musculoskeletal & Joint Diseases',
    '11': 'Eye', '12': 'Ear, Nose & Oropharynx', '13': 'Skin'
}

SWITCH_MAPPING = {
    '17603511000001107': {
        'switch_type': 'Therapeutic Switch', 'suggested_drug': 'Lansoprazole 30mg capsules',
        'est_generic_cost': 0.85, 'est_generic_reimbursement': 1.15,
        'clinical_rationale': 'Equipotent PPI therapy for acid suppression. Lansoprazole currently yields a higher net dispensing margin under Category M.',
        'reference_source': 'Local ICB Formulary', 'clinical_link': 'https://bnf.nice.org.uk/treatment-summaries/proton-pump-inhibitors/',
        'clinical_effort': 'Tier 2: Clinical Review Required', 'mds_warning': False,
        'locality_alignment': 'Green List (Preferred)', 'incentive_scheme': 'Aligned with QIPP targets'
    },
    '28572511000001104': {
        'switch_type': 'Therapeutic Switch', 'suggested_drug': 'Apixaban 5mg tablets',
        'est_generic_cost': 2.10, 'est_generic_reimbursement': 2.25,
        'clinical_rationale': 'Both are effective DOACs for stroke prevention in non-valvular AF. Apixaban availability offers a superior generic margin profile.',
        'reference_source': 'BNF / NICE NG196', 'clinical_link': 'https://bnf.nice.org.uk/treatment-summaries/anticoagulants-oral/',
        'clinical_effort': 'Tier 2: Clinical Review Required', 'mds_warning': False,
        'locality_alignment': 'Green List (Preferred)', 'incentive_scheme': 'Aligned with National DOAC Guidance'
    },
    '8058211000001101': {
        'switch_type': 'Generic Switch', 'suggested_drug': 'Atorvastatin 20mg tablets (Category M)',
        'est_generic_cost': 0.75, 'est_generic_reimbursement': 0.98,
        'clinical_rationale': 'Direct molecular equivalent. Eliminates branded prescribing leakage and aligns with primary care formulary guidance.',
        'reference_source': 'NICE CG71', 'clinical_link': 'https://bnf.nice.org.uk/drugs/atorvastatin/',
        'clinical_effort': 'Tier 1: Immediate (Administrative)', 'mds_warning': True,
        'locality_alignment': 'Green List (Preferred)', 'incentive_scheme': 'High-Intensity Statin Target'
    },
    '11417011000001106': {
        'switch_type': 'Generic Switch', 'suggested_drug': 'Esomeprazole 20mg tablets (Category M)',
        'est_generic_cost': 1.12, 'est_generic_reimbursement': 1.45,
        'clinical_rationale': 'Direct molecular equivalent.',
        'reference_source': 'BNF', 'clinical_link': 'https://bnf.nice.org.uk/drugs/esomeprazole/',
        'clinical_effort': 'Tier 1: Immediate (Administrative)', 'mds_warning': True,
        'locality_alignment': 'Grey List (Non-Preferred)', 'incentive_scheme': 'Conflicts with local PPI targets'
    }
}

CONCESSIONS_MAPPING = {
    '11417011000001106': 22.50, '28246311000001109': 4.50,
    '15152011000001109': 8.20, '14188111000001100': 3.10
}

MDS_MAPPING = {
    '28572511000001104': 10.0, '8058211000001101': 15.0, '11417011000001106': 12.5
}

KNOWN_PA_DMD_CODES = [
    '1411111000001103', '10862711000001106', '3371911000001104', '15569411000001107'
]

def get_clawback_rate(total_monthly_basic_price: float) -> float:
    if total_monthly_basic_price <= 2000.00: return 0.0317
    elif total_monthly_basic_price <= 4000.00: return 0.0593
    elif total_monthly_basic_price <= 6000.00: return 0.0721
    elif total_monthly_basic_price <= 8000.00: return 0.0806
    elif total_monthly_basic_price <= 10000.00: return 0.0868
    elif total_monthly_basic_price <= 12000.00: return 0.0919
    elif total_monthly_basic_price <= 14000.00: return 0.0960
    elif total_monthly_basic_price <= 16000.00: return 0.0997
    elif total_monthly_basic_price <= 18000.00: return 0.1029
    elif total_monthly_basic_price <= 20000.00: return 0.1057
    elif total_monthly_basic_price <= 22000.00: return 0.1082
    elif total_monthly_basic_price <= 24000.00: return 0.1103
    else: return 0.1118

def get_dispensing_fee(total_items: int) -> float:
    if total_items <= 460: return 2.58
    elif total_items <= 575: return 2.55
    elif total_items <= 690: return 2.52
    elif total_items <= 805: return 2.49
    elif total_items <= 920: return 2.46
    elif total_items <= 1035: return 2.44
    elif total_items <= 1495: return 2.40
    elif total_items <= 1955: return 2.36
    elif total_items <= 2415: return 2.32
    elif total_items <= 2875: return 2.29
    elif total_items <= 3335: return 2.25
    elif total_items <= 3795: return 2.22
    elif total_items <= 4600: return 2.19
    else: return 2.11

def calculate_metrics(df: pd.DataFrame, tariff_df: pd.DataFrame, dnd_df: pd.DataFrame, override_basic_price: float = None, rebate_dict: dict = None, mds_active: bool = False, concessions_df: pd.DataFrame = None) -> pd.DataFrame:
    df = df.copy()
    if rebate_dict is None: rebate_dict = {}
    
    # 1. Clean BNF data
    if 'bnf_code' not in df.columns: df['bnf_code'] = ''
    df['bnf_code'] = df['bnf_code'].fillna('').astype(str)
    df['bnf_chapter_code'] = df['bnf_code'].str[:2]
    df['therapeutic_group'] = df['bnf_chapter_code'].map(BNF_MAPPING).fillna('Unclassified')
    
    # 2. Units & Acquisition Costs (Strict)
    df['total_units_dispensed'] = df['pack_size'] * df['quantity_dispensed']
    df['actual_cost_per_unit'] = df['avg_unit_cost'] / df['invoice_pack_size']
    df['best_cost_per_unit'] = df['min_unit_cost'] / df['invoice_pack_size']
    df['acquisition_cost_gbp'] = df['total_units_dispensed'] * df['actual_cost_per_unit']
    df['benchmark_cost_gbp'] = df['total_units_dispensed'] * df['best_cost_per_unit']
    df['maverick_leakage_gbp'] = (df['acquisition_cost_gbp'] - df['benchmark_cost_gbp']).clip(lower=0)

    # 3. Dynamic Wholesaler Rebates
    supp_col = next((col for col in df.columns if col.lower() in ['supplier', 'wholesaler', 'supplier_name']), 'cheapest_supplier')
    df['rebate_pct'] = df[supp_col].map(rebate_dict).fillna(0.0) if supp_col in df.columns else rebate_dict.get('ALL', 0.0)
    df['wholesaler_rebate_gbp'] = df['acquisition_cost_gbp'] * (df['rebate_pct'] / 100.0)

    # 4. Drug Tariff Merge (Strict deduplication to prevent inflated sums)
    clean_tariff = tariff_df.drop_duplicates(subset=['dm_d_code', 'tariff_form'])
    df['effective_dm_d_code'] = np.where(df['dm_d_code'].replace('', pd.NA).notna(), df['dm_d_code'], df.get('matched_dm_d_code', ''))
    df = df.merge(clean_tariff, left_on=['effective_dm_d_code', 'form'], right_on=['dm_d_code', 'tariff_form'], how='left', suffixes=('', '_tariff'))

    # 5. Concessions & Reimbursement
    active_concessions = CONCESSIONS_MAPPING.copy()
    if concessions_df is not None and not concessions_df.empty:
        uploaded = dict(zip(concessions_df['dm_d_code'].astype(str), pd.to_numeric(concessions_df['concession_price'], errors='coerce').fillna(0.0)))
        active_concessions.update(uploaded)
            
    df['tariff_price_gbp'] = df['tariff_price_gbp'].fillna(0.0)
    df['concession_price_gbp'] = df['effective_dm_d_code'].map(active_concessions).fillna(0.0)
    df['final_reimbursement_price_gbp'] = np.maximum(df['tariff_price_gbp'], df['concession_price_gbp'])
    
    df['tariff_pack_size'] = df['tariff_pack_size'].replace(0, 1).fillna(1.0)
    df['tariff_per_unit'] = df['final_reimbursement_price_gbp'] / df['tariff_pack_size']
    df['gross_drug_reimbursed_gbp'] = df['total_units_dispensed'] * df['tariff_per_unit']
    
    # 6. Basic Price & Clawback
    total_ppa_claim = df['gross_drug_reimbursed_gbp'].sum()
    calc_basic_price = override_basic_price if override_basic_price is not None else total_ppa_claim
    dynamic_rate = get_clawback_rate(calc_basic_price)
    
    df['is_dnd'] = df['effective_dm_d_code'].isin(dnd_df['dm_d_code']) if 'dm_d_code' in dnd_df.columns else False
    df['clawback_rate'] = np.where(df['is_dnd'], 0.0, dynamic_rate)
    df['clawback_deduction_gbp'] = df['gross_drug_reimbursed_gbp'] * df['clawback_rate']
    df['net_drug_reimbursed_gbp'] = df['gross_drug_reimbursed_gbp'] - df['clawback_deduction_gbp']

    # 7. MDS & Profit
    df['mds_pct'] = df['effective_dm_d_code'].map(MDS_MAPPING).fillna(0.0) if mds_active else 0.0
    df['mds_rebate_gbp'] = df['acquisition_cost_gbp'] * (df['mds_pct'] / 100.0)
    df['total_rebates_gbp'] = df['wholesaler_rebate_gbp'] + df['mds_rebate_gbp']
    
    df['dispensing_fee_gbp'] = np.where(df['pa_flag'].str.upper() == 'Y', 0.0, get_dispensing_fee(len(df)))
    df['vat_allowance_gbp'] = np.where(df['pa_flag'].str.upper() == 'Y', df['net_drug_reimbursed_gbp'] * 0.20, 0.0)
    df['net_income_gbp'] = df['net_drug_reimbursed_gbp'] + df['dispensing_fee_gbp'] + df['vat_allowance_gbp']
    
    df['invoice_margin_gbp'] = df['net_income_gbp'] - df['acquisition_cost_gbp']
    df['margin_gbp'] = df['invoice_margin_gbp'] + df['total_rebates_gbp']
    
    # 8. VAT Audit
    df['is_known_pa'] = df['effective_dm_d_code'].isin(KNOWN_PA_DMD_CODES) | df['clean_drug_name'].str.contains('vaccine|injection|implant', case=False, na=False)
    df['lost_vat_gbp'] = np.where((df['is_known_pa']) & (df['pa_flag'].str.upper() != 'Y'), df['net_drug_reimbursed_gbp'] * 0.20, 0.0)

    # 9. Clinical Switches (Fixing missing switches)
    switch_data = df['effective_dm_d_code'].map(SWITCH_MAPPING)
    df['switch_type'] = switch_data.apply(lambda x: x['switch_type'] if isinstance(x, dict) else 'None')
    df['suggested_drug'] = switch_data.apply(lambda x: x['suggested_drug'] if isinstance(x, dict) else 'None')
    
    est_gen_reimb = switch_data.apply(lambda x: x['est_generic_reimbursement'] if isinstance(x, dict) else 0.0)
    est_gen_cost = switch_data.apply(lambda x: x['est_generic_cost'] if isinstance(x, dict) else 0.0)
    
    gen_net_cost = est_gen_cost * (1 - (df['rebate_pct'] / 100.0))
    gen_net_reimb = (est_gen_reimb * df['quantity_dispensed']) * (1 - dynamic_rate)
    df['est_generic_margin'] = (gen_net_reimb + df['dispensing_fee_gbp']) - (gen_net_cost * df['quantity_dispensed'])
    df['potential_savings_gbp'] = np.where(df['switch_type'] != 'None', (df['est_generic_margin'] - df['margin_gbp']).clip(lower=0), 0.0)

    # 10. Aggregation
    return df.groupby('effective_dm_d_code').agg(
        example_drug_description=('drug_description', 'first'),
        therapeutic_group=('therapeutic_group', 'first'),
        total_quantity_packs=('quantity_dispensed', 'sum'),
        gross_drug_reimbursed_gbp=('gross_drug_reimbursed_gbp', 'sum'),
        clawback_deduction_gbp=('clawback_deduction_gbp', 'sum'),
        net_drug_reimbursed_gbp=('net_drug_reimbursed_gbp', 'sum'),
        dispensing_fees_earned_gbp=('dispensing_fee_gbp', 'sum'),
        vat_allowance_gbp=('vat_allowance_gbp', 'sum'),
        lost_vat_gbp=('lost_vat_gbp', 'sum'),
        net_income_gbp=('net_income_gbp', 'sum'),
        acquisition_cost_gbp=('acquisition_cost_gbp', 'sum'),
        total_rebates_gbp=('total_rebates_gbp', 'sum'),
        maverick_leakage_gbp=('maverick_leakage_gbp', 'sum'),
        invoice_margin_gbp=('invoice_margin_gbp', 'sum'),
        margin_gbp=('margin_gbp', 'sum'),
        switch_type=('switch_type', 'first'),
        suggested_drug=('suggested_drug', 'first'),
        potential_savings_gbp=('potential_savings_gbp', 'sum'),
        locality_alignment=('key_drug', lambda x: switch_data.iloc[0].get('locality_alignment', 'Unclassified') if isinstance(switch_data.iloc[0], dict) else 'Unclassified'),
        incentive_scheme=('key_drug', lambda x: switch_data.iloc[0].get('incentive_scheme', 'N/A') if isinstance(switch_data.iloc[0], dict) else 'N/A'),
        applied_basic_price=('key_drug', lambda x: calc_basic_price),
        applied_clawback_rate=('key_drug', lambda x: dynamic_rate),
        applied_dispensing_fee=('key_drug', lambda x: get_dispensing_fee(len(df)))
    ).reset_index()