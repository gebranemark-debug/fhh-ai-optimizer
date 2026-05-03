"""Synthesize 60 months of monthly sales history for the FHH demand layer.

Writes to ``backend/data/demand_history.parquet``. Re-runnable: drops the
file before recreating. The output matches the contract's expected shape
(date, sku, market, units_sold) and is the input the /forecast,
/demand/anomalies, /demand/seasonality endpoints read from when the real
ETL isn't yet in place.

Run:
    python backend/data/generate_demand_history.py

Design notes:
- 37 SKUs (from products.json) x 5 markets (from markets.json) x 60
  months (Jan 2021 - Dec 2025) = 11,100 rows.
- Baseline volume scales by category (tissue is biggest, cosmetics
  smallest) and market (UAE > KSA > Egypt > Jordan > Morocco per the
  brief).
- Per-SKU multiplier inside each category gives some SKUs more than
  others, deterministically derived from the SKU string.
- Seasonal lifts applied at monthly granularity, with Hijri-aware dates:
    - Ramadan: +35% on tissue/baby_care/adult_care, in whichever month
      contains Ramadan 1 of each Hijri year (drifts ~10-11 days earlier
      per Gregorian year — Mar 2021 -> Jan/Feb 2025 etc.).
    - Eid al-Fitr: +22% on tissue, in whichever month contains Shawwal 1.
      Often the same month as Ramadan, sometimes the next.
    - Back-to-school (Aug): +12% on tissue, fixed Gregorian.
- Three deliberate anomalies seeded for /demand/anomalies to "detect":
  spike on (fine-baby-s3, ksa), dip on (fine-toilet-3ply, uae),
  trend break on (fine-facial-200, egypt).
- Light Gaussian noise (~5% sigma) on top.

Crucial: this script imports the same _ramadan_start_gregorian /
_eid_al_fitr_gregorian helpers that backend/data.py uses at runtime, so
training data and Prophet's holiday flags share a single Hijri source
of truth.
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

import pandas as pd

# Make backend/ importable so we can pull the Hijri helpers from data.py.
HERE = Path(__file__).parent
BACKEND_DIR = HERE.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from data import _ramadan_start_gregorian, _eid_al_fitr_gregorian  # noqa: E402

SEED = 20260425  # locked for reproducibility — anchor "today" date.

# Generation window. 5 years gives Prophet enough Ramadans across
# different Gregorian months to disentangle "Ramadan effect" from
# "month-of-year effect".
START_YEAR = 2021
START_MONTH = 1
NUM_MONTHS = 60  # Jan 2021 -> Dec 2025

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

# Lifts per the contract's seasonality endpoint example.
RAMADAN_LIFT      = 0.35
EID_LIFT          = 0.22
BACK_TO_SCHOOL_LIFT = 0.12

# Categories that respond to each event.
RAMADAN_CATEGORIES = {"tissue", "baby_care", "adult_care"}
EID_CATEGORIES     = {"tissue", "baby_care", "adult_care"}
BACK_TO_SCHOOL_CATEGORIES = {"tissue"}

# Back-to-school is fixed-Gregorian (kids start school in August
# regardless of Hijri calendar).
BACK_TO_SCHOOL_MONTH = 8


def _build_event_months(start_year: int, end_year: int) -> tuple[set, set]:
    """Compute the (year, month) coordinates where Ramadan and Eid fall,
    for every Gregorian year in [start_year, end_year]. Uses the same
    Hijri helpers as backend/data.py so training data and Prophet's
    holiday flags agree."""
    ramadan_months: set[tuple[int, int]] = set()
    eid_months: set[tuple[int, int]] = set()
    # Look slightly before/after the window so events that span year
    # boundaries are still captured.
    for year in range(start_year - 1, end_year + 2):
        try:
            ramadan = _ramadan_start_gregorian(year)
            eid = _eid_al_fitr_gregorian(ramadan)
            ramadan_months.add((ramadan.year, ramadan.month))
            eid_months.add((eid.year, eid.month))
        except Exception:
            continue
    return ramadan_months, eid_months


# Deliberate anomalies — kept identical to the previous design so the
# /demand/anomalies endpoint surfaces the same examples for the demo.
# Coordinates are in absolute (year, month).
ANOMALIES = [
    # (sku, market, year, month, multiplier, type)
    # Spike: distributor restocking surge.
    ("fine-baby-s3",    "ksa",   2025, 9,  1.47, "spike"),
    # Dip: short-term supply issue.
    ("fine-toilet-3ply","uae",   2025, 6,  0.68, "dip"),
    # Trend break: sustained downward shift starting in this month.
    ("fine-facial-200", "egypt", 2025, 4,  0.82, "trend_break"),
]


def _sku_multiplier(sku: str) -> float:
    """Deterministic per-SKU multiplier derived from the SKU string. Range
    is roughly 0.6 .. 1.4 so the spread is visible without dominating."""
    h = 0
    for ch in sku:
        h = (h * 31 + ord(ch)) % (2**31)
    return 0.6 + (h % 1000) / 1000.0 * 0.8


def _seasonal_lift(
    year: int,
    month: int,
    category: str,
    ramadan_months: set,
    eid_months: set,
) -> float:
    lift = 0.0
    if (year, month) in ramadan_months and category in RAMADAN_CATEGORIES:
        lift += RAMADAN_LIFT
    if (year, month) in eid_months and category in EID_CATEGORIES:
        lift += EID_LIFT
    if month == BACK_TO_SCHOOL_MONTH and category in BACK_TO_SCHOOL_CATEGORIES:
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

    end_year = START_YEAR + (NUM_MONTHS - 1) // 12
    ramadan_months, eid_months = _build_event_months(START_YEAR, end_year)

    print(f"Hijri-derived Ramadan months in window: {sorted(ramadan_months)}")
    print(f"Hijri-derived Eid al-Fitr months: {sorted(eid_months)}")

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
            for year, month in _months(START_YEAR, START_MONTH, NUM_MONTHS):
                base = cat_base * sku_mult * mkt_mult
                lift = _seasonal_lift(year, month, category, ramadan_months, eid_months)
                value = base * (1.0 + lift)
                # Trend break: sustained downward shift from the break month.
                if _trend_break_active(year, month, sku, market):
                    for a_sku, a_mkt, ay, am, mult, atype in ANOMALIES:
                        if atype == "trend_break" and sku == a_sku and market == a_mkt:
                            value *= mult
                            break
                # Point anomalies (spike / dip).
                value *= _point_anomaly(year, month, sku, market)
                # ~5% Gaussian noise on top, deterministic via rng.
                noise = rng.gauss(0.0, 0.05)
                value *= max(0.4, 1.0 + noise)
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