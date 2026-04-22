import pandas as pd
import numpy as np

def normalise_dispensing(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    
    # Standardise SNOMED Codes
    df['dm_d_code'] = df['dm_d_code'].fillna('').astype(str).str.strip()
    df['dm_d_code'] = df['dm_d_code'].str.replace('.0', '', regex=False) 
    
    # Standardise Descriptions
    df['drug_description'] = df['drug_description'].fillna('').astype(str).str.strip()
    df['clean_drug_name'] = df['drug_description'].str.lower()
    
    # Formulation Extraction
    if 'form' not in df.columns:
        df['form'] = 'TAB' # Default to Tablet
        df.loc[df['drug_description'].str.contains('capsule', case=False), 'form'] = 'CAP'
        df.loc[df['drug_description'].str.contains('chewable', case=False), 'form'] = 'CHEW'
    
    # Defensive Date Check
    if 'dispense_date' not in df.columns:
        df['dispense_date'] = pd.Timestamp.now().strftime('%Y-%m-%d')
    df['dispense_date'] = pd.to_datetime(df['dispense_date'], errors='coerce')
    
    # Numeric Conversion
    df['pack_size'] = pd.to_numeric(df['pack_size'], errors='coerce')
    df['quantity_dispensed'] = pd.to_numeric(df['quantity_dispensed'], errors='coerce')
    
    # PA Flag Handling
    if 'pa_flag' in df.columns:
        df['pa_flag'] = df['pa_flag'].fillna('N').astype(str).str.upper().str.strip()
    else:
        df['pa_flag'] = 'N'
        
    return df

def normalise_invoices(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df['dm_d_code'] = df['dm_d_code'].fillna('').astype(str).str.strip()
    df['dm_d_code'] = df['dm_d_code'].str.replace('.0', '', regex=False)
    
    if 'invoice_date' not in df.columns:
        df['invoice_date'] = pd.Timestamp.now().strftime('%Y-%m-%d')
    df['invoice_date'] = pd.to_datetime(df['invoice_date'], errors='coerce')
    
    df['unit_cost_gbp'] = pd.to_numeric(df['unit_cost_gbp'], errors='coerce')
    df['pack_size'] = pd.to_numeric(df['pack_size'], errors='coerce')
    return df

def normalise_tariff(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    
    # 1. Clean Headers: Removes hidden spaces often found in NHSBSA CSV exports
    df.columns = df.columns.str.strip()
    
    # 2. Robust Rename: Handles 'Pack size' (official) vs 'Pack Size' (mock)
    df = df.rename(columns={
        'VMPP Snomed Code': 'dm_d_code',
        'Basic Price': 'tariff_price_pence',
        'Pack size': 'tariff_pack_size',
        'Pack Size': 'tariff_pack_size',
        'Medicine': 'tariff_medicine_name'
    })
    
    # 3. Security Check: Ensures the rename actually happened
    if 'dm_d_code' not in df.columns:
        # Check for VMP variant if VMPP isn't present
        if 'VMP Snomed Code' in df.columns:
            df = df.rename(columns={'VMP Snomed Code': 'dm_d_code'})
        else:
            raise KeyError("Tariff file is missing 'VMPP Snomed Code'. Check headers for spelling/spaces.")
    
    df['dm_d_code'] = df['dm_d_code'].fillna('').astype(str).str.strip()
    df['dm_d_code'] = df['dm_d_code'].str.replace('.0', '', regex=False)
    
    # 4. Formulation Extraction for Tariff
    df['tariff_form'] = 'TAB'
    if 'tariff_medicine_name' in df.columns:
        df['tariff_medicine_name'] = df['tariff_medicine_name'].fillna('').astype(str)
        # Search for capsule indicators
        cap_mask = df['tariff_medicine_name'].str.contains('capsule|cap ', case=False, regex=True)
        df.loc[cap_mask, 'tariff_form'] = 'CAP'
        df.loc[df['tariff_medicine_name'].str.contains('chewable', case=False), 'tariff_form'] = 'CHEW'
    
    # 5. Data Type Conversion
    df['tariff_price_gbp'] = pd.to_numeric(df['tariff_price_pence'], errors='coerce') / 100.0
    df['tariff_pack_size'] = pd.to_numeric(df['tariff_pack_size'], errors='coerce')
    
    return df[['dm_d_code', 'tariff_price_gbp', 'tariff_pack_size', 'tariff_form']]