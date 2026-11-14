"""Génère un CSV synthétique de 10 000 lignes sans doublon. Usage : python scripts/gen_perf.py <graine>"""
import random
import sys

seed = int(sys.argv[1]) if len(sys.argv) > 1 else 1
random.seed(seed)
codes = ["DEPOSITS", "LOANS", "NPL_RATIO"]
with open(f"perf_10k_{seed}.csv", "w", newline="") as f:
    f.write("period,indicator_code,amount,currency\n")
    for i in range(10000):
        year, month, code = 2000 + i // 36, (i // 3) % 12 + 1, codes[i % 3]
        amount = f"{random.random():.4f}" if code == "NPL_RATIO" else f"{random.randint(1000, 9999999)}.{random.randint(0, 99):02d}"
        f.write(f"{year}-{month:02d},{code},{amount},MGA\n")
