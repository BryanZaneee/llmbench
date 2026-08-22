"""Merge `llmbench leaderboard --json` snapshots into web/data/all.json.

Lives here rather than inline in the workflow so it can be linted and tested.
Missing snapshots are skipped, not fatal: one source failing upstream should
cost that source's rows for the day, not the whole refresh.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

SOURCES = ["huggingface", "lmarena", "aider", "bundled"]


def merge(src_dir: Path, sources: list[str]) -> dict:
    snapshots = []
    for name in sources:
        path = src_dir / f"{name}.json"
        if not path.exists() or not path.stat().st_size:
            print(f"skip {name}: no snapshot at {path}", file=sys.stderr)
            continue
        try:
            snapshots.append(json.loads(path.read_text()))
        except json.JSONDecodeError as exc:
            print(f"skip {name}: {exc}", file=sys.stderr)

    if not snapshots:
        raise SystemExit("every source failed; refusing to overwrite all.json")

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sources": [
            {
                "source": s["source"],
                "source_url": s.get("source_url"),
                "fetched_at": s.get("fetched_at"),
                "count": len(s.get("entries", [])),
            }
            for s in snapshots
        ],
        "entries": [e for s in snapshots for e in s.get("entries", [])],
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--snapshots", type=Path, required=True, help="Directory of <source>.json")
    ap.add_argument("--out", type=Path, default=Path("web/data/all.json"))
    ap.add_argument("--sources", nargs="*", default=SOURCES)
    args = ap.parse_args()

    merged = merge(args.snapshots, args.sources)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(merged, indent=2))
    names = ", ".join(s["source"] for s in merged["sources"])
    print(f"merged {len(merged['entries'])} entries from {len(merged['sources'])} sources: {names}")


if __name__ == "__main__":
    main()
