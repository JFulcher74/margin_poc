import pandas as pd
import numpy as np
import random
from datetime import datetime, timedelta

def generate_targeted_poc_data():
    catalog = [
        # Clinical Switches (Triggers £6k target)
        {"dm_d_code": "17603511000001107", "desc": "Esomeprazole 20mg gastro-resistant capsules", "pack": 28, "tariff": 2.21, "pa": 0, "weight": 60},
        {"dm_d_code": "28572511000001104", "desc": "Rivaroxaban 20mg tablets", "pack": 28, "tariff": 36.00, "pa": 0, "weight": 120},
        {"dm_d_code": "8058211000001101", "desc": "Lipitor 20mg tablets", "pack": 28, "tariff": 12.00, "pa": 0, "weight": 40},

        # Concessions
        {"dm_d_code": "28246311000001109", "desc": "Aripiprazole 10mg tablets", "pack": 28, "tariff": 1.50, "pa": 0, "weight": 50},
        {"dm_d_code": "14188111000001100", "desc": "Felodipine 5mg modified-release tablets", "pack": 28, "tariff": 0.95, "pa": 0, "weight": 50},

        # Personally Administered (Triggers £4k VAT loss)
        {"dm_d_code": "1411111000001103", "desc": "Zoladex 10.8mg implant", "pack": 1, "tariff": 235.00, "pa": 1, "weight": 15},
        {"dm_d_code": "10862711000001106", "desc": "Depo-Provera 150mg/1ml injection", "pack": 1, "tariff": 6.50, "pa": 1, "weight": 50},
        {"dm_d_code": "3371911000001104", "desc": "Nexplanon 68mg implant", "pack": 1, "tariff": 85.00, "pa": 1, "weight": 20},
        {"dm_d_code": "20534211000001109", "desc": "Denosumab 60mg/1ml solution for injection pre-filled syringes", "pack": 1, "tariff": 183.00, "pa": 1, "weight": 15},

        # High Volume UK Generics
        {"dm_d_code": "1271511000001104", "desc": "Atorvastatin 20mg tablets", "pack": 28, "tariff": 0.61, "pa": 0, "weight": 400},
        {"dm_d_code": "995011000001102", "desc": "Amlodipine 5mg tablets", "pack": 28, "tariff": 0.55, "pa": 0, "weight": 350},
        {"dm_d_code": "1057211000001103", "desc": "Omeprazole 20mg gastro-resistant capsules", "pack": 28, "tariff": 0.60, "pa": 0, "weight": 300},
        {"dm_d_code": "1199511000001105", "desc": "Levothyroxine sodium 50microgram tablets", "pack": 28, "tariff": 0.65, "pa": 0, "weight": 250},
        {"dm_d_code": "5011011000001107", "desc": "Ramipril 5mg capsules", "pack": 28, "tariff": 0.74, "pa": 0, "weight": 200},
        {"dm_d_code": "1320811000001101", "desc": "Metformin 500mg tablets", "pack": 28, "tariff": 0.55, "pa": 0, "weight": 200},
        {"dm_d_code": "1064711000001107", "desc": "Paracetamol 500mg tablets", "pack": 32, "tariff": 0.61, "pa": 0, "weight": 150},
        {"dm_d_code": "1111111000001101", "desc": "Sertraline 50mg tablets", "pack": 28, "tariff": 1.20, "pa": 0, "weight": 150}
    ]

    total_items = 20000
    start_date = datetime.strptime("2026-03-01", "%Y-%m-%d")
    
    weights = np.array([item["weight"] for item in catalog])
    weights = weights / weights.sum()
    
    dispensing_data = []
    
    target_vat_loss = 4000
    accumulated_vat_loss = 0
    
    for _ in range(total_items):
        drug = np.random.choice(catalog, p=weights)
        
        # CORRECTED PA FLAG LOGIC
        pa_flag = "N"
        if drug["pa"] == 1:
            pa_flag = "Y"
            vat_value = drug["tariff"] * 0.20
            # Force VAT errors until we hit the £4k target
            if accumulated_vat_loss < target_vat_loss and random.random() < 0.60:
                pa_flag = "N"
                accumulated_vat_loss += vat_value
            
        dispense_date = start_date + timedelta(days=random.randint(0, 30))
        dispensing_data.append({
            "dispense_date": dispense_date.strftime("%Y-%m-%d"),
            "dm_d_code": drug["dm_d_code"],
            "drug_description": drug["desc"],
            "pack_size": drug["pack"],
            "quantity_dispensed": 1, 
            "pa_flag": pa_flag
        })
        
    disp_df = pd.DataFrame(dispensing_data).sort_values("dispense_date")
    
    invoices = []
    suppliers = ["AAH Pharmaceuticals", "Alliance Healthcare", "Phoenix Healthcare"]
    volume_summary = disp_df.groupby("dm_d_code")["quantity_dispensed"].sum().reset_index()
    
    target_waste = 8000
    accumulated_waste = 0
    invoice_id = 10000
    
    for _, row in volume_summary.iterrows():
        drug = next(item for item in catalog if item["dm_d_code"] == row["dm_d_code"])
        total_packs_needed = int(np.ceil(row["quantity_dispensed"] * 1.05))
        
        # Calculate optimal baseline cost to guarantee the overall practice gross profit
        income = drug["tariff"] - (drug["tariff"] * 0.1118) + 2.19
        optimal_cost = income - 4.00
        if optimal_cost < (drug["tariff"] * 0.40):
            optimal_cost = drug["tariff"] * 0.40
        
        deliveries = random.randint(1, 4)
        packs_per_delivery = max(1, total_packs_needed // deliveries)
        
        for _ in range(deliveries):
            supplier = random.choice(suppliers)
            invoice_id += random.randint(1, 5)
            inv_date = start_date + timedelta(days=random.randint(0, 30))
            
            unit_price = optimal_cost
            
            # Force procurement waste until we hit the £8k target
            if drug["pa"] == 0 and accumulated_waste < target_waste and random.random() < 0.35:
                surcharge = random.uniform(0.50, 3.00)
                unit_price = drug["tariff"] + surcharge
                waste_generated = (unit_price - optimal_cost) * packs_per_delivery
                accumulated_waste += waste_generated

            invoices.append({
                "invoice_date": inv_date.strftime("%Y-%m-%d"),
                "invoice_number": f"INV-{invoice_id}",
                "supplier_name": supplier,
                "dm_d_code": drug["dm_d_code"],
                "supplier_description": drug["desc"],
                "pack_size": drug["pack"],
                "packs_purchased": packs_per_delivery,
                "unit_cost_gbp": round(unit_price, 2)
            })
            
    inv_df = pd.DataFrame(invoices).sort_values("invoice_date")
    
    disp_df.to_csv("mock_dispensing_20k.csv", index=False)
    inv_df.to_csv("mock_invoices_20k.csv", index=False)

if __name__ == "__main__":
    generate_targeted_poc_data()
