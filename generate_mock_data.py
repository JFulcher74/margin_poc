import pandas as pd
import numpy as np
import random
from datetime import datetime, timedelta

def build_drug_catalog():
    """Generates a realistic catalogue of ~145 UK Primary Care Drugs."""
    catalog = []
    
    # Standard Generics (Base Name, Base Price)
    generics = [
        ("Atorvastatin", 1.05), ("Omeprazole", 0.90), ("Amlodipine", 0.85),
        ("Ramipril", 1.20), ("Metformin", 1.50), ("Levothyroxine", 0.95),
        ("Bisoprolol", 1.10), ("Sertraline", 1.30), ("Lansoprazole", 1.15),
        ("Losartan", 1.40), ("Citalopram", 1.25), ("Simvastatin", 0.90),
        ("Clopidogrel", 1.45), ("Fluoxetine", 1.15), ("Naproxen", 1.80),
        ("Pregabalin", 2.10), ("Gabapentin", 2.20), ("Amitriptyline", 1.05)
    ]
    
    # Expand generics by dosage
    dmd_counter = 3970001100000000
    for name, price in generics:
        for dose, multiplier in [("10mg", 1.0), ("20mg", 1.2), ("40mg", 1.8), ("80mg", 2.5)]:
            dmd_counter += 17
            catalog.append({
                "Drug_Name": f"{name} {dose} tablets",
                "dmd_Code": str(dmd_counter),
                "Tariff_Price": round(price * multiplier, 2),
                "Pack_Size": 28,
                "Is_PA": 0,
                "Category": "Generic"
            })

    # High Cost & Branded Items
    speciality = [
        ("Apixaban 5mg tablets", 26.50, 56),
        ("Rivaroxaban 20mg tablets", 36.00, 28),
        ("Edoxaban 60mg tablets", 40.00, 28),
        ("Fostair 100/6 dose inhaler", 29.32, 1),
        ("Symbicort 200/6 Turbohaler", 38.00, 1),
        ("Captopril 50mg tablets", 38.50, 56), # Volatile Concession
        ("Domperidone 1mg/ml suspension", 92.00, 1) # Volatile Concession
    ]
    for name, price, pack in speciality:
        dmd_counter += 17
        catalog.append({
            "Drug_Name": name, "dmd_Code": str(dmd_counter),
            "Tariff_Price": price, "Pack_Size": pack,
            "Is_PA": 0, "Category": "Branded"
        })

    # Personally Administered (PA) Items
    pa_items = [
        ("Hydroxocobalamin 1mg/1ml injection", 12.50, 1), # B12
        ("Zoladex 10.8mg implant", 235.00, 1),
        ("Zoladex 3.6mg implant", 70.00, 1),
        ("Depo-Provera 150mg/1ml injection", 6.50, 1),
        ("Nexplanon 68mg implant", 85.00, 1),
        ("Pneumococcal vaccine", 10.00, 1),
        ("Denosumab 60mg/1ml injection", 183.00, 1)
    ]
    for name, price, pack in pa_items:
        dmd_counter += 17
        catalog.append({
            "Drug_Name": name, "dmd_Code": str(dmd_counter),
            "Tariff_Price": price, "Pack_Size": pack,
            "Is_PA": 1, "Category": "PA"
        })

    return pd.DataFrame(catalog)

def generate_dispensing_data(catalog_df, total_items=20000, month_year="2026-03"):
    data = []
    start_date = datetime.strptime(f"{month_year}-01", "%Y-%m-%d")
    
    # Create weighted probabilities (Generics 80%, Branded 12%, PA 8%)
    weights = []
    for _, row in catalog_df.iterrows():
        if row["Category"] == "Generic": weights.append(80 / 72) 
        elif row["Category"] == "Branded": weights.append(12 / 7)
        else: weights.append(8 / 7)
    
    weights = np.array(weights) / sum(weights)
    
    for _ in range(total_items):
        drug = catalog_df.sample(n=1, weights=weights).iloc[0]
        
        # Simulate PA Flagging errors (15% of PA items are missed by staff)
        pa_flag = drug["Is_PA"]
        if pa_flag == 1 and random.random() < 0.15:
            pa_flag = 0 
            
        dispense_date = start_date + timedelta(days=random.randint(0, 30))
        
        data.append({
            "Dispense_Date": dispense_date.strftime("%Y-%m-%d"),
            "dmd_Code": drug["dmd_Code"],
            "Drug_Name": drug["Drug_Name"],
            "Quantity_Dispensed": drug["Pack_Size"],
            "Reimbursement_Price": drug["Tariff_Price"],
            "PA_Flag": pa_flag,
            "Category": drug["Category"]
        })
        
    return pd.DataFrame(data).sort_values("Dispense_Date")

def generate_invoice_data(dispensing_df, catalog_df, month_year="2026-03"):
    invoices = []
    start_date = datetime.strptime(f"{month_year}-01", "%Y-%m-%d")
    suppliers = ["AAH Pharmaceuticals", "Alliance Healthcare", "Phoenix Healthcare"]
    
    # Aggregate dispensed volumes to create realistic purchase orders
    volume_summary = dispensing_df.groupby("dmd_Code")["Quantity_Dispensed"].sum().reset_index()
    
    invoice_id = 10000
    for _, row in volume_summary.iterrows():
        drug = catalog_df[catalog_df["dmd_Code"] == row["dmd_Code"]].iloc[0]
        
        # Calculate total packs needed, add random 5% buffer for stock holding
        total_quantity_needed = row["Quantity_Dispensed"]
        total_packs_needed = int(np.ceil((total_quantity_needed / drug["Pack_Size"]) * 1.05))
        
        # Split into 1 to 4 deliveries across the month
        deliveries = random.randint(1, 4)
        packs_per_delivery = max(1, total_packs_needed // deliveries)
        
        for _ in range(deliveries):
            supplier = random.choice(suppliers)
            invoice_id += random.randint(1, 5)
            inv_date = start_date + timedelta(days=random.randint(0, 30))
            
            # Simulate Procurement Waste: 20% of the time, they buy generics at a loss
            if drug["Category"] == "Generic" and random.random() < 0.20:
                unit_price = round(drug["Tariff_Price"] * random.uniform(1.05, 1.20), 2)
            else:
                # Standard wholesale discount (8% to 15% off tariff)
                unit_price = round(drug["Tariff_Price"] * random.uniform(0.85, 0.92), 2)
            
            invoices.append({
                "Invoice_Date": inv_date.strftime("%Y-%m-%d"),
                "Invoice_Number": f"INV-{invoice_id}",
                "Supplier": supplier,
                "dmd_Code": drug["dmd_Code"],
                "Drug_Name": drug["Drug_Name"],
                "Pack_Size": drug["Pack_Size"],
                "Packs_Purchased": packs_per_delivery,
                "Unit_Price_Paid": unit_price,
                "Total_Net_Cost": round(unit_price * packs_per_delivery, 2)
            })
            
    return pd.DataFrame(invoices).sort_values("Invoice_Date")

if __name__ == "__main__":
    print("Building Drug Catalogue...")
    catalog = build_drug_catalog()
    
    print("Generating 20,000 Dispensing Records...")
    dispensing_df = generate_dispensing_data(catalog, total_items=20000)
    
    print("Reverse-engineering Wholesaler Invoices...")
    invoice_df = generate_invoice_data(dispensing_df, catalog)
    
    dispensing_df.to_csv("mock_dispensing_20k.csv", index=False)
    invoice_df.to_csv("mock_invoices_20k.csv", index=False)
    
    print("\nSuccess! Files created:")
    print(f"- mock_dispensing_20k.csv ({len(dispensing_df)} rows)")
    print(f"- mock_invoices_20k.csv ({len(invoice_df)} rows)")