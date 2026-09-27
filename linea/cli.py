"""Command-line interface for Linea — data provenance tracker."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import List, Optional

from . import __version__
from .store import Store
from .runner import run_command
from .lineage import Lineage
from .verify import verify_run, verify_file
from .graph import build_graph


def _store(args) -> Store:
    return Store(base_dir=getattr(args, "dir", "."))


def cmd_init(args) -> int:
    store = Store(base_dir=args.dir)
    if store.exists() and not args.force:
        print(f"linea store already exists at {store.store_path}")
        return 0
    store.init()
    print(f"Initialized linea store at {store.store_path}")
    return 0


def cmd_run(args) -> int:
    store = _store(args)
    if not store.exists():
        store.init()
    if not args.command:
        print("error: no command specified", file=sys.stderr)
        return 2
    # Strip leading "--" separator if present
    cmd_parts = args.command
    if cmd_parts and cmd_parts[0] == "--":
        cmd_parts = cmd_parts[1:]
    command = " ".join(cmd_parts)
    inputs = [p for p in (args.inputs or "").split(",") if p]
    outputs = [p for p in (args.outputs or "").split(",") if p]
    tags = [t for t in (args.tags or "").split(",") if t]

    run = run_command(
        command=command,
        inputs=inputs,
        outputs=outputs,
        store=store,
        cwd=args.dir,
        tags=tags,
        notes=args.notes or "",
    )
    status = "OK" if run["exit_code"] == 0 else "FAILED"
    print(f"[{status}] {run['id']}")
    print(f"  command: {command}")
    print(f"  duration: {run['duration_ms']}ms, exit: {run['exit_code']}")
    print(f"  inputs: {len(run['inputs'])}, outputs: {len(run['outputs'])}")
    for o in run["outputs"]:
        sha = (o.get('sha256') or 'missing')[:12]
        print(f"    → {o['path']} ({o.get('size', 0)} bytes, sha256:{sha})")
    return run["exit_code"] if isinstance(run["exit_code"], int) and run["exit_code"] >= 0 else 1


def cmd_trace(args) -> int:
    store = _store(args)
    lin = Lineage(store)
    tree = lin.trace(args.file, max_depth=args.depth)
    _print_tree(tree, prefix="", is_last=True)
    return 0


def _print_tree(node, prefix, is_last):
    connector = "└── " if is_last else "├── "
    label = node["file"]
    extra = ""
    if node.get("produced_by"):
        pb = node["produced_by"]
        extra = f"  ← {pb['command'][:50]} ({pb.get('duration_ms','?')}ms)"
    elif node.get("source") == "external":
        extra = "  [external/untracked]"
    if node.get("hash"):
        extra += f"  sha:{node['hash'][:8]}"
    print(f"{prefix}{connector}{label}{extra}")
    inputs = node.get("inputs", [])
    for i, child in enumerate(inputs):
        child_prefix = prefix + ("    " if is_last else "│   ")
        _print_tree(child, child_prefix, i == len(inputs) - 1)


def cmd_impact(args) -> int:
    store = _store(args)
    lin = Lineage(store)
    if args.flat:
        files = lin.all_downstream_files(args.file)
        print(f"Files affected if '{args.file}' changes:")
        for f in files:
            print(f"  → {f}")
        print(f"\n{len(files)} downstream files")
    else:
        tree = lin.impact(args.file, max_depth=args.depth)
        _print_impact_tree(tree, prefix="", is_last=True)
    return 0


def _print_impact_tree(node, prefix, is_last):
    connector = "└── " if is_last else "├── "
    print(f"{prefix}{connector}{node['file']}")
    for consumer in node.get("consumed_by", []):
        print(f"{prefix}{'    ' if is_last else '│   '}    ↳ {consumer['command'][:50]}")
        outputs = consumer.get("outputs", [])
        for i, child in enumerate(outputs):
            child_prefix = prefix + ("    " if is_last else "│   ") + "    "
            _print_impact_tree(child, child_prefix, i == len(outputs) - 1)


def cmd_orphans(args) -> int:
    store = _store(args)
    lin = Lineage(store)
    orphans = lin.orphans()
    if not orphans:
        print("No orphan files — everything is tracked.")
        return 0
    print(f"{'PATH':50s} {'SIZE':>10s}")
    print("-" * 62)
    for o in orphans[:args.limit]:
        print(f"{o['path']:50s} {o['size']:>10d}")
    print(f"\n{len(orphans)} orphan files (showing top {min(args.limit, len(orphans))})")
    return 0


def cmd_list(args) -> int:
    store = _store(args)
    runs = store.list_runs(limit=args.limit, tag=args.tag)
    if not runs:
        print("No runs recorded.")
        return 0
    print(f"{'ID':28s} {'EXIT':>4s} {'DUR':>8s} {'COMMAND':40s}")
    print("-" * 84)
    for r in runs:
        ts = time.strftime("%H:%M:%S", time.localtime(r.get("started_at", 0)))
        cmd = r["command"][:38]
        print(f"{r['id']:28s} {r.get('exit_code','?'):>4} {r.get('duration_ms',0):>7.0f}ms {cmd:40s}")
    print(f"\n{runs.__len__()} runs")
    return 0


def cmd_show(args) -> int:
    store = _store(args)
    run = store.get_run(args.run_id)
    if not run:
        print(f"error: run {args.run_id} not found", file=sys.stderr)
        return 1
    print(json.dumps(run, indent=2, ensure_ascii=False, default=str))
    return 0


def cmd_verify(args) -> int:
    store = _store(args)
    if args.run_id:
        result = verify_run(args.run_id, store, timeout=args.timeout)
    elif args.file:
        result = verify_file(args.file, store)
        if result is None:
            print(f"No run found that produced '{args.file}'")
            return 1
    else:
        print("error: specify --run-id or --file", file=sys.stderr)
        return 2

    d = result.to_dict()
    status = "REPRODUCIBLE" if result.reproducible else "NOT REPRODUCIBLE"
    print(f"[{status}] {result.run_id}")
    print(f"  command: {d.get('command', '')}")
    print(f"  exit code: original={d.get('original_exit_code')}, new={d.get('new_exit_code')} (match={d.get('exit_code_match')})")
    print(f"  duration: original={d.get('original_duration_ms')}ms, new={d.get('new_duration_ms')}ms")
    for f in d.get("files", []):
        mark = "✓" if f["match"] else "✗"
        print(f"  {mark} {f['path']}")
        if not f["match"]:
            print(f"      original: {f.get('original_hash')}")
            print(f"      new:      {f.get('new_hash')}")
    return 0 if result.reproducible else 1


def cmd_compare(args) -> int:
    store = _store(args)
    lin = Lineage(store)
    result = lin.compare_runs(args.run_a, args.run_b)
    if "error" in result:
        print(f"error: {result['error']}", file=sys.stderr)
        return 1
    print(f"Comparing {args.run_a} vs {args.run_b}")
    print(f"  same command: {result['same_command']}")
    print(f"  exit codes: {result['exit_a']} vs {result['exit_b']}")
    print(f"  durations: {result['duration_a']}ms vs {result['duration_b']}ms")
    if result["files_changed"]:
        print(f"\n  Changed files ({len(result['files_changed'])}):")
        for f in result["files_changed"]:
            print(f"    ! {f['path']}")
    if result["files_added"]:
        print(f"\n  Added files: {', '.join(result['files_added'])}")
    if result["files_removed"]:
        print(f"\n  Removed files: {', '.join(result['files_removed'])}")
    if not result["files_changed"] and not result["files_added"] and not result["files_removed"]:
        print("\n  No file differences.")
    return 0


def cmd_stats(args) -> int:
    store = _store(args)
    s = store.stats()
    print(f"Runs:        {s['total_runs']}")
    print(f"  successful: {s['successful']}")
    print(f"  failed:     {s['failed']}")
    print(f"Inputs:      {s['total_inputs']}")
    print(f"Outputs:     {s['total_outputs']}")
    print(f"Unique files:{s['unique_files']}")
    return 0


def cmd_serve(args) -> int:
    from .server import serve
    store = _store(args)
    if not store.exists():
        print("error: no linea store. Run 'linea init' first.", file=sys.stderr)
        return 2
    serve(store, host=args.host, port=args.port)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="linea",
        description="Local-first data provenance tracker — trace how every file was made.",
    )
    p.add_argument("--version", action="version", version=f"linea {__version__}")
    p.add_argument("-C", "--dir", default=".", help="Project directory (default: current)")
    sub = p.add_subparsers(dest="command", metavar="<command>")

    s = sub.add_parser("init", help="Initialize a provenance store")
    s.add_argument("--force", action="store_true")
    s.set_defaults(func=cmd_init)

    s = sub.add_parser("run", help="Run a command and record provenance")
    s.add_argument("command", nargs=argparse.REMAINDER, help="Command to run")
    s.add_argument("-i", "--inputs", default="", help="Comma-separated input files")
    s.add_argument("-o", "--outputs", default="", help="Comma-separated output files")
    s.add_argument("-t", "--tags", default="", help="Comma-separated tags")
    s.add_argument("-n", "--notes", default="", help="Free-text notes")
    s.set_defaults(func=cmd_run)

    s = sub.add_parser("trace", help="Trace the ancestry of a file")
    s.add_argument("file")
    s.add_argument("--depth", type=int, default=20)
    s.set_defaults(func=cmd_trace)

    s = sub.add_parser("impact", help="Show downstream impact of a file change")
    s.add_argument("file")
    s.add_argument("--depth", type=int, default=20)
    s.add_argument("--flat", action="store_true", help="Flat list of affected files")
    s.set_defaults(func=cmd_impact)

    s = sub.add_parser("orphans", help="Find files not tracked by any run")
    s.add_argument("--limit", type=int, default=50)
    s.set_defaults(func=cmd_orphans)

    s = sub.add_parser("list", help="List recorded runs")
    s.add_argument("--limit", type=int, default=20)
    s.add_argument("--tag", default=None)
    s.set_defaults(func=cmd_list)

    s = sub.add_parser("show", help="Show full details of a run")
    s.add_argument("run_id")
    s.set_defaults(func=cmd_show)

    s = sub.add_parser("verify", help="Re-run and verify reproducibility")
    s.add_argument("--run-id", default=None)
    s.add_argument("--file", default=None)
    s.add_argument("--timeout", type=int, default=300)
    s.set_defaults(func=cmd_verify)

    s = sub.add_parser("compare", help="Compare two runs")
    s.add_argument("run_a")
    s.add_argument("run_b")
    s.set_defaults(func=cmd_compare)

    s = sub.add_parser("stats", help="Show store statistics")
    s.set_defaults(func=cmd_stats)

    s = sub.add_parser("serve", help="Start the web dashboard")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8765)
    s.set_defaults(func=cmd_serve)

    return p


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        parser.print_help()
        return 1
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
