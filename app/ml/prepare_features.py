"""Prepare feature matrix CSV from raw transaction CSV using existing feature extractor.

Usage:
    python -m app.ml.prepare_features --input data/synthetic.csv --out app/ml/features_matrix.csv --preview 10
"""
from __future__ import annotations

import argparse
import csv

from app.ml.features import extract_features


def prepare(input_path: str, out_path: str):
    rows = []
    with open(input_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(r)

    header = [
        "amount_zscore",
        "is_just_below_10k",
        "is_high_risk",
        "is_round_number",
        "is_large_wire",
        "hour",
        "txn_type_encoded",
        "direction_encoded",
        "label",
    ]

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        for r in rows:
            feats = extract_features(r)
            label = r.get("label", "0")
            writer.writerow([*feats, label])


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--preview", type=int, default=10)
    args = p.parse_args()

    prepare(args.input, args.out)

    # print preview
    with open(args.out, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            print(line.strip())
            if i >= args.preview:
                break


if __name__ == "__main__":
    main()
