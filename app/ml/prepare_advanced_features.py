"""Prepare advanced transaction-level features from large CSVs.

This script processes a transactions CSV in chronological order and computes
per-account rolling statistics (count, mean amount, std, velocity) and
transaction-level features suitable for ML training.

Usage:
    python -m app.ml.prepare_advanced_features --input path/to/large.csv --out app/ml/advanced_features.csv --chunk 200000
"""
from __future__ import annotations

import argparse
import csv
from collections import deque
from datetime import datetime
from typing import Dict

import pandas as pd


def parse_timestamp(ts_str: str):
    # try common formats
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S.%f"):
        try:
            return datetime.strptime(ts_str, fmt)
        except Exception:
            continue
    # fallback
    return pd.to_datetime(ts_str)


def compute_features_for_chunk(df: pd.DataFrame, state: Dict):
    out_rows = []
    df = df.sort_values("txn_timestamp")
    for _, row in df.iterrows():
        acct = row.get("account_id") or row.get("entity_id") or "unknown"
        ts = (
            parse_timestamp(row["txn_timestamp"])
            if not pd.isna(row["txn_timestamp"])
            else None
        )
        amt = float(row.get("amount") or 0.0)

        st = state.setdefault(
            acct, {"window": deque(maxlen=50), "sum": 0.0, "count": 0}
        )
        win = st["window"]

        # basic historical stats
        hist_count = st["count"]
        hist_mean = (st["sum"] / st["count"]) if st["count"] > 0 else 0.0
        hist_std = pd.Series(list(win)).std() if len(win) > 1 else 0.0

        # velocity = transactions in last 24h (approx using window)
        recent_count = sum(1 for _ in win)

        is_large = 1 if amt > (hist_mean * 3 if hist_mean > 0 else 10000) else 0
        is_round = 1 if abs(amt - round(amt)) < 1e-6 and amt % 100 == 0 else 0

        features = {
            "txn_id": row.get("id"),
            "account_id": acct,
            "amount": amt,
            "hour": ts.hour if ts else None,
            "hist_count": hist_count,
            "hist_mean": hist_mean,
            "hist_std": hist_std,
            "recent_count": recent_count,
            "is_large": is_large,
            "is_round": is_round,
            "direction": row.get("direction"),
            "txn_type": row.get("txn_type"),
            "label": row.get("label") if "label" in row else None,
        }

        out_rows.append(features)

        # update state
        win.append(amt)
        st["sum"] += amt
        st["count"] += 1

    return out_rows


def prepare(input_path: str, out_path: str, chunk: int = 200000):
    state = {}
    first = True
    for chunk_df in pd.read_csv(input_path, chunksize=chunk):
        rows = compute_features_for_chunk(chunk_df, state)
        if not rows:
            continue
        if first:
            # open csv and write header
            with open(out_path, "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
                w.writeheader()
                w.writerows(rows)
            first = False
        else:
            with open(out_path, "a", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
                w.writerows(rows)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--chunk", type=int, default=200000)
    args = p.parse_args()
    prepare(args.input, args.out, chunk=args.chunk)


if __name__ == "__main__":
    main()
