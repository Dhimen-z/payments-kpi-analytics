import pandas as pd
import pytest

from analytics import dataset, kpis


@pytest.fixture(scope="module")
def con(tmp_path_factory):
    d = tmp_path_factory.mktemp("data")
    for name, df in dataset.build(n_customers=300, n_merchants=60, months=6).items():
        df.to_parquet(d / f"{name}.parquet", index=False)
    return kpis.connect(d)


def test_toutes_les_requetes_sont_chargees():
    q = kpis.load_queries()
    assert {"monthly_overview", "category_performance", "channel_funnel", "fraud_by_hour",
            "cohort_retention", "segment_value", "top_merchants_by_city"} <= set(q)


def test_coherence_des_kpi(con):
    r = kpis.run_all(con)
    fact = con.execute("select * from fact").df()
    approved = fact.loc[fact["is_approved"], "amount"].sum()
    # les agrégats SQL doivent réconcilier avec un calcul pandas indépendant
    assert r["monthly_overview"]["approved_volume"].sum() == pytest.approx(approved)
    assert r["category_performance"]["share_of_volume"].sum() == pytest.approx(1.0)
    assert r["channel_funnel"]["transactions"].sum() == len(fact)
    assert r["fraud_by_hour"]["hour"].between(0, 23).all()


def test_retention_bornee_et_mois0_a_100(con):
    co = kpis.run_all(con)["cohort_retention"]
    assert co["retention"].between(0, 1).all()
    assert (co.loc[co["month_n"] == 0, "retention"] == 1).all()


def test_top3_par_ville(con):
    top = kpis.run_all(con)["top_merchants_by_city"]
    assert top.groupby("city")["rk"].max().le(3).all()
    assert isinstance(top, pd.DataFrame)
