"""Génère le rapport d'analyse (RAPPORT.md + graphiques PNG dans docs/) à partir des KPI.

Tous les chiffres du rapport sont calculés : relancer le script après un
changement de données met le texte à jour.
"""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from analytics.kpis import ROOT, connect, run_all  # noqa: E402

DOCS = ROOT / "docs"
BLUE, ORANGE, GREY = "#2f5d8a", "#d9822b", "#9aa5b1"


def _style(ax, title):
    ax.set_title(title, loc="left", fontsize=12, fontweight="bold")
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", alpha=.25)


def chart_monthly(df: pd.DataFrame) -> str:
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.bar(df["month"].astype(str).str[:7], df["approved_volume"] / 1e6, color=BLUE)
    ax.set_ylabel("Volume approuvé (M€)")
    ax2 = ax.twinx()
    ax2.plot(df["month"].astype(str).str[:7], df["active_customers"], color=ORANGE, marker="o")
    ax2.set_ylabel("Clients actifs", color=ORANGE)
    ax2.spines[["top"]].set_visible(False)
    _style(ax, "Volume approuvé et clients actifs par mois")
    ax.tick_params(axis="x", rotation=45)
    return _save(fig, "volume_mensuel.png")


def chart_category(df: pd.DataFrame) -> str:
    d = df.sort_values("fraud_rate")
    fig, ax = plt.subplots(figsize=(8, 4))
    colors = [ORANGE if r <= 2 else GREY for r in d["risk_rank"]]
    ax.barh(d["category"], d["fraud_rate"] * 100, color=colors)
    ax.set_xlabel("Taux de fraude (% des transactions)")
    _style(ax, "Risque de fraude par catégorie de marchand")
    ax.grid(axis="x", alpha=.25)
    return _save(fig, "fraude_categorie.png")


def chart_hour(df: pd.DataFrame) -> str:
    fig, ax = plt.subplots(figsize=(8, 3.5))
    ax.plot(df["hour"], df["fraud_rate"] * 100, color=ORANGE, marker="o")
    ax.axvspan(-.5, 5.5, color=ORANGE, alpha=.08)
    ax.set_xlabel("Heure")
    ax.set_ylabel("Taux de fraude (%)")
    _style(ax, "Profil horaire de la fraude")
    return _save(fig, "fraude_heure.png")


def chart_cohorts(df: pd.DataFrame) -> str:
    pivot = df.pivot(index="cohort", columns="month_n", values="retention")
    fig, ax = plt.subplots(figsize=(9, 4.5))
    im = ax.imshow(pivot.to_numpy() * 100, aspect="auto", cmap="Blues", vmin=0, vmax=100)
    ax.set_yticks(range(len(pivot)), [str(c)[:7] for c in pivot.index])
    ax.set_xticks(range(pivot.shape[1]), pivot.columns)
    ax.set_xlabel("Mois depuis l'acquisition")
    fig.colorbar(im, ax=ax, label="Rétention (%)")
    ax.set_title("Rétention par cohorte d'acquisition", loc="left", fontsize=12, fontweight="bold")
    return _save(fig, "retention_cohortes.png")


def _save(fig, name: str) -> str:
    DOCS.mkdir(exist_ok=True)
    fig.tight_layout()
    fig.savefig(DOCS / name, dpi=130)
    plt.close(fig)
    return name


def pct(x: float, d: int = 1) -> str:
    return f"{x * 100:.{d}f} %".replace(".", ",")


def eur(x: float) -> str:
    return f"{x:,.0f} €".replace(",", " ")


def build_report(k: dict[str, pd.DataFrame]) -> str:
    mo, cat, ch, hr, co, seg = (k[n] for n in ("monthly_overview", "category_performance", "channel_funnel",
                                               "fraud_by_hour", "cohort_retention", "segment_value"))
    total = mo["approved_volume"].sum()
    top2 = cat.nlargest(2, "approved_volume")
    risky = cat.nsmallest(2, "risk_rank")
    ecom = ch.set_index("channel").loc["E-commerce"]
    store = ch.set_index("channel").loc["Paiement en magasin"]
    night = hr[hr["hour"] < 6]["fraud_rate"].mean()
    day = hr[hr["hour"] >= 6]["fraud_rate"].mean()
    r3 = co[co["month_n"] == 3]["retention"].mean()
    r6 = co[co["month_n"] == 6]["retention"].mean()
    s = seg.set_index("segment")["spend_per_active_month"]

    imgs = dict(monthly=chart_monthly(mo), category=chart_category(cat),
                hour=chart_hour(hr), cohorts=chart_cohorts(co))

    return f"""# Rapport d'analyse — activité de paiement carte (12 mois)

> Rapport généré automatiquement par `python -m analytics.report` à partir de données synthétiques.

## Synthèse

- **{eur(total)}** de volume approuvé sur la période, porté à **{pct(top2['share_of_volume'].sum(), 0)}** par deux catégories : {top2.iloc[0]['category']} et {top2.iloc[1]['category']}.
- Les catégories les plus risquées sont **{risky.iloc[0]['category']}** ({pct(risky.iloc[0]['fraud_rate'], 2)} de fraude) et **{risky.iloc[1]['category']}** ({pct(risky.iloc[1]['fraud_rate'], 2)}), contre {pct(cat['fraud_rate'].median(), 2)} en médiane.
- L'**e-commerce** cumule un taux d'acceptation plus bas ({pct(ecom['approval_rate'])} contre {pct(store['approval_rate'])} en magasin) et une fraude {ecom['fraud_rate'] / store['fraud_rate']:.1f} fois plus élevée.
- La nuit (0 h–6 h), le taux de fraude est **{night / day:.1f} fois** celui de la journée.
- Rétention moyenne : **{pct(r3, 0)} à 3 mois**, **{pct(r6, 0)} à 6 mois** après l'acquisition.
- Un client Pro dépense **{s['Pro'] / s['Particulier']:.1f} fois** plus par mois actif qu'un particulier.

## 1. Évolution mensuelle

![Volume mensuel](docs/{imgs['monthly']})

{_table(mo[['month', 'transactions', 'active_customers', 'approved_volume', 'approval_rate', 'volume_mom']])}

## 2. Risque par catégorie

![Fraude par catégorie](docs/{imgs['category']})

{_table(cat[['category', 'approved_volume', 'share_of_volume', 'fraud_rate', 'fraud_amount']])}

**Recommandation** : renforcer les règles d'authentification (3-D Secure systématique, plafonds) sur les deux catégories en tête du classement de risque, qui pèsent peu en volume mais concentrent une part disproportionnée des montants fraudés.

## 3. Canaux et horaires

{_table(ch)}

![Fraude par heure](docs/{imgs['hour']})

**Recommandation** : un seuil de score plus strict sur la plage 0 h–6 h, en e-commerce en priorité.

## 4. Rétention des clients

![Rétention](docs/{imgs['cohorts']})

**Lecture** : chaque ligne est une cohorte de clients acquis le même mois ; la décroissance le long de la ligne mesure le churn. La perte la plus forte a lieu entre le 2ᵉ et le 4ᵉ mois : c'est la fenêtre où une action de réactivation a le plus d'effet.

## 5. Valeur par segment

{_table(seg)}

## Méthode

Requêtes SQL (DuckDB) dans `sql/kpis.sql`, exécutées sur un schéma en étoile Parquet. Fonctions de fenêtre (`LAG`, `RANK`, `ROW_NUMBER`), agrégats filtrés et analyse de cohortes. Les mêmes tables sont exportables vers Power BI (`python -m analytics.export_powerbi`).
"""


def _table(df: pd.DataFrame) -> str:
    d = df.copy()
    for c in d.columns:
        if c.endswith(("rate", "share_of_volume", "_mom", "retention")):
            d[c] = d[c].map(lambda v: "" if pd.isna(v) else pct(v, 2))
        elif "volume" in c or "amount" in c or "spend" in c or c == "avg_ticket":
            d[c] = d[c].map(eur)
        elif c == "month":
            d[c] = d[c].astype(str).str[:7]
    return d.to_markdown(index=False)


def main() -> None:
    k = run_all(connect())
    (ROOT / "RAPPORT.md").write_text(build_report(k), encoding="utf-8")
    print("Rapport écrit : RAPPORT.md (+ graphiques dans docs/)")


if __name__ == "__main__":
    main()
