"""Exécute les requêtes de sql/kpis.sql sur les fichiers Parquet via DuckDB."""
from __future__ import annotations

import re
from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SQL_FILE = ROOT / "sql" / "kpis.sql"


def load_queries(path: Path = SQL_FILE) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    blocks = re.split(r"^-- name: (\w+)\s*$", text, flags=re.M)
    return {blocks[i]: blocks[i + 1].strip().rstrip(";") for i in range(1, len(blocks), 2)}


def connect(data_dir: Path = ROOT / "data") -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    for view, file in (("fact", "fact_transactions"), ("dim_customer", "dim_customer"),
                       ("dim_merchant", "dim_merchant")):
        con.execute(f"CREATE VIEW {view} AS SELECT * FROM read_parquet('{data_dir / (file + '.parquet')}')")
    return con


def run_all(con) -> dict[str, pd.DataFrame]:
    return {name: con.execute(q).df() for name, q in load_queries().items()}
