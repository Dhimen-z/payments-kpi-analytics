"""Exporte le schéma en étoile en CSV (UTF-8, séparateur ;) pour Power BI / Excel, avec une table calendrier."""
from __future__ import annotations

import pandas as pd

from analytics.kpis import ROOT

OUT = ROOT / "powerbi" / "data"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    fact = pd.read_parquet(ROOT / "data" / "fact_transactions.parquet")
    fact["date"] = fact["event_ts"].dt.date
    fact.to_csv(OUT / "fact_transactions.csv", sep=";", index=False, decimal=",")
    for name in ("dim_customer", "dim_merchant"):
        pd.read_parquet(ROOT / "data" / f"{name}.parquet").to_csv(OUT / f"{name}.csv", sep=";", index=False)
    cal = pd.DataFrame({"date": pd.date_range(fact["event_ts"].min().normalize(), fact["event_ts"].max(), freq="D")})
    cal["annee"] = cal["date"].dt.year
    cal["mois"] = cal["date"].dt.strftime("%Y-%m")
    cal["jour_semaine"] = cal["date"].dt.dayofweek + 1
    cal["week_end"] = cal["jour_semaine"] >= 6
    cal["date"] = cal["date"].dt.date
    cal.to_csv(OUT / "dim_date.csv", sep=";", index=False)
    print(f"Export Power BI : {OUT}")


if __name__ == "__main__":
    main()
