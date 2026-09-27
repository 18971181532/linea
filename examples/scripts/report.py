"""Generate a text report from the summary JSON."""
import json
import sys
from datetime import datetime

input_path = sys.argv[1] if len(sys.argv) > 1 else "data/summary.json"
output_path = sys.argv[2] if len(sys.argv) > 2 else "data/report.txt"

with open(input_path, encoding="utf-8") as f:
    summary = json.load(f)

lines = [
    "=" * 50,
    "  DATA ANALYSIS REPORT",
    f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
    "=" * 50,
    "",
    f"Total rows: {summary['total_rows']}",
    f"Categories: {len(summary['categories'])}",
    "",
    "OVERALL:",
    f"  Count: {summary['overall']['count']}",
    f"  Sum:   {summary['overall']['sum']}",
    f"  Mean:  {summary['overall']['mean']}",
    f"  Min:   {summary['overall']['min']}",
    f"  Max:   {summary['overall']['max']}",
    "",
    "BY CATEGORY:",
]
for cat, stats in summary["categories"].items():
    lines.append(f"  {cat}:")
    lines.append(f"    count={stats['count']}, sum={stats['sum']}, mean={stats['mean']}")
    lines.append(f"    min={stats['min']}, max={stats['max']}")
lines.append("")
lines.append("=" * 50)

with open(output_path, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))

print(f"Report written to {output_path}")
