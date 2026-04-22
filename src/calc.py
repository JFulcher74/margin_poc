import pandas as pd
import numpy as np
from src.utils import get_worst_confidence

# Comprehensive UK BNF Chapter Mapping (First 2 digits)
BNF_MAPPING = {
    '01': 'Gastro-Intestinal System',
    '02': 'Cardiovascular System',
    '03': 'Respiratory System',
    '04': 'Central Nervous System',
    '05': 'Infections',
    '06': 'Endocrine System',
    '07': 'Obstetrics, Gynaecology & Urinary',
    '08': 'Malignant Disease & Immunosuppression',
    '09': 'Nutrition & Blood',
    '10': 'Musculoskeletal & Joint Diseases',
    '11': 'Eye',
    '12': 'Ear, Nose & Oropharynx',
    '13': 'Skin'
}

# Consolidated Clinical & Financial Switch Engine
SWITCH_MAPPING = {
    # Therapeutic Switches (Generic to Generic)
    '17603511000001107': { # Omeprazole 20mg capsules
        'switch_type': 'Therapeutic Switch',
        'suggested_drug': 'Lansoprazole 30mg capsules',
        'est_generic_cost': 0.85, 'est_generic_reimbursement': 1.15,
        'clinical_rationale': 'Equipotent PPI therapy for acid suppression. Lansoprazole currently yields a higher net dispensing margin under Category M.',
        'reference_source': 'Local ICB Formulary',
        'clinical_link': 'https://bnf.nice.org.uk/treatment-summaries/proton-pump-inhibitors/'
    },
    '28572511000001104': { # Edoxaban 60mg tablets
        'switch_type': 'Therapeutic Switch',
        'suggested_drug': 'Apixaban 5mg tablets',
        'est_generic_cost': 2.10, 'est_generic_reimbursement': 2.25,
        'clinical_rationale': 'Both are effective DOACs for stroke prevention in non-valvular AF. Apixaban availability offers a superior generic margin profile.',
        'reference_source': 'BNF / NICE NG196',
        'clinical_link': 'https://bnf.nice.org.uk/treatment-summaries/anticoagulants-oral/'
    },
    
    # Brand to Generic Switches
    '8058211000001101': { # Lipitor 20mg tablets (Brand)
        'switch_type': 'Generic Switch',
        'suggested_drug': 'Atorvastatin 20mg tablets (Category M)',
        'est_generic_cost': 0.75, 'est_generic_reimbursement': 0.98,
        'clinical_rationale': 'Direct molecular equivalent. Eliminates branded prescribing leakage and aligns with primary care formulary guidance.',
        'reference_source': 'NICE CG71',
        'clinical_link': 'https://bnf.nice.org.uk/drugs/atorvastatin/'
    },
    '11417011000001106': { # Nexium 20mg tablets (Brand)
        'switch_type': 'Generic Switch',
        'suggested_drug': 'Esomeprazole 20mg tablets (Category M)',
        'est_generic_cost': 1.12, 'est_generic_reimbursement': 1.45,
        'clinical_rationale': 'Direct molecular equivalent.',
        'reference_source': 'BNF',
        'clinical_link': 'https://bnf.nice.org.uk/drugs/esomeprazole/'
    }
}

# Simulated NHSBSA Price Concessions
CONCESSIONS_MAPPING = {
    '11417011000001106': 22.50, # Nexium 20mg 
    '28246311000001109': 4.50,  # Amoxicillin 500mg
    '15152011000001109': 8.20,  # Sertraline 50mg
    '14188111000001100': 3.10   # Amlodipine 5mg
}

def calculate_metrics(df: pd.DataFrame, tariff_df: pd.DataFrame, dnd_df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    
    # 1. BNF Mapping
    if 'bnf_code' not in df.columns:
        df['bnf_code'] = ''
    df['bnf_code'] = df['bnf_code'].fillna('').astype(str)
    
    df['bnf_chapter_code'] = df['bnf_code'].str[:2]
    df['therapeutic_group'] = df['bnf_chapter_code'].map(BNF_MAPPING).fillna('Unclassified / Other')
    
    # 2. Units
    df['total_units_dispensed'] = df['pack_size'] * df['quantity_dispensed']
    
    # 3. Acquisition Cost & Maverick Leakage
    df['actual_cost_per_unit'] = df['avg_unit_cost'] / df['invoice_pack_size']
    df['best_cost_per_unit'] = df['min_unit_cost'] / df['invoice_pack_size']
    
    df['acquisition_cost_gbp'] = df['total_units_dispensed'] * df['actual_cost_per_unit']
    df['benchmark_cost_gbp'] = df['total_units_dispensed'] * df['best_cost_per_unit']
    df['acquisition_cost_gbp'] = df['acquisition_cost_gbp'].fillna(0.0)
    
    df['maverick_leakage_gbp'] = df['acquisition_cost_gbp'] - df['benchmark_cost_gbp']
    df['maverick_leakage_gbp'] = df['maverick_leakage_gbp'].apply(lambda x: x if x > 0.01 else 0.0)
    
    # 4. Effective dm+d Code
    df['effective_dm_d_code'] = np.where(
        df['dm_d_code'].replace('', pd.NA).notna(),
        df['dm_d_code'],
        df['matched_dm_d_code']
    )
    
    # 5. Tariff Merge
    df = df.merge(
        tariff_df, 
        left_on=['effective_dm_d_code', 'form'], 
        right_on=['dm_d_code', 'tariff_form'], 
        how='left', 
        suffixes=('', '_tariff')
    )
    
    # 6. Concession Guard Logic
    df['concession_price_gbp'] = df['effective_dm_d_code'].map(CONCESSIONS_MAPPING).fillna(0.0)
    df['tariff_price_gbp'] = df['tariff_price_gbp'].fillna(0.0)
    
    df['final_reimbursement_price_gbp'] = np.maximum(df['tariff_price_gbp'], df['concession_price_gbp'])
    
    df['concession_uplift_gbp'] = np.where(
        df['concession_price_gbp'] > df['tariff_price_gbp'],
        ((df['concession_price_gbp'] - df['tariff_price_gbp']) / df['tariff_pack_size']) * df['total_units_dispensed'],
        0.0
    )
    
    # 7. Reimbursement
    df['tariff_per_unit'] = df['final_reimbursement_price_gbp'] / df['tariff_pack_size']
    df['gross_drug_reimbursed_gbp'] = df['total_units_dispensed'] * df['tariff_per_unit']
    df['gross_drug_reimbursed_gbp'] = df['gross_drug_reimbursed_gbp'].fillna(0.0)
    
    # 8. Clawback
    df['is_dnd'] = df['effective_dm_d_code'].isin(dnd_df['dm_d_code'])
    df['clawback_rate'] = np.where(df['is_dnd'], 0.0, 0.1118)
    df['clawback_deduction_gbp'] = df['gross_drug_reimbursed_gbp'] * df['clawback_rate']
    df['net_drug_reimbursed_gbp'] = df['gross_drug_reimbursed_gbp'] - df['clawback_deduction_gbp']
    
    # 9. Fees & VAT
    df['dispensing_fee_gbp'] = np.where(df['pa_flag'] == 'Y', 0.0, 2.18)
    df['vat_allowance_gbp'] = np.where(df['pa_flag'] == 'Y', df['net_drug_reimbursed_gbp'] * 0.20, 0.0)
    
    # 10. Net Income & Margin
    df['net_income_gbp'] = df['net_drug_reimbursed_gbp'] + df['dispensing_fee_gbp'] + df['vat_allowance_gbp']
    df['margin_gbp'] = df['net_income_gbp'] - df['acquisition_cost_gbp']

    df['key_drug'] = np.where(
        df['effective_dm_d_code'].replace('', pd.NA).notna(),
        df['effective_dm_d_code'],
        df['clean_drug_name']
    )

    # 11. Switch Logic
    switch_data = df['effective_dm_d_code'].map(SWITCH_MAPPING)
    df['switch_type'] = switch_data.apply(lambda x: x['switch_type'] if isinstance(x, dict) else 'None')
    df['suggested_drug'] = switch_data.apply(lambda x: x['suggested_drug'] if isinstance(x, dict) else 'None')
    df['est_generic_cost'] = switch_data.apply(lambda x: x['est_generic_cost'] if isinstance(x, dict) else 0.0)
    df['est_generic_reimb'] = switch_data.apply(lambda x: x['est_generic_reimbursement'] if isinstance(x, dict) else 0.0)
    df['clinical_rationale'] = switch_data.apply(lambda x: x.get('clinical_rationale', '') if isinstance(x, dict) else '')
    df['reference_source'] = switch_data.apply(lambda x: x.get('reference_source', '') if isinstance(x, dict) else '')
    df['clinical_link'] = switch_data.apply(lambda x: x.get('clinical_link', '') if isinstance(x, dict) else '')

    est_generic_clawback = df['est_generic_reimb'] * df['quantity_dispensed'] * 0.1118
    est_generic_net_reimb = (df['est_generic_reimb'] * df['quantity_dispensed']) - est_generic_clawback
    est_generic_income = est_generic_net_reimb + df['dispensing_fee_gbp'] 
    est_generic_total_cost = df['est_generic_cost'] * df['quantity_dispensed']
    
    df['est_generic_margin'] = est_generic_income - est_generic_total_cost
    
    df['potential_savings_gbp'] = np.where(
        df['switch_type'] != 'None',
        df['est_generic_margin'] - df['margin_gbp'],
        0.0
    )
    df['potential_savings_gbp'] = np.where(df['potential_savings_gbp'] > 0, df['potential_savings_gbp'], 0.0)

    # 12. Aggregate
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
        net_income_gbp=('net_income_gbp', 'sum'),
        acquisition_cost_gbp=('acquisition_cost_gbp', 'sum'),
        maverick_leakage_gbp=('maverick_leakage_gbp', 'sum'),
        supplier_variance=('supplier_variance', 'first'),
        cheapest_supplier=('cheapest_supplier', 'first'),
        margin_gbp=('margin_gbp', 'sum'),
        switch_type=('switch_type', 'first'),
        suggested_drug=('suggested_drug', 'first'),
        clinical_rationale=('clinical_rationale', 'first'),
        reference_source=('reference_source', 'first'),
        clinical_link=('clinical_link', 'first'),
        potential_savings_gbp=('potential_savings_gbp', 'sum'),
        confidence_list=('confidence', list)
    ).reset_index()

    grouped['confidence'] = grouped['confidence_list'].apply(get_worst_confidence)
    grouped.drop(columns=['confidence_list'], inplace=True)

    return grouped