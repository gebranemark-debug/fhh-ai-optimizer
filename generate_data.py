import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import random

random.seed(42)
np.random.seed(42)

# Monthly seasonal multipliers by category (MENA/Gulf market)
SEASONAL = {
    "Tissues": {
        1: 1.25, 2: 1.20, 3: 1.05, 4: 0.95, 5: 0.90, 6: 0.88,
        7: 0.90, 8: 0.95, 9: 1.10, 10: 1.05, 11: 1.15, 12: 1.30,
    },
    "Toilet Paper": {
        1: 0.95, 2: 0.97, 3: 1.22, 4: 1.18, 5: 1.05, 6: 1.00,
        7: 0.97, 8: 0.97, 9: 1.00, 10: 1.02, 11: 1.05, 12: 1.12,
    },
    "Kitchen Towels": {
        1: 0.95, 2: 0.92, 3: 1.00, 4: 1.05, 5: 1.12, 6: 1.22,
        7: 1.25, 8: 1.18, 9: 1.05, 10: 1.00, 11: 1.05, 12: 1.15,
    },
    "Napkins": {
        1: 0.95, 2: 0.95, 3: 1.20, 4: 1.30, 5: 1.15, 6: 0.95,
        7: 0.92, 8: 0.92, 9: 1.00, 10: 1.05, 11: 1.10, 12: 1.20,
    },
    "Baby Wipes": {
        1: 0.90, 2: 0.92, 3: 1.10, 4: 1.15, 5: 1.10, 6: 1.25,
        7: 1.30, 8: 1.28, 9: 1.05, 10: 0.95, 11: 0.90, 12: 0.88,
    },
    "Baby Diapers": {
        1: 0.98, 2: 0.97, 3: 1.05, 4: 1.08, 5: 1.05, 6: 1.02,
        7: 1.00, 8: 1.00, 9: 1.03, 10: 1.02, 11: 0.98, 12: 0.97,
    },
    "Adult Wipes": {
        1: 0.85, 2: 0.88, 3: 0.95, 4: 1.05, 5: 1.18, 6: 1.32,
        7: 1.35, 8: 1.28, 9: 1.05, 10: 0.95, 11: 0.88, 12: 0.88,
    },
    "Hand Sanitizers": {
        1: 1.18, 2: 1.12, 3: 1.22, 4: 1.18, 5: 1.00, 6: 0.90,
        7: 0.88, 8: 0.88, 9: 0.95, 10: 1.00, 11: 1.10, 12: 1.15,
    },
    "Feminine Care": {
        1: 1.00, 2: 1.00, 3: 1.02, 4: 1.02, 5: 1.02, 6: 0.98,
        7: 0.97, 8: 0.97, 9: 1.00, 10: 1.00, 11: 1.00, 12: 1.02,
    },
    "Industrial Hygiene": {
        1: 0.95, 2: 0.95, 3: 1.00, 4: 1.02, 5: 1.05, 6: 1.05,
        7: 0.95, 8: 0.90, 9: 1.05, 10: 1.05, 11: 1.12, 12: 1.22,
    },
    "Cotton Products": {
        1: 0.97, 2: 0.97, 3: 1.00, 4: 1.02, 5: 1.05, 6: 1.08,
        7: 1.08, 8: 1.05, 9: 1.00, 10: 0.98, 11: 0.97, 12: 0.97,
    },
}

# 37 SKUs across 11 categories — stock levels set to produce a realistic mix:
# 7 STOCKOUT RISK · 5 OVERSTOCK · 7 ORDER NOW · 18 HEALTHY
products = [
    # ── TISSUES (5) ──────────────────────────────────────────────────────────
    {"sku": "FHH-TIS-001", "name": "Fine Facial Tissues 200s (Box)",
     "category": "Tissues",       "base_demand": 4200, "unit": "boxes",
     "current_stock": 5000,  "reorder_point": 3200, "max_stock": 12000, "lead_time_days": 14, "cost_per_unit": 1.20},
    # STOCKOUT RISK — well below 19-day threshold
    {"sku": "FHH-TIS-002", "name": "Fine Travel Pocket Tissues 10s (Pack)",
     "category": "Tissues",       "base_demand": 3800, "unit": "packs",
     "current_stock": 1800,  "reorder_point": 2800, "max_stock": 11000, "lead_time_days": 12, "cost_per_unit": 0.65},
    # OVERSTOCK — above 85% of max
    {"sku": "FHH-TIS-003", "name": "Fine Soft Box Tissues 150s",
     "category": "Tissues",       "base_demand": 3500, "unit": "boxes",
     "current_stock": 9900,  "reorder_point": 2500, "max_stock": 11500, "lead_time_days": 12, "cost_per_unit": 0.95},
    {"sku": "FHH-TIS-004", "name": "Fine Ultra Soft Facial Tissues 100s",
     "category": "Tissues",       "base_demand": 2900, "unit": "boxes",
     "current_stock": 4500,  "reorder_point": 2100, "max_stock":  9000, "lead_time_days": 14, "cost_per_unit": 1.05},
    # ORDER NOW — below reorder point, not yet critical
    {"sku": "FHH-TIS-005", "name": "Fine Jumbo Tissue Box 200s",
     "category": "Tissues",       "base_demand": 2100, "unit": "boxes",
     "current_stock": 2000,  "reorder_point": 2500, "max_stock":  7000, "lead_time_days": 14, "cost_per_unit": 1.30},

    # ── TOILET PAPER (4) ─────────────────────────────────────────────────────
    {"sku": "FHH-TOI-001", "name": "Fine Toilet Rolls 10-Pack",
     "category": "Toilet Paper",   "base_demand": 5800, "unit": "packs",
     "current_stock": 9000,  "reorder_point": 4200, "max_stock": 16000, "lead_time_days": 14, "cost_per_unit": 2.80},
    {"sku": "FHH-TOI-002", "name": "Fine Toilet Rolls 4-Pack",
     "category": "Toilet Paper",   "base_demand": 4200, "unit": "packs",
     "current_stock": 5500,  "reorder_point": 3200, "max_stock": 13000, "lead_time_days": 14, "cost_per_unit": 1.20},
    # ORDER NOW
    {"sku": "FHH-TOI-003", "name": "Fine Ultra Soft Toilet Rolls 10-Pack",
     "category": "Toilet Paper",   "base_demand": 3600, "unit": "packs",
     "current_stock": 2600,  "reorder_point": 3500, "max_stock": 11000, "lead_time_days": 10, "cost_per_unit": 3.50},
    # OVERSTOCK
    {"sku": "FHH-TOI-004", "name": "Fine Compact Toilet Rolls 48-Pack",
     "category": "Toilet Paper",   "base_demand": 2800, "unit": "packs",
     "current_stock": 10500, "reorder_point": 2000, "max_stock": 12000, "lead_time_days": 12, "cost_per_unit": 8.20},

    # ── KITCHEN TOWELS (3) ───────────────────────────────────────────────────
    # STOCKOUT RISK — far below 19-day threshold
    {"sku": "FHH-KIT-001", "name": "Fine Kitchen Towels 2-Roll Pack",
     "category": "Kitchen Towels", "base_demand": 3100, "unit": "packs",
     "current_stock": 1000,  "reorder_point": 2400, "max_stock":  9000, "lead_time_days": 12, "cost_per_unit": 1.95},
    {"sku": "FHH-KIT-002", "name": "Fine Kitchen Towels 4-Roll Pack",
     "category": "Kitchen Towels", "base_demand": 2400, "unit": "packs",
     "current_stock": 4500,  "reorder_point": 1900, "max_stock":  8000, "lead_time_days": 12, "cost_per_unit": 3.60},
    {"sku": "FHH-KIT-003", "name": "Fine Mega Kitchen Roll",
     "category": "Kitchen Towels", "base_demand": 1900, "unit": "rolls",
     "current_stock": 3200,  "reorder_point": 1500, "max_stock":  6500, "lead_time_days": 10, "cost_per_unit": 2.40},

    # ── NAPKINS (3) ──────────────────────────────────────────────────────────
    {"sku": "FHH-NAP-001", "name": "Fine Napkins 150s (Pack)",
     "category": "Napkins",        "base_demand": 3400, "unit": "packs",
     "current_stock": 6000,  "reorder_point": 2600, "max_stock": 10000, "lead_time_days": 10, "cost_per_unit": 0.95},
    # ORDER NOW
    {"sku": "FHH-NAP-002", "name": "Fine Dinner Napkins 100s",
     "category": "Napkins",        "base_demand": 2800, "unit": "packs",
     "current_stock": 2200,  "reorder_point": 2800, "max_stock":  9000, "lead_time_days": 10, "cost_per_unit": 0.75},
    # OVERSTOCK
    {"sku": "FHH-NAP-003", "name": "Fine Cocktail Napkins 50s",
     "category": "Napkins",        "base_demand": 2200, "unit": "packs",
     "current_stock": 8000,  "reorder_point": 1600, "max_stock":  9000, "lead_time_days": 10, "cost_per_unit": 0.55},

    # ── BABY WIPES (3) ───────────────────────────────────────────────────────
    {"sku": "FHH-WIP-001", "name": "Fine Baby Wipes 80s",
     "category": "Baby Wipes",     "base_demand": 6200, "unit": "packs",
     "current_stock": 10000, "reorder_point": 4800, "max_stock": 18000, "lead_time_days": 16, "cost_per_unit": 2.10},
    # ORDER NOW
    {"sku": "FHH-WIP-002", "name": "Fine Baby Wipes 120s",
     "category": "Baby Wipes",     "base_demand": 4800, "unit": "packs",
     "current_stock": 4500,  "reorder_point": 5500, "max_stock": 15000, "lead_time_days": 16, "cost_per_unit": 2.85},
    # STOCKOUT RISK — well below 23-day threshold
    {"sku": "FHH-WIP-003", "name": "Fine Baby Extra Sensitive Wipes 80s",
     "category": "Baby Wipes",     "base_demand": 3200, "unit": "packs",
     "current_stock": 1200,  "reorder_point": 2500, "max_stock": 10000, "lead_time_days": 16, "cost_per_unit": 2.50},

    # ── BABY DIAPERS (5) ─────────────────────────────────────────────────────
    {"sku": "FHH-DIA-001", "name": "Fine Baby Diapers Size 1 (0-5 kg / 36s)",
     "category": "Baby Diapers",   "base_demand": 2200, "unit": "packs",
     "current_stock": 4500,  "reorder_point": 1700, "max_stock":  7500, "lead_time_days": 21, "cost_per_unit": 6.80},
    {"sku": "FHH-DIA-002", "name": "Fine Baby Diapers Size 2 (3-6 kg / 40s)",
     "category": "Baby Diapers",   "base_demand": 2800, "unit": "packs",
     "current_stock": 5500,  "reorder_point": 2100, "max_stock":  9000, "lead_time_days": 21, "cost_per_unit": 7.40},
    {"sku": "FHH-DIA-003", "name": "Fine Baby Diapers Size 3 (4-9 kg / 46s)",
     "category": "Baby Diapers",   "base_demand": 3800, "unit": "packs",
     "current_stock": 6000,  "reorder_point": 3000, "max_stock": 11000, "lead_time_days": 21, "cost_per_unit": 8.50},
    {"sku": "FHH-DIA-004", "name": "Fine Baby Diapers Size 4 (7-14 kg / 40s)",
     "category": "Baby Diapers",   "base_demand": 4100, "unit": "packs",
     "current_stock": 7000,  "reorder_point": 3200, "max_stock": 12000, "lead_time_days": 21, "cost_per_unit": 9.20},
    # STOCKOUT RISK — well below 28-day threshold
    {"sku": "FHH-DIA-005", "name": "Fine Baby Diapers Size 5 (11-16 kg / 36s)",
     "category": "Baby Diapers",   "base_demand": 3200, "unit": "packs",
     "current_stock": 1500,  "reorder_point": 2500, "max_stock": 10000, "lead_time_days": 21, "cost_per_unit": 9.80},

    # ── ADULT WIPES (2) ──────────────────────────────────────────────────────
    # STOCKOUT RISK — well below 23-day threshold
    {"sku": "FHH-AWP-001", "name": "Fine Flushable Wipes 40s",
     "category": "Adult Wipes",    "base_demand": 2800, "unit": "packs",
     "current_stock": 800,   "reorder_point": 2100, "max_stock":  8000, "lead_time_days": 16, "cost_per_unit": 1.75},
    {"sku": "FHH-AWP-002", "name": "Fine Antibacterial Wipes 80s",
     "category": "Adult Wipes",    "base_demand": 2400, "unit": "packs",
     "current_stock": 4200,  "reorder_point": 1900, "max_stock":  8000, "lead_time_days": 14, "cost_per_unit": 2.20},

    # ── HAND SANITIZERS (3) ──────────────────────────────────────────────────
    {"sku": "FHH-SAN-001", "name": "Fine Hand Sanitizer 500ml",
     "category": "Hand Sanitizers","base_demand": 3600, "unit": "bottles",
     "current_stock": 5500,  "reorder_point": 2800, "max_stock": 11000, "lead_time_days": 14, "cost_per_unit": 3.20},
    # ORDER NOW
    {"sku": "FHH-SAN-002", "name": "Fine Hand Sanitizer 250ml",
     "category": "Hand Sanitizers","base_demand": 4200, "unit": "bottles",
     "current_stock": 3700,  "reorder_point": 4500, "max_stock": 13000, "lead_time_days": 14, "cost_per_unit": 1.90},
    # OVERSTOCK
    {"sku": "FHH-SAN-003", "name": "Fine Antibacterial Hand Wash 400ml",
     "category": "Hand Sanitizers","base_demand": 3100, "unit": "bottles",
     "current_stock": 11200, "reorder_point": 2200, "max_stock": 12500, "lead_time_days": 12, "cost_per_unit": 2.50},

    # ── FEMININE CARE (4) ────────────────────────────────────────────────────
    {"sku": "FHH-FEM-001", "name": "Fine Lady Maxi Pads Regular 20s",
     "category": "Feminine Care",  "base_demand": 4800, "unit": "packs",
     "current_stock": 8500,  "reorder_point": 3700, "max_stock": 15000, "lead_time_days": 18, "cost_per_unit": 1.80},
    # STOCKOUT RISK — well below 25-day threshold
    {"sku": "FHH-FEM-002", "name": "Fine Lady Maxi Pads Night 16s",
     "category": "Feminine Care",  "base_demand": 3600, "unit": "packs",
     "current_stock": 1500,  "reorder_point": 2700, "max_stock": 11000, "lead_time_days": 18, "cost_per_unit": 2.10},
    {"sku": "FHH-FEM-003", "name": "Fine Lady Panty Liners 30s",
     "category": "Feminine Care",  "base_demand": 5200, "unit": "packs",
     "current_stock": 10000, "reorder_point": 4000, "max_stock": 16000, "lead_time_days": 18, "cost_per_unit": 1.40},
    # ORDER NOW
    {"sku": "FHH-FEM-004", "name": "Fine Lady Ultra Thin Pads 22s",
     "category": "Feminine Care",  "base_demand": 3900, "unit": "packs",
     "current_stock": 4200,  "reorder_point": 5000, "max_stock": 12000, "lead_time_days": 18, "cost_per_unit": 2.30},

    # ── INDUSTRIAL HYGIENE (3) ───────────────────────────────────────────────
    {"sku": "FHH-IND-001", "name": "Fine Maxi Roll Tissue Industrial (6-Pack)",
     "category": "Industrial Hygiene","base_demand": 1800, "unit": "packs",
     "current_stock": 3500,  "reorder_point": 1400, "max_stock":  6000, "lead_time_days": 21, "cost_per_unit": 12.50},
    # ORDER NOW
    {"sku": "FHH-IND-002", "name": "Fine C-Fold Hand Towels (200s Pack)",
     "category": "Industrial Hygiene","base_demand": 2400, "unit": "packs",
     "current_stock": 2900,  "reorder_point": 3500, "max_stock":  8000, "lead_time_days": 21, "cost_per_unit": 7.80},
    # STOCKOUT RISK — well below 28-day threshold
    {"sku": "FHH-IND-003", "name": "Fine Industrial Cleaning Wipes 50s",
     "category": "Industrial Hygiene","base_demand": 1600, "unit": "packs",
     "current_stock": 600,   "reorder_point": 1300, "max_stock":  5500, "lead_time_days": 21, "cost_per_unit": 5.60},

    # ── COTTON PRODUCTS (2) ──────────────────────────────────────────────────
    {"sku": "FHH-COT-001", "name": "Fine Cotton Pads 100s",
     "category": "Cotton Products","base_demand": 3800, "unit": "packs",
     "current_stock": 6500,  "reorder_point": 3000, "max_stock": 12000, "lead_time_days": 14, "cost_per_unit": 1.60},
    # OVERSTOCK
    {"sku": "FHH-COT-002", "name": "Fine Cotton Buds 200s",
     "category": "Cotton Products","base_demand": 4200, "unit": "packs",
     "current_stock": 10800, "reorder_point": 3200, "max_stock": 12500, "lead_time_days": 14, "cost_per_unit": 1.10},
]

# Generate 24 months of historical data (Jan 2023 – Dec 2024)
start_date = datetime(2023, 1, 1)
records = []

for product in products:
    seasonal = SEASONAL[product["category"]]
    for month_offset in range(24):
        date  = start_date + timedelta(days=30 * month_offset)
        month = date.month
        year  = date.year

        # 8% YoY growth for FHH MENA region
        growth = 1.0 + (0.08 * (year - 2023)) + (0.08 * (month_offset / 12) * 0.5)
        noise  = np.random.normal(1.0, 0.08)
        demand = max(int(product["base_demand"] * seasonal[month] * growth * noise), 0)

        records.append({
            "date":         date.strftime("%Y-%m-01"),
            "sku":          product["sku"],
            "product_name": product["name"],
            "category":     product["category"],
            "units_sold":   demand,
            "unit":         product["unit"],
        })

df_sales = pd.DataFrame(records)
df_sales.to_csv("fhh_sales_history.csv", index=False)
print(f"Sales history generated: {len(df_sales)} rows ({len(products)} products × 24 months)")

df_products = pd.DataFrame(products)
df_products.to_csv("fhh_products.csv", index=False)
print(f"Product master generated: {len(df_products)} products across {df_products['category'].nunique()} categories")
print(df_products[["sku", "name", "current_stock", "reorder_point", "lead_time_days"]].to_string())
