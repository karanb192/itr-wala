#!/usr/bin/env python3
"""Print the SHAPE of a JSON file - key paths, types, string lengths.

Never prints a value. Use this to learn what fields exist so a mapping can be
written against key names alone.

Usage:  python3 shape.py <file.json> [--no-lengths] [--collapse | --full]

By default, files with more than 200 leaf fields collapse array indices
(accounts[0], accounts[1], ... -> accounts[*]) and report one row per distinct
path pattern with an occurrence count. --full forces per-leaf output;
--collapse forces the collapsed view.
"""

import json
import re
import sys

if sys.version_info < (3, 9):
    sys.exit("itr-wala needs Python 3.9 or newer (found %d.%d)."
             % sys.version_info[:2])

COLLAPSE_THRESHOLD = 200


def walk(node, path=""):
    """Yield (path, type_name, length_or_None). Values are never yielded."""
    if isinstance(node, dict):
        if not node:
            yield path or "$", "object(empty)", None
        for k, v in node.items():
            child = f"{path}.{k}" if path else k
            yield from walk(v, child)
    elif isinstance(node, list):
        if not node:
            yield path or "$", "array(empty)", None
        for i, v in enumerate(node):
            yield from walk(v, f"{path}[{i}]")
    elif isinstance(node, str):
        yield path, "string", len(node)
    elif isinstance(node, bool):
        yield path, "bool", None
    elif node is None:
        yield path, "null", None
    elif isinstance(node, (int, float)):
        # Type only. Magnitude is withheld - it can be identifying.
        yield path, "number", None
    else:
        yield path, type(node).__name__, None


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2

    show_len = "--no-lengths" not in argv

    try:
        with open(argv[1]) as fh:
            data = json.load(fh)
    except json.JSONDecodeError as exc:
        # lineno/colno only - the offending text is never echoed.
        print(f"Not valid JSON (line {exc.lineno}, col {exc.colno}).",
              file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"Cannot read file: {exc.strerror}", file=sys.stderr)
        return 1

    rows = list(walk(data))

    collapse = "--collapse" in argv or (
        len(rows) > COLLAPSE_THRESHOLD and "--full" not in argv
    )

    if not collapse:
        width = max((len(p) for p, _, _ in rows), default=10)
        print(f"# shape of {argv[1]} - {len(rows)} leaf fields, "
              f"no values shown\n")
        for path, kind, length in rows:
            note = f"  ({length} chars)" if (show_len and length is not None) else ""
            print(f"{path:<{width}}  {kind}{note}")
        return 0

    # Collapsed: one row per distinct path pattern.
    groups = {}
    for path, kind, length in rows:
        pattern = re.sub(r"\[\d+\]", "[*]", path)
        g = groups.setdefault(pattern, {"n": 0, "kinds": set(), "lens": []})
        g["n"] += 1
        g["kinds"].add(kind)
        if length is not None:
            g["lens"].append(length)

    width = max((len(p) for p in groups), default=10)
    print(f"# shape of {argv[1]} - {len(rows):,} leaf fields collapsed to "
          f"{len(groups)} distinct patterns. No values shown.")
    print("# columns: path pattern | occurrences | type(s) | string length range\n")

    for pattern, g in sorted(groups.items()):
        kinds = "/".join(sorted(g["kinds"]))
        if show_len and g["lens"]:
            lo, hi = min(g["lens"]), max(g["lens"])
            span = f"  len {lo}" + (f"-{hi}" if hi != lo else "")
        else:
            span = ""
        print(f"{pattern:<{width}}  x{g['n']:<6} {kinds}{span}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
