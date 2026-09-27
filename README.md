# 🔗 Linea

**Local-first data provenance tracker.** Trace how every file was made, verify
reproducibility, and explore the full lineage graph — all with **zero third-party
dependencies**.

[![tests](https://github.com/18971181532/linea/actions/workflows/test.yml/badge.svg)](https://github.com/18971181532/linea/actions/workflows/test.yml)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue)]()
[![License: MIT](https://img.shields.io/badge/license-MIT-green)]()
[![dependencies](https://img.shields.io/badge/dependencies-zero-success)]()

---

## Why Linea?

In data science and research, the question "how was this file generated?" is
asked constantly — and answered poorly. Linea wraps your commands and records
the full provenance: inputs (with hashes), outputs (with hashes), command,
environment, timing, and exit code. Then it lets you:

- **Trace** any file back through its entire dependency chain
- **Verify** that a result is reproducible by re-running and comparing hashes
- **Analyze impact** — if this input changes, what downstream files break?
- **Find orphans** — files in your project with no provenance record
- **Compare runs** — what changed between two executions?
- **Visualize** the provenance DAG in an interactive dashboard

## Quick start

```bash
# Initialize a provenance store in your project
linea init

# Run a command, declaring its inputs and outputs
linea run -i data/raw.csv -o data/clean.csv -- python scripts/clean.py data/raw.csv data/clean.csv
linea run -i data/clean.csv -o data/summary.json -- python scripts/analyze.py data/clean.csv data/summary.json
linea run -i data/summary.json -o data/report.txt -- python scripts/report.py data/summary.json data/report.txt

# Trace where a file came from
linea trace data/report.txt

# See what breaks if an input changes
linea impact data/raw.csv --flat

# Verify reproducibility
linea verify --file data/summary.json

# Open the dashboard
linea serve
```

## Trace output example

```
$ linea trace data/report.txt
└── data/report.txt  ← python scripts/report.py ... (12.3ms)
    └── data/summary.json  ← python scripts/analyze.py ... (45.1ms)
        └── data/clean.csv  ← python scripts/clean.py ... (23.7ms)
            └── data/raw.csv  [external/untracked]
```

## Architecture

```
linea/
├── hasher.py      # SHA-256 file hashing (streaming for large files)
├── store.py       # JSON-file provenance store (.linea/runs/)
├── runner.py      # Command wrapper: hash inputs → execute → hash outputs
├── lineage.py     # Trace ancestry, impact analysis, orphan detection, run comparison
├── verify.py      # Re-execute and compare output hashes
├── graph.py       # Bipartite DAG construction for visualization
├── cli.py         # init/run/trace/impact/orphans/list/show/verify/compare/stats/serve
├── server.py      # http.server REST API + static dashboard
└── web/           # Vanilla-JS dashboard, Canvas provenance graph
```

Data model — each run records:

```json
{
  "id": "run_1727328000000_a1b2c3d4",
  "command": "python scripts/analyze.py clean.csv summary.json",
  "cwd": "/path/to/project",
  "started_at": 1727328000.123,
  "finished_at": 1727328000.456,
  "duration_ms": 333.0,
  "exit_code": 0,
  "inputs":  [{"path": "clean.csv", "sha256": "abc...", "size": 2048}],
  "outputs": [{"path": "summary.json", "sha256": "def...", "size": 512}],
  "environment": {"os": "...", "python": "3.11.4", "git_commit": "..."},
  "tags": ["experiment-1"],
  "notes": ""
}
```

## CLI commands

| Command | Description |
|---|---|
| `linea init` | Initialize `.linea/` store in current directory |
| `linea run -i in.csv -o out.json -- <command>` | Run command and record provenance |
| `linea trace <file>` | Print full ancestry tree of a file |
| `linea impact <file>` | Show downstream dependencies if file changes |
| `linea orphans` | List files not tracked by any run |
| `linea list` | List all recorded runs |
| `linea show <run_id>` | Show full run details (stdout/stderr/env) |
| `linea verify --file <file>` | Re-run and compare output hashes |
| `linea compare <run_a> <run_b>` | Diff two runs (inputs/outputs/hashes) |
| `linea stats` | Show store statistics |
| `linea serve` | Start the web dashboard (default port 8765) |

## Web dashboard

```bash
linea serve
```

Open <http://127.0.0.1:8765>. Features:

- **Provenance graph** — bipartite DAG (green=file, gold=run, red=failed),
  laid out by topological depth with bezier-curve edges
- **Run list** — all recorded runs with status, command, duration; click to inspect
- **File detail** — click a file node to see its producer, dependencies, and downstream impact
- **Run detail** — click a run to see full command, inputs/outputs with hashes, stdout/stderr, environment

## REST API

| Method | Path | Description |
|---|---|---|
| GET | `/api/stats` | Store statistics |
| GET | `/api/runs?limit=50` | Run list (no stdout/stderr) |
| GET | `/api/run?id=...` | Full run details |
| GET | `/api/graph?max_runs=50` | Provenance graph (nodes + edges) |
| GET | `/api/trace?file=...` | File ancestry tree |
| GET | `/api/impact?file=...` | Downstream impact tree |
| GET | `/api/orphans` | Untracked files |
| GET | `/api/verify?run_id=...` | Re-run and verify reproducibility |

## Verification

`linea verify` re-executes the original command and compares every output
file's SHA-256 hash against the recorded value. A match means the result is
reproducible; a mismatch flags non-determinism (timestamps, random seeds,
external API calls, etc.).

```
$ linea verify --file data/summary.json
[REPRODUCIBLE] run_...a1b2c3d4
  command: python scripts/analyze.py clean.csv summary.json
  exit code: original=0, new=0 (match=True)
  ✓ data/summary.json
```

## Impact analysis

`linea impact data/raw.csv --flat` returns a flat list of every downstream
file that depends (directly or transitively) on the given file — essential
for understanding the blast radius of a data change.

## Orphan detection

`linea orphans` scans your project directory and lists files that don't
appear in any run's inputs or outputs — useful for finding forgotten
intermediate files, old results, or uncommitted data.

## Install

```bash
git clone https://github.com/18971181532/linea.git
cd linea
python -m pip install -e .
```

Requires Python 3.9+. No dependencies.

## Examples

See [`examples/`](examples/) for a complete 3-step pipeline (clean → analyze
→ report) with sample data. Run it with:

```bash
cd examples
linea init
linea run -i data/raw.csv -o data/clean.csv -- python scripts/clean.py data/raw.csv data/clean.csv
linea run -i data/clean.csv -o data/summary.json -- python scripts/analyze.py data/clean.csv data/summary.json
linea run -i data/summary.json -o data/report.txt -- python scripts/report.py data/summary.json data/report.txt
linea trace data/report.txt
linea serve
```

## Development

```bash
python -m unittest discover -s tests -v
```

CI runs on Python 3.9–3.12.

## Roadmap

- [ ] Automatic input/output detection (scan filesystem before/after)
- [ ] Diff of output file contents (not just hashes)
- [ ] Time-based provenance timeline view
- [ ] Export provenance as RO-Crate or W3C PROV
- [ ] Integration with Make / Snakemake / Airflow
- [ ] Pluggable storage backends (SQLite, remote)
- [ ] Real-time monitoring mode (watch and auto-record)

## License

MIT — see [LICENSE](LICENSE).
