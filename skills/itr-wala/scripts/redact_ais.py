#!/usr/bin/env python3
"""Emit a REDACTED view of a decrypted AIS JSON.

Whitelist-based: only approved columns are emitted. Identity columns are
replaced with stable pseudonyms. Anything not explicitly listed is dropped,
so an unexpected column fails closed rather than leaking.

Sums are computed here, in code - never by hand.

Usage:  python3 redact_ais.py <AIS-decrypted.json> [--rows]
"""

import json
import re
import sys
from collections import defaultdict

if sys.version_info < (3, 9):
    sys.exit("itr-wala needs Python 3.9 or newer (found %d.%d)."
             % sys.version_info[:2])

# Columns safe to display: amounts, dates, codes, status.
SHOW = {
    "Quarter", "Reported On", "Date of Payment/Credit", "Date of Receipt/ Debit",
    "Amount Paid/Credited", "Dividend Amount", "Interest amount",
    "Amount Received/Debited", "TDS Deducted", "TDS Deposited",
    "Tax Collected", "TCS Deposited", "Status", "Feedback", "Account Type",
    "Information Category", "Information Code", "Information Category Code",
    "Count", "Amount", "Derived Amount", "Qualifies For",
}

# Identity columns -> stable pseudonym prefix.
PSEUDO = {
    "Information Source": "PAYER",
    "TSN": "TXN",
    "Account Number": "ACCT",
}

# Never displayed; cardinality only.
PROBE = {"Information Description"}

# Columns whose sums are meaningful.
NUMERIC = {
    "Amount Paid/Credited", "Dividend Amount", "Interest amount",
    "Amount Received/Debited", "TDS Deducted", "TDS Deposited",
    "Tax Collected", "TCS Deposited", "Amount", "Derived Amount",
}

_pseudonyms = defaultdict(dict)


def tag(kind, value):
    """Stable pseudonym per distinct value, e.g. PAYER-01."""
    book = _pseudonyms[kind]
    if value not in book:
        book[value] = f"{kind}-{len(book) + 1:02d}"
    return book[value]


def num(v):
    """Parse an amount string. Returns None if not numeric."""
    if v is None:
        return None
    s = str(v).replace(",", "").strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def col_names(labels):
    out = []
    for lab in labels or []:
        if isinstance(lab, dict):
            out.append(str(lab.get("name") or lab.get("field") or "?"))
        else:
            out.append(str(lab))
    return out


def read_block(elem, key):
    blk = elem.get(key)
    if not isinstance(blk, dict):
        return [], []
    return col_names(blk.get("columnLabel")), (blk.get("columnData") or [])


def rupees(x):
    return f"{x:,.2f}"


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2

    show_rows = "--rows" in argv
    data = json.load(open(argv[1]))

    probe_values = defaultdict(set)
    print("# REDACTED AIS view - whitelist applied, identities pseudonymised.")
    print("# Sums computed in code. Amounts in rupees.\n")

    for sec in data.get("partB", {}).get("sections", []) or []:
        elements = sec.get("elements", []) or []
        if not elements:
            continue

        # Bucket elements by table title.
        by_title = defaultdict(list)
        for elem in elements:
            by_title[elem.get("title") or "(untitled)"].append(elem)

        printed_header = False
        for title, elems in by_title.items():
            rows_out = []
            inactive = defaultdict(float)
            sums = defaultdict(float)
            counts = defaultdict(int)
            quarters = defaultdict(lambda: defaultdict(float))

            for elem in elems:
                # Payer comes from the L2 drill-down.
                l2names, l2rows = read_block(elem, "l2")
                payer = "PAYER-??"
                for r in l2rows:
                    for name, val in zip(l2names, r):
                        if name in PROBE:
                            probe_values[name].add(str(val))
                        if name == "Information Source" and val:
                            payer = tag("PAYER", str(val))

                l1names, l1rows = read_block(elem, "l1")
                for r in l1rows:
                    # AIS supersedes corrected entries by flagging them
                    # Inactive. They must not enter any total.
                    status = dict(zip(l1names, r)).get("Status")
                    if str(status).strip().lower() == "inactive":
                        inactive["rows"] += 1
                        for name, val in zip(l1names, r):
                            n = num(val)
                            if n is not None and name in NUMERIC:
                                inactive[name] += n
                        continue

                    rec = {"payer": payer}
                    for name, val in zip(l1names, r):
                        if name in PROBE:
                            probe_values[name].add(str(val))
                            continue
                        if name in PSEUDO:
                            rec[name] = tag(PSEUDO[name], str(val)) if val else ""
                            continue
                        if name not in SHOW:
                            continue          # fail closed
                        rec[name] = val
                        n = num(val)
                        if n is not None and name in NUMERIC:
                            sums[name] += n
                            counts[name] += 1
                    rows_out.append(rec)

                    q = rec.get("Quarter")
                    for money in ("Amount Paid/Credited", "Dividend Amount",
                                  "Interest amount", "Amount Received/Debited",
                                  "TDS Deducted", "Tax Collected"):
                        n = num(rec.get(money))
                        if q and n is not None:
                            quarters[str(q)][money] += n

            if not rows_out:
                continue

            if not printed_header:
                print("=" * 74)
                print(f"SECTION {sec.get('sectionKey')} - {sec.get('heading')}")
                print("=" * 74)
                printed_header = True

            print(f"\nTABLE: {title}   "
                  f"[{len(elems)} table(s), {len(rows_out)} rows, "
                  f"{len(set(r['payer'] for r in rows_out))} distinct payers]")

            for name in sorted(sums):
                print(f"    SUM {name:<26} {rupees(sums[name]):>16}"
                      f"   (over {counts[name]} ACTIVE rows)")
            if inactive.get("rows"):
                bits = "  ".join(f"{k}={rupees(v)}" for k, v in sorted(inactive.items())
                                 if k != "rows")
                print(f"    EXCLUDED {int(inactive['rows'])} Inactive row(s): {bits}")

            if quarters:
                print("    Quarter-wise:")
                for q in sorted(quarters):
                    parts = "  ".join(f"{k}={rupees(v)}"
                                      for k, v in sorted(quarters[q].items()))
                    print(f"      {q:<28} {parts}")

            if show_rows:
                print("    Rows:")
                for rec in rows_out:
                    bits = [f"{k}={v}" for k, v in rec.items() if v not in ("", None)]
                    print("      " + " | ".join(bits))

    print("\n" + "=" * 74)
    print("WITHHELD COLUMNS - cardinality only, no values shown")
    print("=" * 74)
    for name, vals in probe_values.items():
        print(f"  {name}: {len(vals)} distinct value(s) across the file")
    for kind, book in _pseudonyms.items():
        print(f"  {kind}: {len(book)} distinct identit(ies) pseudonymised")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
