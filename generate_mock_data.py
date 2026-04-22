import pandas as pd
import random

# (Name, dm+d, BNF, pack_size, tariff_pence, is_brand)
DRUG_LIBRARY = [
    # --- HIGH VALUE TARGETS (The "Hooks" in your SWITCH_MAPPING) ---
    ("Edoxaban 60mg tablets", "28572511000001104", "0208020AA", 28, 4900, True),
    ("Lipitor 20mg tablets", "8058211000001101", "0212010B0", 28, 2464, True),
    ("Nexium 20mg gastro-resistant tablets", "11417011000001106", "0103050P0", 28, 1850, True),
    
    # --- TOP VOLUME GENERICS ---
    ("Atorvastatin 20mg tablets", "9474711000001109", "0212010B0", 28, 98, False),
    ("Amlodipine 5mg tablets", "14188111000001100", "0206020A0", 28, 85, False),
    ("Omeprazole 20mg gastro-resistant capsules", "17603511000001107", "0103050P0", 28, 112, False),
    ("Lansoprazole 30mg gastro-resistant capsules", "13768511000001107", "0103050L0", 28, 115, False),
    ("Levothyroxine 50microgram tablets", "2201211000001104", "0602010V0", 28, 110, False),
    ("Ramipril 5mg capsules", "12140411000001101", "0205051R0", 28, 105, False),
    ("Bisoprolol 2.5mg tablets", "1157411000001105", "0204000C0", 28, 108, False),
    ("Sertraline 50mg tablets", "15152011000001109", "0403030Q0", 28, 135, False),
    ("Metformin 500mg tablets", "31782211000001102", "0601022B0", 84, 210, False),
    ("Salbutamol 100micrograms/dose inhaler", "3324011000001108", "0301011R0", 200, 150, False),
    ("Furosemide 40mg tablets", "1261511000001107", "0202020F0", 28, 92, False),
    ("Clopidogrel 75mg tablets", "14389111000001108", "0209000C0", 28, 125, False),
    ("Citalopram 20mg tablets", "14588111000001105", "0403030C0", 28, 118, False),
    ("Mirtazapine 30mg tablets", "15456111000001106", "0403030N0", 28, 350, False),
    ("Losartan 50mg tablets", "15132111000001106", "0205052M0", 28, 140, False),
    ("Amitriptyline 10mg tablets", "1172111000001102", "0403010A0", 28, 95, False),
    ("Aspirin 75mg dispersible tablets", "1182211000001108", "0209000A0", 28, 82, False),
    ("Co-codamol 30mg/500mg tablets", "18567111000001100", "0407010C0", 30, 245, False),
    ("Gabapentin 300mg capsules", "14920111000001101", "0408010G0", 100, 450, False),
    ("Nitrofurantoin 100mg m/r capsules", "15901111000001107", "0504030R0", 30, 520, False),
    ("Fluoxetine 20mg capsules", "14833111000001100", "0403030F0", 30, 155, False),
    ("Naproxen 250mg tablets", "15762111000001100", "1001010P0", 28, 195, False),
    ("Gliclazide 80mg tablets", "14954111000001109", "0601021L0", 28, 145, False)
]

# Dynamically fill to 100 drugs to ensure data density
while len(DRUG_LIBRARY) < 100:
    base = random.choice(DRUG_LIBRARY[3:]) 
    DRUG_LIBRARY.append((f"{base[0]} (Alt Dose)", base[1], base[2], base[3], base[4] + random.randint(-10, 10), False))

# 1. Generate Dispensing File (5000 items)
disp_list = []
for i in range(5000):
    # Weighting: 10% chance to pick a high-value branded switch
    if random.random() < 0.10:
        drug = random.choice(DRUG_LIBRARY[:3])
    else:
        drug = random.choice(DRUG_LIBRARY)
        
    disp_list.append({
        'dispense_date': '2026-04-15',
        'drug_description': drug[0],
        'dm_d_code': drug[1],
        'bnf_code': drug[2],
        'quantity_dispensed': random.randint(1, 2),
        'pack_size': drug[3],
        'form': 'TAB' if 'tablet' in drug[0].lower() else 'CAP',
        'pa_flag': 'N'
    })
pd.DataFrame(disp_list).to_csv("mock_dispensing_5000.csv", index=False)

# 2. Generate Invoice File
inv_list = []
for drug in DRUG_LIBRARY:
    tariff_gbp = drug[4] / 100
    # Branded items MUST have zero discount to trigger clawback losses in the engine
    unit_cost = tariff_gbp if drug[5] else tariff_gbp * random.uniform(0.72, 0.88)
    
    inv_list.append({
        'invoice_date': '2026-04-10',
        'dm_d_code': drug[1],
        'supplier_name': "AAH",
        'supplier_description': drug[0],
        'unit_cost_gbp': round(unit_cost, 2),
        'pack_size': drug[3],
        'invoice_pack_size': drug[3],
        'min_unit_cost': round(unit_cost * 0.95, 2),
        'avg_unit_cost': round(unit_cost, 2)
    })
pd.DataFrame(inv_list).to_csv("mock_invoices_5000.csv", index=False)

# 3. Generate Tariff File
tariff_list = []
for drug in DRUG_LIBRARY:
    tariff_list.append({
        'dm_d_code': drug[1],
        'tariff_drug': drug[0],
        'tariff_price_gbp': drug[4] / 100,
        'tariff_pack_size': drug[3],
        'tariff_form': 'TAB' if 'tablet' in drug[0].lower() else 'CAP'
    })
pd.DataFrame(tariff_list).to_csv("Part VIIIA April 2026.csv", index=False)
