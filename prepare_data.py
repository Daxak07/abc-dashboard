"""
prepare_data.py
---------------
One-off, reproducible data-preparation step for the ABC payments dashboard.

What it does (and why):
  * Reads the raw export (`for_Task_2_-_dashboard.csv`).
  * Parses the `month` column from DD.MM.YYYY (ambiguous, non-standard) into a
    real date and re-expresses it in ISO 8601 (YYYY-MM-DD).
  * Filters to Q4 2025 (October-December). The earlier months (Mar-Sep 2025)
    contain only a handful of net-negative rows (refunds / pre-launch test
    activity) and would distort every metric. This is the deliberate
    "use only the data needed for meaningful insight" decision.
  * Drops three columns that hold a single constant value and therefore carry
    no analytical signal: product, record_type_key, legal_entity.
  * Replaces missing categorical values with an explicit "Unknown" / "No offer"
    category instead of dropping rows (so totals stay correct and the gaps are
    visible rather than hidden).
  * Writes a minimal, analysis-ready file: `data_q4_2025.csv`.

Run:  python prepare_data.py
"""

from pathlib import Path
import pandas as pd

RAW = Path("for_Task_2_-_dashboard.csv")
OUT = Path("data_q4_2025.csv")

# Columns kept for analysis (everything else is dropped).
KEEP = [
    "date", "month_label", "provider", "country_iso3", "order_payment_type",
    "payment_method", "card_brand", "gender", "offer", "orders_count",
    "total_payout_usd",
]


def main() -> None:
    df = pd.read_csv(RAW)

    # --- ISO 8601 dates -----------------------------------------------------
    df["date"] = pd.to_datetime(df["month"], format="%d.%m.%Y")
    df["month_label"] = df["date"].dt.strftime("%b %Y")  # e.g. "Oct 2025"

    # --- Filter to Q4 2025 (the only period with real, positive volume) -----
    before = len(df)
    df = df[df["date"] >= "2025-10-01"].copy()
    print(f"Filtered Mar-Sep noise: {before} -> {len(df)} rows "
          f"({len(df) / before:.1%} kept)")

    # --- Rename / tidy ------------------------------------------------------
    df = df.rename(columns={"vat_geo": "country_iso3"})

    # offer is a numeric code; treat blanks as an explicit category
    df["offer"] = (
        df["offer"].apply(lambda x: "No offer" if pd.isna(x) else str(int(x)))
    )

    # Explicit "Unknown" for missing categoricals (don't silently drop rows)
    for col in ["card_brand", "gender"]:
        df[col] = df[col].fillna("Unknown")

    df = df[KEEP]

    # --- Sanity report ------------------------------------------------------
    print(f"Rows: {len(df):,}")
    print(f"Orders: {int(df['orders_count'].sum()):,}")
    print(f"Net payout (USD): {df['total_payout_usd'].sum():,.2f}")
    print(f"Months: {sorted(df['month_label'].unique())}")
    print(f"Countries (ISO 3166-1 alpha-3): {df['country_iso3'].nunique()}")

    df.to_csv(OUT, index=False)
    print(f"\nWrote {OUT.resolve()}  ({OUT.stat().st_size/1024:.0f} KB)")


if __name__ == "__main__":
    main()
