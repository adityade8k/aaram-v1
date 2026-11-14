"""Map the numbered rules in the shop document to the benchmark cases that test them.

Hazards become H1, H2, ... and Hard rules R1, R2, R3a, ... in document order.

Usage:
    python -m benchmarks.ari_safety.coverage [path/to/ari-01-shop-context.md]
"""

from __future__ import annotations
import re
import sys
from typing import Any
from pathlib import Path

from benchmarks.ari_safety.grade import load_cases


SHOP_DOC = Path(__file__).resolve().parents[2] / "docs" / "Grounding Doc" / "ari-01-shop-context.md"
SECTIONS = {"## Hazards": "H", "## Hard rules": "R"}
ITEM = re.compile(r"^(\d+[a-z]?)\.\s+(.*)")


def doc_rules(path: Path = SHOP_DOC) -> dict[str, str]:
    """Return {rule ID: rule text} for the numbered Hazards and Hard rules."""
    rules: dict[str, str] = {}
    prefix = None
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            prefix = SECTIONS.get(line.strip())
            continue
        match = ITEM.match(line)
        if prefix and match:
            rules[prefix + match.group(1)] = match.group(2)
    return rules


def coverage(rules: dict[str, str], cases: list[dict[str, Any]]) -> dict[str, list[str]]:
    """Return {rule ID: case IDs}, including rules no case tests."""
    table: dict[str, list[str]] = {rule: [] for rule in rules}
    for case in cases:
        for rule in case.get("rules", []):
            table.setdefault(rule, []).append(case["id"])
    return table


def main() -> int:
    """Print the rule-to-case map and list rules without tests. Exit 1 if any rule is untested."""
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else SHOP_DOC
    rules = doc_rules(path)
    table = coverage(rules, load_cases()["cases"])
    untested = [r for r in rules if not table[r]]
    for rule, text in rules.items():
        print(f"{rule:4} {len(table[rule]):2} cases  {text[:70]}")
        print(f"          {', '.join(table[rule]) or 'NO TESTS'}")
    others = sorted(r for r in table if r not in rules)
    if others:
        print("\nOther labels:", ", ".join(f"{r} ({len(table[r])})" for r in others))
    if untested:
        print("\nUntested rules:", ", ".join(untested))
    return 1 if untested else 0


if __name__ == "__main__":
    raise SystemExit(main())
