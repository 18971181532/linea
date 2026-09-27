"""Clean raw data: remove rows with missing values, normalize categories."""
import csv
import sys

input_path = sys.argv[1] if len(sys.argv) > 1 else "data/raw.csv"
output_path = sys.argv[2] if len(sys.argv) > 2 else "data/clean.csv"

rows = []
with open(input_path, newline="", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        if not row["value"]:
            continue
        row["value"] = int(row["value"])
        row["category"] = row["category"].upper()
        rows.append(row)

with open(output_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=["id", "name", "value", "category", "date"])
    writer.writeheader()
    writer.writerows(rows)

print(f"Cleaned: {len(rows)} rows written to {output_path}")
