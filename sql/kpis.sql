-- Requêtes KPI (DuckDB). Chaque bloc est nommé `-- name: <kpi>` et chargé par analytics/kpis.py.
-- Les vues fact / dim_customer / dim_merchant sont créées sur les fichiers Parquet.

-- name: monthly_overview
-- Vue mensuelle : volume, transactions, clients actifs, panier moyen, acceptation, fraude, évolution M-1.
with m as (
    select date_trunc('month', event_ts)::date                     as month,
           count(*)                                                as transactions,
           count(distinct customer_id)                             as active_customers,
           sum(amount) filter (where is_approved)                  as approved_volume,
           avg(amount)                                             as avg_ticket,
           avg(is_approved::int)                                   as approval_rate,
           sum(amount) filter (where is_fraud) / sum(amount)       as fraud_rate_amount
    from fact group by 1
)
select *,
       approved_volume / lag(approved_volume) over (order by month) - 1 as volume_mom
from m order by month;

-- name: category_performance
-- Contribution de chaque catégorie au volume et au risque, avec rang.
select m.category,
       count(*)                                                    as transactions,
       sum(f.amount) filter (where f.is_approved)                  as approved_volume,
       sum(f.amount) filter (where f.is_approved)
         / sum(sum(f.amount) filter (where f.is_approved)) over () as share_of_volume,
       avg(f.is_fraud::int)                                        as fraud_rate,
       sum(f.amount) filter (where f.is_fraud)                     as fraud_amount,
       rank() over (order by avg(f.is_fraud::int) desc)            as risk_rank
from fact f join dim_merchant m using (merchant_id)
group by 1 order by approved_volume desc;

-- name: channel_funnel
-- Acceptation et fraude par canal : où sont les refus et où est le risque.
select channel,
       count(*)                     as transactions,
       avg(is_approved::int)        as approval_rate,
       avg(is_fraud::int)           as fraud_rate,
       avg(amount)                  as avg_ticket
from fact group by 1 order by transactions desc;

-- name: fraud_by_hour
-- Profil horaire de la fraude (part des transactions frauduleuses par heure).
select extract(hour from event_ts) as hour,
       count(*)                     as transactions,
       avg(is_fraud::int)           as fraud_rate
from fact group by 1 order by 1;

-- name: cohort_retention
-- Rétention par cohorte d'acquisition : part des clients d'une cohorte encore actifs N mois plus tard.
with first_tx as (
    select customer_id, date_trunc('month', min(event_ts))::date as cohort
    from fact group by 1
), activity as (
    select distinct f.customer_id, ft.cohort,
           datediff('month', ft.cohort, date_trunc('month', f.event_ts)::date) as month_n
    from fact f join first_tx ft using (customer_id)
), sizes as (
    select cohort, count(distinct customer_id) as cohort_size from activity where month_n = 0 group by 1
)
select a.cohort, a.month_n, s.cohort_size,
       count(distinct a.customer_id) / s.cohort_size as retention
from activity a join sizes s using (cohort)
group by 1, 2, 3 order by 1, 2;

-- name: segment_value
-- Valeur par segment : dépense mensuelle moyenne par client actif.
select c.segment,
       count(distinct f.customer_id)                                         as customers,
       sum(f.amount) filter (where f.is_approved)
         / count(distinct (f.customer_id, date_trunc('month', f.event_ts)))  as spend_per_active_month
from fact f join dim_customer c using (customer_id)
group by 1 order by spend_per_active_month desc;

-- name: top_merchants_by_city
-- Top 3 des marchands par ville (volume approuvé) — fenêtre ROW_NUMBER.
select * from (
    select m.city, f.merchant_id, m.category,
           sum(f.amount) filter (where f.is_approved) as approved_volume,
           row_number() over (partition by m.city order by sum(f.amount) filter (where f.is_approved) desc) as rk
    from fact f join dim_merchant m using (merchant_id)
    group by 1, 2, 3
) where rk <= 3 order by city, rk;
