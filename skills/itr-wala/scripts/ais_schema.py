#!/usr/bin/env python3
"""Print the SCHEMA of a decrypted AIS JSON - never the data.

AIS stores every table as columnLabel[] (headers) + columnData[][] (rows).
This prints headings, table titles, column names/types and row COUNTS so a
per-column whitelist can be designed. columnData is never read or printed.

Usage:  python3 ais_schema.py <AIS-decrypted.json>
"""

import json
import sys

if sys.version_info < (3, 9):
    sys.exit("itr-wala needs Python 3.9 or newer (found %d.%d)."
             % sys.version_info[:2])


def col_names(labels):
    """Column labels are either plain strings (l2) or objects (l1)."""
    out = []
    for lab in labels or []:
        if isinstance(lab, dict):
            out.append(str(lab.get("name") or lab.get("field") or "?"))
        else:
            out.append(str(lab))
    return out


def level(elem, key):
    """Row count and column names for an l1/l2 block. Data is never returned."""
    blk = elem.get(key)
    if not isinstance(blk, dict):
        return 0, []
    rows = blk.get("columnData")
    n = len(rows) if isinstance(rows, list) else 0
    names = col_names(blk.get("columnLabel"))
    types = [str(t) for t in (blk.get("columnDataType") or [])]
    return n, list(zip(names, types + [""] * (len(names) - len(types))))


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2

    data = json.load(open(argv[1]))
    print(f"# AIS schema - {argv[1]}")
    print("# Column names and row counts only. No row data is read.\n")

    for sec in data.get("partB", {}).get("sections", []) or []:
        print("=" * 78)
        print(f"SECTION  {sec.get('sectionKey')}  |  {sec.get('heading')}")
        if sec.get("title"):
            print(f"         {sec.get('title')}")
        print("=" * 78)

        # Group identical (title, columns) tables - AIS emits one per payer.
        groups = {}
        for elem in sec.get("elements", []) or []:
            title = elem.get("title") or "(untitled)"
            n1, cols1 = level(elem, "l1")
            n2, cols2 = level(elem, "l2")
            if not (n1 or n2):
                continue
            sig = (title, tuple(cols1), tuple(cols2))
            g = groups.setdefault(sig, {"tables": 0, "r1": 0, "r2": 0})
            g["tables"] += 1
            g["r1"] += n1
            g["r2"] += n2

        for (title, cols1, cols2), g in groups.items():
            print(f"\n  TABLE: {title}   "
                  f"[{g['tables']} table(s), {g['r1']} L1 rows, "
                  f"{g['r2']} L2 rows]")
            if cols1:
                print("    L1 columns:")
                for name, typ in cols1:
                    print(f"       - {name}  [{typ}]")
            if cols2:
                print("    L2 columns (drill-down):")
                for name, typ in cols2:
                    print(f"       - {name}  [{typ}]")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
