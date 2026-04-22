import pandas as pd
import random

# Top UK Primary Care Drugs for POC Demonstration
REAL_DRUGS = [
    # Mapped for Brand -> Generic Switches
    ("Lipitor 20mg tablets", "8058211000001101", "0212010B0", 28, 2464),
    ("Nexium 20mg gastro-resistant tablets", "11417011000001106", "0103050P0", 28, 1850),
    
    # Mapped for Therapeutic Switches
    ("Omeprazole 20mg gastro-resistant capsules", "17603511000001107", "0103050P0", 28, 120),
    ("Edoxaban 60mg tablets", "28572511000001104", "0208020AA", 28, 4900),
    
    # Standard Controls
    ("Atorvastatin 20mg tablets", "9474711000001109", "0212010B0", 28, 98),
    ("Ramipril 5mg capsules", "12140411000001101", "0205051R0", 28, 115),
    ("Amlodipine 5mg tablets", "14188111000001100", "0206020A0", 28, 88),
    ("Lansoprazole 30mg gastro-resistant capsules", "13768511000001107", "0103050L0", 28, 115),
    ("Sertraline 50mg tablets", "15152011000001109", "0403030Q0", 28, 140),
    ("Metformin 500mg tablets", "31782211000001102", "0601022B0", 84, 215),
    ("Amoxicillin 500mg capsules", "28246311000001109", "0501013B0", 21, 145)
]

# 1. Generate Dispensing File
disp_list = []
for i in range(100):
    drug = random.choice(REAL_DRUGS)
    med_name = drug[0]
    
    form = 'TAB'
    if 'capsule' in med_name.lower(): form = 'CAP'
    
    disp_list.append({
        'dispense_date': '2026-04-15',
        'drug_description': med_name,
        'dm_d_code': drug[1],
        'bnf_code': drug[2],
        'quantity_dispensed': random.randint(1, 12),
        'pack_size': drug[3],
        'form': form,
        'pa_flag': 'N'
    })
pd.DataFrame(disp_list).to_csv("mock_dispensing_100.csv", index=False)

# 2. Generate Invoice File 
inv_list = []
for drug in REAL_DRUGS:
    tariff_gbp = drug[4] / 100
    
    inv_list.append({
        'invoice_date': '2026-04-10',
        'dm_d_code': drug[1],
        'supplier_name': "AAH",
        'supplier_description': f"{drug[0]} {drug[3]}",
        'unit_cost_gbp': round(tariff_gbp * 0.85, 2), 
        'pack_size': drug[3]
    })
    
    inv_list.append({
        'invoice_date': '2026-04-12',
        'dm_d_code': drug[1],
        'supplier_name': "Alliance",
        'supplier_description': f"{drug[0]} {drug[3]}",
        'unit_cost_gbp': round(tariff_gbp * 0.95, 2), 
        'pack_size': drug[3]
    })
pd.DataFrame(inv_list).to_csv("mock_invoices_100.csv", index=False)

# 3. Generate Factual Tariff File 
tariff_list = []
for drug in REAL_DRUGS:
    tariff_list.append({
        'VMPP Snomed Code': drug[1],
        'Medicine': drug[0],
        'Basic Price': drug[4],
        'Pack Size': drug[3]
    })
pd.DataFrame(tariff_list).to_csv("Part VIIIA April 2026.csv", index=False)

print("Data generation complete. Clinical logic test dataset ready.")