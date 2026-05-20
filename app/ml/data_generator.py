"""Convenience wrapper to generate synthetic training data.
"""
from __future__ import annotations

from app.ml.generate_synthetic import generate


def generate_synthetic(out: str = "data/synthetic.csv", n: int = 2000, seed: int = 42):
    generate(out, n=n, seed=seed)


if __name__ == "__main__":
    import argparse
    import os

    p = argparse.ArgumentParser()
    p.add_argument("--out", default="data/synthetic.csv")
    p.add_argument("--n", type=int, default=2000)
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args()
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    generate_synthetic(args.out, args.n, args.seed)
    print(f"Wrote {args.out}")
