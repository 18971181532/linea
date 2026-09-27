"""Analyze cleaned data: aggregate by category, compute stats."""
import csv
import json
import sys
from collections import defaultdict

input_path = sys.argv[1] if len(sys.argv) > 1 else "data/clean.csv"
output_path = sys.argv[2] if len(sys.argv) > 2 else "data/summary.json"

by_cat = defaultdict(list)
with open(input_path, newline="", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        by_cat[row["category"]].append(int(row["value"]))

summary = {
    "total_rows": sum(len(v) for v in by_cat.values()),
    "categories": {},
    "overall": {},
}
all_values = []
for cat, values in sorted(by_cat.items()):
    all_values.extend(values)
    summary["categories"][cat] = {
        "count": len(values),
        "sum": sum(values),
        "mean": round(sum(values) / len(values), 2),
        "min": min(values),
        "max": max(values),
    }
summary["overall"] = {
    "count": len(all_values),
    "sum": sum(all_values),
    "mean": round(sum(all_values) / len(all_values), 2),
    "min": min(all_values),
    "max": max(all_values),
}

with open(output_path, "w", encoding="utf-8") as f:
    json.dump(summary, f, indent=2)

print(f"Analysis: {summary['total_rows']} rows, {len(by_cat)} categories → {output_path}")
