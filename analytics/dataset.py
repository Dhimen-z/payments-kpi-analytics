"""Construit un jeu de données synthétique de paiements carte sur 12 mois (schéma en étoile).

Comportements simulés pour que l'analyse ait quelque chose à trouver :
- saisonnalité hebdomadaire et pic de décembre,
- churn progressif des clients (cohortes d'acquisition),
- taux de refus plus élevé en e-commerce,
- fraude concentrée sur certaines catégories, la nuit et sur les gros montants.

Sortie : data/*.parquet (fact_transactions, dim_customer, dim_merchant).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path("data")
CATEGORIES = {"Alimentation": (35, .02), "Restaurants": (28, .03), "Carburant": (55, .02),
              "Électronique": (180, .12), "Transport": (20, .02), "Mode": (70, .05),
              "Jeux en ligne": (45, .25), "Voyages": (320, .10)}
CITIES = ["Paris", "Lyon", "Marseille", "Toulouse", "Clermont-Ferrand", "Lille", "Nantes", "Bordeaux"]


def build(n_customers: int = 3000, n_merchants: int = 600, seed: int = 7,
          start: str = "2025-12-01", months: int = 12) -> dict[str, pd.DataFrame]:
    rng = np.random.default_rng(seed)
    t0 = pd.Timestamp(start)
    t1 = t0 + pd.DateOffset(months=months)
    days = pd.date_range(t0, t1 - pd.Timedelta(days=1), freq="D")

    # --- clients : date d'acquisition, segment, durée de vie (churn)
    acq_day = rng.integers(0, len(days) - 30, n_customers)
    segment = rng.choice(["Particulier", "Premium", "Pro"], n_customers, p=[.72, .18, .10])
    lifetime = rng.exponential(np.where(segment == "Premium", 420, 240))
    dim_customer = pd.DataFrame({
        "customer_id": [f"C{i:05d}" for i in range(n_customers)],
        "segment": segment,
        "city": rng.choice(CITIES, n_customers),
        "acquisition_date": days[acq_day],
    })

    cats = np.array(list(CATEGORIES))
    m_cat = rng.choice(cats, n_merchants, p=[.22, .2, .12, .08, .12, .12, .06, .08])
    dim_merchant = pd.DataFrame({
        "merchant_id": [f"M{i:04d}" for i in range(n_merchants)],
        "category": m_cat,
        "city": rng.choice(CITIES, n_merchants),
    })

    # --- transactions : intensité par client × saisonnalité, vectorisé jour par jour
    rate = np.where(segment == "Premium", .55, np.where(segment == "Pro", .8, .3))
    dow = np.array([1.0, 1.0, 1.05, 1.1, 1.3, 1.45, .7])
    frames = []
    for d_idx, day in enumerate(days):
        active = (acq_day <= d_idx) & (d_idx - acq_day <= lifetime)
        season = dow[day.dayofweek] * (1.35 if day.month == 12 else 1.0)
        counts = rng.poisson(rate * season * active)
        n = int(counts.sum())
        if n == 0:
            continue
        cust_idx = np.repeat(np.arange(n_customers), counts)
        merch_idx = rng.integers(0, n_merchants, n)
        cat = m_cat[merch_idx]
        base = np.array([CATEGORIES[c][0] for c in cat])
        risk = np.array([CATEGORIES[c][1] for c in cat])
        amount = np.round(base * rng.lognormal(0, .6, n), 2)
        hour = rng.choice(24, n, p=_hour_profile())
        channel = rng.choice(["Paiement en magasin", "E-commerce", "Sans contact"], n, p=[.45, .3, .25])
        p_fraud = .0015 * (1 + 6 * risk) * np.where(hour < 6, 4, 1) * np.where(amount > 300, 3, 1) \
            * np.where(channel == "E-commerce", 2.5, 1)
        fraud = rng.random(n) < p_fraud
        p_decline = np.where(channel == "E-commerce", .06, .02) + np.where(fraud, .35, 0)
        frames.append(pd.DataFrame({
            "event_ts": day + pd.to_timedelta(hour, unit="h") + pd.to_timedelta(rng.integers(0, 3600, n), unit="s"),
            "customer_id": dim_customer["customer_id"].to_numpy()[cust_idx],
            "merchant_id": dim_merchant["merchant_id"].to_numpy()[merch_idx],
            "channel": channel,
            "amount": amount,
            "is_approved": rng.random(n) >= p_decline,
            "is_fraud": fraud,
        }))
    fact = pd.concat(frames, ignore_index=True).sort_values("event_ts", ignore_index=True)
    fact.insert(0, "transaction_id", [f"T{i:08d}" for i in range(len(fact))])
    return {"fact_transactions": fact, "dim_customer": dim_customer, "dim_merchant": dim_merchant}


def _hour_profile() -> np.ndarray:
    h = np.arange(24)
    p = .2 + np.exp(-((h - 12.5) ** 2) / 8) + .8 * np.exp(-((h - 18.5) ** 2) / 6)
    return p / p.sum()


def main() -> None:
    OUT.mkdir(exist_ok=True)
    for name, df in build().items():
        df.to_parquet(OUT / f"{name}.parquet", index=False)
        print(f"{name:<18} {len(df):>8} lignes")


if __name__ == "__main__":
    main()
