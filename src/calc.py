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
    
    # Defensive column check
    for expected_col in ['avg_unit_cost', 'invoice_pack_size', 'min_unit_cost']:
        if expected_col not in df.columns:
            df[expected_col] = 0.0
            
    if 'bnf_code' not in df.columns: df['bnf_code'] = ''
    df['bnf_code'] = df['bnf_code'].fillna('').astype(str)
    df['bnf_chapter_code'] = df['bnf_code'].str[:2]
    df['therapeutic_group'] = df['bnf_chapter_code'].map(BNF_MAPPING).fillna('Unclassified / Other')
    
    df['total_units_dispensed'] = df['pack_size'] * df['quantity_dispensed']
    
    # Use np.where to prevent division by zero errors safely
    df['actual_cost_per_unit'] = np.where(df['invoice_pack_size'] > 0, df['avg_unit_cost'] / df['invoice_pack_size'], 0.0)
    df['best_cost_per_unit'] = np.where(df['invoice_pack_size'] > 0, df['min_unit_cost'] / df['invoice_pack_size'], 0.0)
    
    df['acquisition_cost_gbp'] = df['total_units_dispensed'] * df['actual_cost_per_unit']
    df['benchmark_cost_gbp'] = df['total_units_dispensed'] * df['best_cost_per_unit']
    df['acquisition_cost_gbp'] = df['acquisition_cost_gbp'].fillna(0.0)
    df['maverick_leakage_gbp'] = df['acquisition_cost_gbp'] - df['benchmark_cost_gbp']
    df['maverick_leakage_gbp'] = df['maverick_leakage_gbp'].apply(lambda x: x if x > 0.01 else 0.0)
    
    supp_col = next((col for col in df.columns if col.lower() in ['supplier', 'wholesaler', 'supplier_name', 'cheapest_supplier']), None)
    if supp_col:
        df['rebate_pct'] = df[supp_col].map(rebate_dict).fillna(0.0)
    else:
        df['rebate_pct'] = rebate_dict.get('ALL', 0.0)
        
    df['wholesaler_rebate_gbp'] = df['acquisition_cost_gbp'] * (df['rebate_pct'] / 100.0)
    
    df['effective_dm_d_code'] = np.where(df['dm_d_code'].replace('', pd.NA).notna(), df['dm_d_code'], df.get('matched_dm_d_code', ''))
    df = df.merge(tariff_df, left_on=['effective_dm_d_code', 'form'], right_on=['dm_d_code', 'tariff_form'], how='left', suffixes=('', '_tariff'))
    
    if mds_active:
        df['mds_pct'] = df['effective_dm_d_code'].map(MDS_MAPPING).fillna(0.0)
    else:
        df['mds_pct'] = 0.0
        
    df['mds_rebate_gbp'] = df['acquisition_cost_gbp'] * (df['mds_pct'] / 100.0)
    
    df['total_rebates_gbp'] = df['wholesaler_rebate_gbp'] + df['mds_rebate_gbp']
    df['net_acquisition_cost_gbp'] = df['acquisition_cost_gbp'] - df['total_rebates_gbp']
    
    active_concessions = CONCESSIONS_MAPPING.copy()
    if concessions_df is not None and not concessions_df.empty:
        if 'dm_d_code' in concessions_df.columns and 'concession_price' in concessions_df.columns:
            uploaded_concessions = dict(zip(concessions_df['dm_d_code'].astype(str), pd.to_numeric(concessions_df['concession_price'], errors='coerce').fillna(0.0)))
            active_concessions.update(uploaded_concessions)
            
    df['concession_price_gbp'] = df['effective_dm_d_code'].map(active_concessions).fillna(0.0)
    
    # Safe fillna for merged columns
    if 'tariff_price_gbp' not in df.columns: df['tariff_price_gbp'] = 0.0
    if 'tariff_pack_size' not in df.columns: df['tariff_pack_size'] = 1.0
    
    df['tariff_price_gbp'] = df['tariff_price_gbp'].fillna(0.0)
    df['tariff_pack_size'] = df['tariff_pack_size'].fillna(1.0)
    
    df['final_reimbursement_price_gbp'] = np.maximum(df['tariff_price_gbp'], df['concession_price_gbp'])
    df['concession_uplift_gbp'] = np.where(df['concession_price_gbp'] > df['tariff_price_gbp'], ((df['concession_price_gbp'] - df['tariff_price_gbp']) / df['tariff_pack_size']) * df['total_units_dispensed'], 0.0)
    
    df['tariff_per_unit'] = df['final_reimbursement_price_gbp'] / df['tariff_pack_size']
    df['gross_drug_reimbursed_gbp'] = df['total_units_dispensed'] * df['tariff_per_unit']
    df['gross_drug_reimbursed_gbp'] = df['gross_drug_reimbursed_gbp'].fillna(0.0)
    
    calc_basic_price = override_basic_price if override_basic_price is not None else df['gross_drug_reimbursed_gbp'].sum()
    dynamic_rate = get_clawback_rate(calc_basic_price)
    
    df['is_dnd'] = df['effective_dm_d_code'].isin(dnd_df['dm_d_code']) if 'dm_d_code' in dnd_df.columns else False
    df['clawback_rate'] = np.where(df['is_dnd'], 0.0, dynamic_rate)
    df['clawback_deduction_gbp'] = df['gross_drug_reimbursed_gbp'] * df['clawback_rate']
    df['net_drug_reimbursed_gbp'] = df['gross_drug_reimbursed_gbp'] - df['clawback_deduction_gbp']
    
    if 'pa_flag' not in df.columns:
        df['pa_flag'] = 'N'
    df['pa_flag'] = df['pa_flag'].fillna('N').str.upper()
    
    if 'clean_drug_name' not in df.columns:
        df['clean_drug_name'] = ''
        
    df['is_known_pa'] = df['effective_dm_d_code'].isin(KNOWN_PA_DMD_CODES) | df['clean_drug_name'].str.contains('vaccine|injection|implant|zoladex|depo-provera', case=False, na=False)
    df['missed_pa_claim'] = df['is_known_pa'] & (df['pa_flag'] != 'Y')
    
    total_prescriptions = len(df)
    dynamic_fee = get_dispensing_fee(total_prescriptions)
    
    df['dispensing_fee_gbp'] = np.where(df['pa_flag'] == 'Y', 0.0, dynamic_fee)
    df['vat_allowance_gbp'] = np.where(df['pa_flag'] == 'Y', df['net_drug_reimbursed_gbp'] * 0.20, 0.0)
    df['lost_vat_gbp'] = np.where(df['missed_pa_claim'], df['net_drug_reimbursed_gbp'] * 0.20, 0.0)
    
    df['net_income_gbp'] = df['net_drug_reimbursed_gbp'] + df['dispensing_fee_gbp'] + df['vat_allowance_gbp']
    
    df['invoice_margin_gbp'] = df['net_income_gbp'] - df['acquisition_cost_gbp']
    df['margin_gbp'] = df['invoice_margin_gbp'] + df['total_rebates_gbp'] 
    
    df['key_drug'] = np.where(df['effective_dm_d_code'].replace('', pd.NA).notna(), df['effective_dm_d_code'], df['clean_drug_name'])

    switch_data = df['effective_dm_d_code'].map(SWITCH_MAPPING)
    df['switch_type'] = switch_data.apply(lambda x: x['switch_type'] if isinstance(x, dict) else 'None')
    df['suggested_drug'] = switch_data.apply(lambda x: x['suggested_drug'] if isinstance(x, dict) else 'None')
    df['est_generic_cost'] = switch_data.apply(lambda x: x['est_generic_cost'] if isinstance(x, dict) else 0.0)
    df['est_generic_reimb'] = switch_data.apply(lambda x: x['est_generic_reimbursement'] if isinstance(x, dict) else 0.0)
    
    df['est_generic_net_cost'] = df['est_generic_cost'] * (1 - (df['rebate_pct'] / 100.0))
    
    est_generic_clawback = df['est_generic_reimb'] * df['quantity_dispensed'] * dynamic_rate
    est_generic_net_reimb = (df['est_generic_reimb'] * df['quantity_dispensed']) - est_generic_clawback
    est_generic_income = est_generic_net_reimb + df['dispensing_fee_gbp'] 
    
    est_generic_total_cost = df['est_generic_net_cost'] * df['quantity_dispensed']
    df['est_generic_margin'] = est_generic_income - est_generic_total_cost
    
    df['potential_savings_gbp'] = np.where(df['switch_type'] != 'None', df['est_generic_margin'] - df['margin_gbp'], 0.0)
    df['potential_savings_gbp'] = np.where(df['potential_savings_gbp'] > 0, df['potential_savings_gbp'], 0.0)
    
    df['clinical_rationale'] = switch_data.apply(lambda x: x.get('clinical_rationale', '') if isinstance(x, dict) else '')
    df['reference_source'] = switch_data.apply(lambda x: x.get('reference_source', '') if isinstance(x, dict) else '')
    df['clinical_link'] = switch_data.apply(lambda x: x.get('clinical_link', '') if isinstance(x, dict) else '')
    df['clinical_effort'] = switch_data.apply(lambda x: x.get('clinical_effort', 'Uncategorised') if isinstance(x, dict) else 'Uncategorised')
    df['mds_warning'] = switch_data.apply(lambda x: x.get('mds_warning', False) if isinstance(x, dict) else False)
    df['locality_alignment'] = switch_data.apply(lambda x: x.get('locality_alignment', 'Unclassified') if isinstance(x, dict) else 'Unclassified')
    df['incentive_scheme'] = switch_data.apply(lambda x: x.get('incentive_scheme', 'N/A') if isinstance(x, dict) else 'N/A')

    # Final guarantee that all required output columns exist before grouping
    if 'supplier_variance' not in df.columns: df['supplier_variance'] = 0.0
    if 'cheapest_supplier' not in df.columns: df['cheapest_supplier'] = 'Unknown'
    if 'drug_description' not in df.columns: df['drug_description'] = df['clean_drug_name']

    grouped = df.groupby('key_drug').agg(
        example_drug_description=('drug_description', 'first'),
        therapeutic_group=('therapeutic_group', 'first'),
        total_quantity_packs=('quantity_dispensed', 'sum'),
        gross_drug_reimbursed_gbp=('gross_drug_reimbursed_gbp', 'sum'),
        concession_uplift_gbp=('concession_uplift_gbp', 'sum'),
        clawback_deduction_gbp=('clawback_deduction_gbp', 'sum'),
        net_drug_reimbursed_gbp=('net_drug_reimbursed_gbp', 'sum'),
        dispensing_fees_earned_gbp=('dispensing_fee_gbp', 'sum'),
        vat_allowance_gbp=('vat_allowance_gbp', 'sum'),
        lost_vat_gbp=('lost_vat_gbp', 'sum'),
        missed_pa_claim=('missed_pa_claim', 'max'),
        net_income_gbp=('net_income_gbp', 'sum'),
        acquisition_cost_gbp=('acquisition_cost_gbp', 'sum'),
        wholesaler_rebate_gbp=('wholesaler_rebate_gbp', 'sum'),
        mds_rebate_gbp=('mds_rebate_gbp', 'sum'),
        total_rebates_gbp=('total_rebates_gbp', 'sum'),
        net_acquisition_cost_gbp=('net_acquisition_cost_gbp', 'sum'),
        maverick_leakage_gbp=('maverick_leakage_gbp', 'sum'),
        supplier_variance=('supplier_variance', 'first'),
        cheapest_supplier=('cheapest_supplier', 'first'),
        invoice_margin_gbp=('invoice_margin_gbp', 'sum'),
        margin_gbp=('margin_gbp', 'sum'),
        switch_type=('switch_type', 'first'),
        suggested_drug=('suggested_drug', 'first'),
        clinical_rationale=('clinical_rationale', 'first'),
        reference_source=('reference_source', 'first'),
        clinical_link=('clinical_link', 'first'),
        clinical_effort=('clinical_effort', 'first'),
        mds_warning=('mds_warning', 'first'),
        locality_alignment=('locality_alignment', 'first'),
        incentive_scheme=('incentive_scheme', 'first'),
        potential_savings_gbp=('potential_savings_gbp', 'sum'),
        confidence_list=('confidence', list) if 'confidence' in df.columns else ('key_drug', lambda x: [1.0])
    ).reset_index()

    grouped['confidence'] = grouped['confidence_list'].apply(get_worst_confidence) if 'confidence_list' in grouped.columns else 1.0
    if 'confidence_list' in grouped.columns:
        grouped.drop(columns=['confidence_list'], inplace=True)
    
    grouped['applied_basic_price'] = calc_basic_price
    grouped['applied_clawback_rate'] = dynamic_rate
    grouped['applied_dispensing_fee'] = dynamic_fee

    return grouped