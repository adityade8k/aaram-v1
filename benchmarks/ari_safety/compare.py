"""Compare two benchmark result files, e.g. two doc contexts run on the same cases.

Usage:
    python -m benchmarks.ari_safety.compare results/<A>.json results/<B>.json
"""

from __future__ import annotations
import sys
import json
from typing import Any
from pathlib import Path


def _runs(result: dict[str, Any]) -> tuple[int, int, int]:
    runs = result["runs"]
    return sum(not r["failures"] for r in runs), sum(r["researched"] for r in runs), len(runs)


def compare(a: dict[str, Any], b: dict[str, Any]) -> list[str]:
    """Return report lines: per-category totals, then every case whose outcome differs."""
    by_id_a = {r["id"]: r for r in a["results"]}
    by_id_b = {r["id"]: r for r in b["results"]}
    shared = [i for i in by_id_a if i in by_id_b]
    label_a, label_b = a.get("label", "A"), b.get("label", "B")
    lines = [f"{'category':10} {label_a:>14} {label_b:>14}   (cases passed on every run)"]
    categories = sorted({by_id_a[i]["category"] for i in shared})
    for category in categories:
        ids = [i for i in shared if by_id_a[i]["category"] == category]
        pass_a = sum(by_id_a[i]["passed"] for i in ids)
        pass_b = sum(by_id_b[i]["passed"] for i in ids)
        lines.append(f"{category:10} {pass_a:>11}/{len(ids):<2} {pass_b:>11}/{len(ids):<2}")
    lines.append("")
    lines.append(f"{'case':22} {label_a:>18} {label_b:>18}   (runs passed / runs researched / runs)")
    for case_id in shared:
        ra, rb = by_id_a[case_id], by_id_b[case_id]
        if ra["passed"] == rb["passed"] and _runs(ra) == _runs(rb):
            continue
        cells = ["{}/{}/{}".format(*_runs(r)) for r in (ra, rb)]
        lines.append(f"{case_id:22} {cells[0]:>18} {cells[1]:>18}")
    missing = sorted(set(by_id_a) ^ set(by_id_b))
    if missing:
        lines.append(f"\nOnly in one file (not compared): {', '.join(missing)}")
    return lines


def main() -> int:
    """Print the comparison of two result files."""
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    a, b = (json.loads(Path(p).read_text(encoding="utf-8")) for p in sys.argv[1:])
    print("\n".join(compare(a, b)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
