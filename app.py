"""Tableau de bord Streamlit : streamlit run app.py"""
from __future__ import annotations

import duckdb
import plotly.express as px
import streamlit as st

from analytics.kpis import ROOT, connect

st.set_page_config(page_title="KPI paiements", layout="wide")


@st.cache_resource
def get_con() -> duckdb.DuckDBPyConnection:
    if not (ROOT / "data" / "fact_transactions.parquet").exists():
        from analytics import dataset
        dataset.main()
    return connect()


con = get_con()
cats = [r[0] for r in con.execute("select distinct category from dim_merchant order by 1").fetchall()]
chans = [r[0] for r in con.execute("select distinct channel from fact order by 1").fetchall()]
dmin, dmax = con.execute("select min(event_ts)::date, max(event_ts)::date from fact").fetchone()

with st.sidebar:
    st.header("Filtres")
    period = st.date_input("Période", (dmin, dmax), min_value=dmin, max_value=dmax)
    sel_cat = st.multiselect("Catégories", cats, default=cats)
    sel_ch = st.multiselect("Canaux", chans, default=chans)

if len(period) != 2 or not sel_cat or not sel_ch:
    st.info("Choisis une période complète, au moins une catégorie et un canal.")
    st.stop()

# Filtre paramétré (pas de concaténation de valeurs dans le SQL)
filtered = con.execute("""select f.*, m.category, c.segment from fact f
               join dim_merchant m using (merchant_id) join dim_customer c using (customer_id)
               where event_ts::date between ? and ? and list_contains(?, m.category) and list_contains(?, f.channel)""",
                       [period[0], period[1], sel_cat, sel_ch]).df()
con.register("f", filtered)

k = con.execute("""select sum(amount) filter (where is_approved), count(*), count(distinct customer_id),
                          avg(is_approved::int), avg(is_fraud::int) from f""").fetchone()
st.title("Activité de paiement carte")
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Volume approuvé", f"{(k[0] or 0) / 1e6:.2f} M€")
c2.metric("Transactions", f"{k[1]:,}".replace(",", " "))
c3.metric("Clients actifs", f"{k[2]:,}".replace(",", " "))
c4.metric("Taux d'acceptation", f"{(k[3] or 0) * 100:.1f} %")
c5.metric("Taux de fraude", f"{(k[4] or 0) * 100:.2f} %")

left, right = st.columns(2)
monthly = con.execute("""select date_trunc('month', event_ts)::date as mois, category,
                                sum(amount) filter (where is_approved) as volume
                         from f group by 1, 2 order by 1""").df()
left.plotly_chart(px.bar(monthly, x="mois", y="volume", color="category", title="Volume approuvé par mois"),
                  width="stretch")
risk = con.execute("""select category, avg(is_fraud::int) * 100 as taux_fraude from f
                      group by 1 order by 2""").df()
right.plotly_chart(px.bar(risk, x="taux_fraude", y="category", orientation="h",
                          title="Taux de fraude par catégorie (%)"), width="stretch")

left, right = st.columns(2)
hours = con.execute("""select extract(hour from event_ts) as heure, avg(is_fraud::int) * 100 as taux_fraude
                       from f group by 1 order by 1""").df()
left.plotly_chart(px.line(hours, x="heure", y="taux_fraude", markers=True, title="Fraude par heure (%)"),
                  width="stretch")
seg = con.execute("""select segment, channel, avg(is_approved::int) * 100 as acceptation
                     from f group by 1, 2""").df()
right.plotly_chart(px.bar(seg, x="segment", y="acceptation", color="channel", barmode="group",
                          title="Taux d'acceptation par segment et canal (%)"), width="stretch")

with st.expander("Données détaillées (1 000 dernières transactions)"):
    st.dataframe(con.execute("select * from f order by event_ts desc limit 1000").df(), width="stretch")
