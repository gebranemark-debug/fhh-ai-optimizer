"""Synthesize 24 months of monthly sales history for the FHH demand layer.

Writes to ``backend/data/demand_history.parquet``. Re-runnable: drops the
file before recreating. The output matches the contract's expected shape
(date, sku, market, units_sold) and is the input the /forecast,
/demand/anomalies, /demand/seasonality endpoints read from when the real
ETL isn't yet in place.

Run:
    python backend/data/generate_demand_history.py

Design notes:
- 37 SKUs (from products.json) x 5 markets (from markets.json) x 24
  months (Jan 2024 - Dec 2025) = 4,440 rows.
- Baseline volume scales by category (tissue is biggest, cosmetics
  smallest) and market (UAE > KSA > Egypt > Jordan > Morocco per the
  brief).
- Per-SKU multiplier inside each category gives some SKUs more than
  others, deterministically derived from the SKU string.
- Seasonal lifts applied at monthly granularity:
    - Ramadan (Mar 2024, Mar 2025): +35% on tissue/baby_care/adult_care
    - Eid al-Fitr (Apr 2024 — Eid lands Apr 10 that year): +22% on tissue
      (Eid 2025 lands Mar 30 so the lift folds into the Ramadan month)
    - Back-to-school (Aug 2024, Aug 2025): +12% on tissue
- Three deliberate anomalies seeded for /demand/anomalies to "detect":
  spike on (fine-baby-s3, ksa), dip on (fine-toilet-3ply, uae),
  trend break on (fine-facial-200, egypt).
- Light Gaussian noise (~5% sigma) on top.
"""

from __future__ import annotations

import json
import math
import random
from pathlib import Path

import pandas as pd


HERE = Path(__file__).parent
SEED = 20260425  # locked for reproducibility — anchor "today" date.

# Category-level monthly baseline (units in a UAE-sized market without
# any seasonal adjustment).
CATEGORY_BASELINE = {
    "tissue":     100_000,
    "baby_care":   60_000,
    "adult_care":  25_000,
    "fine_guard":  15_000,
    "wellness":    35_000,
    "cosmetics":   18_000,
}

# Market multipliers per the brief: UAE > KSA > Egypt > Jordan > Morocco.
MARKET_MULTIPLIER = {
    "uae":     1.20,
    "ksa":     1.00,
    "egypt":   0.75,
    "jordan":  0.55,
    "morocco": 0.40,
}

# Months touched by each event (1-indexed within the calendar year).
# Lifts apply to the full month for monthly-granularity data.
RAMADAN_MONTHS    = {(2024, 3), (2025, 3)}
EID_MONTHS        = {(2024, 4)}
BACK_TO_SCHOOL    = {(2024, 8), (2025, 8)}

# Lifts per the contract's seasonality endpoint example.
RAMADAN_LIFT      = 0.35
EID_LIFT          = 0.22
BACK_TO_SCHOOL_LIFT = 0.12

# Categories that respond to each event. Ramadan / Eid drive tissue +
# baby + adult care (households stock up). Back-to-school is tissue-only
# (kitchen towels, napkins, lunchbox tissues).
RAMADAN_CATEGORIES = {"tissue", "baby_care", "adult_care"}
EID_CATEGORIES     = {"tissue"}
BACK_TO_SCHOOL_CATEGORIES = {"tissue"}

# Deliberate anomalies, in absolute month coordinates. The numbers are
# the multiplier applied to the baseline+seasonal value at that month.
ANOMALIES = [
    # (sku, market, year, month, multiplier, type)
    # Spike: distributor restocking surge.
    ("fine-baby-s3",    "ksa",   2025, 9,  1.47, "spike"),
    # Dip: short-term supply issue.
    ("fine-toilet-3ply","uae",   2025, 6,  0.68, "dip"),
    # Trend break: sustained downward shift starting in this month.
    # The generator applies 0.82 from this month forward to end-of-window.
    ("fine-facial-200", "egypt", 2025, 4,  0.82, "trend_break"),
]


def _sku_multiplier(sku: str) -> float:
    """Deterministic per-SKU multiplier derived from the SKU string. Range
    is roughly 0.6 .. 1.4 so the spread is visible without dominating."""
    h = 0
    for ch in sku:
        h = (h * 31 + ord(ch)) % (2**31)
    # Map the hash into [0.6, 1.4].
    return 0.6 + (h % 1000) / 1000.0 * 0.8


def _seasonal_lift(year: int, month: int, category: str) -> float:
    lift = 0.0
    if (year, month) in RAMADAN_MONTHS and category in RAMADAN_CATEGORIES:
        lift += RAMADAN_LIFT
    if (year, month) in EID_MONTHS and category in EID_CATEGORIES:
        lift += EID_LIFT
    if (year, month) in BACK_TO_SCHOOL and category in BACK_TO_SCHOOL_CATEGORIES:
        lift += BACK_TO_SCHOOL_LIFT
    return lift


def _trend_break_active(year: int, month: int, sku: str, market: str) -> bool:
    for tb_sku, tb_mkt, ty, tm, _mult, atype in ANOMALIES:
        if atype != "trend_break":
            continue
        if sku == tb_sku and market == tb_mkt:
            if (year, month) >= (ty, tm):
                return True
    return False


def _point_anomaly(year: int, month: int, sku: str, market: str) -> float:
    """Return the point-anomaly multiplier for a (sku, market, ym) cell, or
    1.0 if no anomaly applies. Trend breaks are handled separately."""
    for a_sku, a_mkt, ay, am, mult, atype in ANOMALIES:
        if atype == "trend_break":
            continue
        if sku == a_sku and market == a_mkt and year == ay and month == am:
            return mult
    return 1.0


def _months(start_year: int, start_month: int, count: int):
    y, m = start_year, start_month
    for _ in range(count):
        yield y, m
        m += 1
        if m > 12:
            m = 1
            y += 1


def main() -> Path:
    rng = random.Random(SEED)

    products = json.loads((HERE / "products.json").read_text())["products"]
    markets = json.loads((HERE / "markets.json").read_text())["markets"]

    rows: list[dict] = []
    for p in products:
        sku = p["sku"]
        category = p["category"]
        sku_mult = _sku_multiplier(sku)
        cat_base = CATEGORY_BASELINE[category]
        for m in markets:
            market = m["market_id"]
            mkt_mult = MARKET_MULTIPLIER[market]
            for year, month in _months(2024, 1, 24):
                base = cat_base * sku_mult * mkt_mult
                lift = _seasonal_lift(year, month, category)
                value = base * (1.0 + lift)
                # Trend break: sustained downward shift from the break month.
                if _trend_break_active(year, month, sku, market):
                    # Trend break uses the same multiplier as the anomaly
                    # entry's multiplier (0.82 for the listed anomaly).
                    for a_sku, a_mkt, ay, am, mult, atype in ANOMALIES:
                        if atype == "trend_break" and sku == a_sku and market == a_mkt:
                            value *= mult
                            break
                # Point anomalies (spike / dip).
                value *= _point_anomaly(year, month, sku, market)
                # ~5% Gaussian noise on top, deterministic via rng.
                noise = rng.gauss(0.0, 0.05)
                value *= max(0.4, 1.0 + noise)  # floor noise so we never go silly-low
                units = int(round(value))

                rows.append({
                    "date": f"{year:04d}-{month:02d}-01",
                    "sku": sku,
                    "market": market,
                    "units_sold": units,
                })

    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    out = HERE / "demand_history.parquet"
    df.to_parquet(out, index=False)
    print(f"wrote {len(df):,} rows to {out}")
    return out


if __name__ == "__main__":
    main()
