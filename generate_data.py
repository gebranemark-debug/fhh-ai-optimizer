import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import random

random.seed(42)
np.random.seed(42)

# FHH Products - realistic SKUs with base monthly demand (units/cases)
products = [
    {"sku": "FHH-TIS-001", "name": "Fine Facial Tissues 200s (Box)", "category": "Tissues",       "base_demand": 4200, "unit": "boxes",  "current_stock": 3100,  "reorder_point": 3000, "max_stock": 12000, "lead_time_days": 14, "cost_per_unit": 1.20},
    {"sku": "FHH-TIS-002", "name": "Fine Toilet Rolls 10-Pack",       "category": "Tissues",       "base_demand": 5800, "unit": "packs",  "current_stock": 8200,  "reorder_point": 4000, "max_stock": 16000, "lead_time_days": 14, "cost_per_unit": 2.80},
    {"sku": "FHH-TIS-003", "name": "Fine Kitchen Towels 2-Roll",       "category": "Tissues",       "base_demand": 3100, "unit": "packs",  "current_stock": 1200,  "reorder_point": 2500, "max_stock": 9000,  "lead_time_days": 12, "cost_per_unit": 1.95},
    {"sku": "FHH-WIP-001", "name": "Fine Baby Wipes 80s",             "category": "Wet Wipes",     "base_demand": 6200, "unit": "packs",  "current_stock": 9800,  "reorder_point": 4500, "max_stock": 18000, "lead_time_days": 16, "cost_per_unit": 2.10},
    {"sku": "FHH-WIP-002", "name": "Fine Flushable Wipes 40s",        "category": "Wet Wipes",     "base_demand": 2800, "unit": "packs",  "current_stock": 980,   "reorder_point": 2000, "max_stock": 8000,  "lead_time_days": 16, "cost_per_unit": 1.75},
    {"sku": "FHH-DIA-001", "name": "Fine Baby Diapers Size 3 (46s)",  "category": "Diapers",       "base_demand": 3800, "unit": "packs",  "current_stock": 4100,  "reorder_point": 2800, "max_stock": 11000, "lead_time_days": 21, "cost_per_unit": 8.50},
    {"sku": "FHH-DIA-002", "name": "Fine Baby Diapers Size 4 (40s)",  "category": "Diapers",       "base_demand": 4100, "unit": "packs",  "current_stock": 5300,  "reorder_point": 3000, "max_stock": 12000, "lead_time_days": 21, "cost_per_unit": 9.20},
    {"sku": "FHH-NAP-001", "name": "Fine Napkins 150s (Pack)",        "category": "Napkins",       "base_demand": 3400, "unit": "packs",  "current_stock": 6100,  "reorder_point": 2500, "max_stock": 10000, "lead_time_days": 10, "cost_per_unit": 0.95},
]

# Generate 24 months of historical data (Jan 2023 - Dec 2024)
start_date = datetime(2023, 1, 1)
records = []

for product in products:
    for month_offset in range(24):
        date = start_date + timedelta(days=30 * month_offset)
        month = date.month
        year = date.year

        # Base seasonality multipliers per category
        if product["category"] == "Tissues":
            # Peak in winter (Dec-Feb) and back-to-school (Sep)
            seasonal = {1: 1.25, 2: 1.20, 3: 1.05, 4: 0.95, 5: 0.90, 6: 0.88,
                        7: 0.90, 8: 0.95, 9: 1.10, 10: 1.05, 11: 1.15, 12: 1.30}

        elif product["category"] == "Wet Wipes":
            # Peak in summer (Jun-Aug) and Ramadan effect (varies, ~Mar-Apr)
            seasonal = {1: 0.90, 2: 0.92, 3: 1.10, 4: 1.15, 5: 1.10, 6: 1.25,
                        7: 1.30, 8: 1.28, 9: 1.05, 10: 0.95, 11: 0.90, 12: 0.88}

        elif product["category"] == "Diapers":
            # Relatively stable, slight peak in spring
            seasonal = {1: 0.98, 2: 0.97, 3: 1.05, 4: 1.08, 5: 1.05, 6: 1.02,
                        7: 1.00, 8: 1.00, 9: 1.03, 10: 1.02, 11: 0.98, 12: 0.97}

        else:  # Napkins
            # Peak during Ramadan/Eid and year-end holidays
            seasonal = {1: 0.95, 2: 0.95, 3: 1.20, 4: 1.25, 5: 1.05, 6: 0.95,
                        7: 0.92, 8: 0.92, 9: 1.00, 10: 1.05, 11: 1.10, 12: 1.20}

        # Year-over-year growth (~8% annually for FHH MENA region)
        growth = 1.0 + (0.08 * (year - 2023)) + (0.08 * (month_offset / 12) * 0.5)

        # Noise ±10%
        noise = np.random.normal(1.0, 0.08)

        demand = int(product["base_demand"] * seasonal[month] * growth * noise)
        demand = max(demand, 0)

        records.append({
            "date": date.strftime("%Y-%m-01"),
            "sku": product["sku"],
            "product_name": product["name"],
            "category": product["category"],
            "units_sold": demand,
            "unit": product["unit"],
        })

df_sales = pd.DataFrame(records)
df_sales.to_csv("/home/claude/fhh_sales_history.csv", index=False)
print(f"Sales history generated: {len(df_sales)} rows")
print(df_sales.head(10).to_string())

# Generate product master (current inventory snapshot)
df_products = pd.DataFrame(products)
df_products.to_csv("/home/claude/fhh_products.csv", index=False)
print(f"\nProduct master generated: {len(df_products)} products")
print(df_products[["sku","name","current_stock","reorder_point","lead_time_days"]].to_string())
