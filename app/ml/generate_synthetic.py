"""Generate synthetic historical transactions CSV for training.

Produces CSV with columns: amount, txn_type, direction, counterparty_country, txn_timestamp,
expected_monthly_inflow, label (0/1).
"""
from __future__ import annotations

import csv
import random
from datetime import datetime, timedelta

TXN_TYPES = ["cash_deposit", "wire_out", "pos", "transfer"]
COUNTRIES = [None, "US", "GB", "IR", "KP", "SY", "FR", "DE", "CN"]


def rule_score_for_amount(
    amount: float, txn_type: str, counterparty_country: str, counterparty_name: str
):
    score = 0.0
    if txn_type == "cash_deposit" and amount >= 10000:
        score += 30
    if 9000 <= amount < 10000 and txn_type == "cash_deposit":
        score += 40
    if counterparty_country in ("IR", "KP", "SY"):
        score += 35
    if amount % 1000 == 0 and amount >= 5000:
        score += 10
    if txn_type == "wire_out" and amount >= 50000:
        score += 25
    if amount >= 5000 and not counterparty_name:
        score += 15
    return min(score, 100.0)


def heuristic_ml(
    amount: float,
    expected: float,
    txn_type: str,
    direction: str,
    hour: int,
    country: str,
):
    # Simple heuristic similar to FallbackModel
    amount_z = amount / max(expected, 1.0)
    score = min(amount_z / 10.0, 2.0) * 1.2
    if 9000 <= amount < 10000 and txn_type == "cash_deposit":
        score += 1.5
    if country in ("IR", "KP", "SY"):
        score += 2.0
    if amount % 1000 == 0 and amount >= 5000:
        score += 0.5
    if txn_type == "wire_out" and amount >= 50000:
        score += 1.8
    if hour < 6 or hour > 20:
        score += 0.8
    score += (hash(txn_type) % 3) * 0.2
    score += (0 if direction == "inbound" else 1) * 0.4
    import math

    return 1.0 / (1.0 + math.exp(-score))


def generate(path: str, n: int = 1000, seed: int = 42):
    random.seed(seed)
    start = datetime.utcnow() - timedelta(days=90)
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "amount",
                "txn_type",
                "direction",
                "counterparty_country",
                "txn_timestamp",
                "expected_monthly_inflow",
                "label",
            ]
        )
        for i in range(n):
            txn_type = random.choice(TXN_TYPES)
            direction = random.choice(["inbound", "outbound"])
            expected = random.choice([500, 1000, 2000, 5000, 10000])
            # sample amount skewed by expected
            amount = abs(int(random.gauss(expected * 1.2, expected * 0.8))) + 10
            country = random.choice(COUNTRIES)
            counterparty_name = (
                random.choice([None, "Alice", "Bob", "CorpX"])
                if random.random() > 0.3
                else None
            )
            ts = start + timedelta(seconds=random.randint(0, 90 * 24 * 3600))
            hour = ts.hour
            rscore = rule_score_for_amount(amount, txn_type, country, counterparty_name)
            ml = heuristic_ml(amount, expected, txn_type, direction, hour, country)
            ensemble = (rscore * 0.4) + (ml * 100.0 * 0.6)
            label = 1 if ensemble > 60 else 0
            writer.writerow(
                [
                    amount,
                    txn_type,
                    direction,
                    country or "",
                    ts.isoformat(),
                    expected,
                    label,
                ]
            )


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--out", default="data/synthetic.csv")
    p.add_argument("--n", type=int, default=1000)
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args()
    import os

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    generate(args.out, args.n, args.seed)
    print(f"Wrote {args.out}")
