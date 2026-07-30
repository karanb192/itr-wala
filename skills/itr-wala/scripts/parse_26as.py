#!/usr/bin/env python3
"""Total a TRACES Form 26AS text export without disclosing identities.

26AS is '^'-delimited with a header row per part. Columns are whitelisted by
name; every name/TAN/PAN column is pseudonymised. Totals are computed in code.

Usage:  python3 parse_26as.py <26AS.txt> [--rows]
"""

import re
import sys
from collections import defaultdict

if sys.version_info < (3, 9):
    sys.exit("itr-wala needs Python 3.9 or newer (found %d.%d)."
             % sys.version_info[:2])

DELIM = "^"

# Columns safe to show: amounts, dates, codes, status.
SHOW = {
    "sr. no.", "section", "transaction date", "status of booking",
    "date of booking", "remarks", "amount paid / credited(rs.)",
    "tax deducted(rs.)", "tds deposited(rs.)",
    "total amount paid / credited(rs.)", "total tax deducted(rs.)",
    "total tds deposited(rs.)", "amount paid / debited(rs.)",
    "tax collected(rs.)", "tcs deposited(rs.)",
    "total amount paid / debited(rs.)", "total tax collected(rs.)",
    "total tcs deposited(rs.)", "assessment year", "mode", "refund issued",
    "nature of refund", "amount of refund(rs.)", "interest(rs.)",
    "date of payment", "financial year", "total transaction amount(rs.)",
    "acknowledgement number",
}

# Columns holding an identity -> pseudonym prefix.
IDENT = {
    "name of deductor": "DEDUCTOR", "tan of deductor": "TAN",
    "name of collector": "COLLECTOR", "tan of collector": "TAN",
    "name of buyer": "PARTY", "name of seller": "PARTY",
    "name of deductee": "PARTY", "pan of deductor": "PAN",
    "pan of buyer": "PAN", "pan of seller": "PAN", "pan of deductee": "PAN",
}

MONEY = {c for c in SHOW if c.endswith("(rs.)")}

_book = defaultdict(dict)


def tag(kind, value):
    b = _book[kind]
    if value not in b:
        b[value] = f"[{kind}-{len(b) + 1:02d}]"
    return b[value]


def num(v):
    s = str(v).replace(",", "").strip()
    if not s or s in ("-", "NA"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def is_header(fields):
    low = [f.strip().lower() for f in fields]
    return "sr. no." in low and any(f in SHOW or f in IDENT for f in low if f)


SHAPE = re.compile(r"\b([A-Z]{4}\d{5}[A-Z]|[A-Z]{5}\d{4}[A-Z])\b")


def safe(text):
    """Last line of defence: mask any TAN/PAN-shaped token before printing."""
    return SHAPE.sub(lambda m: tag("TAN" if len(m.group(0)) == 10 and
                                   m.group(0)[4].isdigit() else "PAN",
                                   m.group(0)), str(text))


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2

    show_rows = "--rows" in argv
    lines = open(argv[1], encoding="utf-8", errors="replace").read().splitlines()

    part = "(header)"
    headers = {}
    totals = defaultdict(lambda: defaultdict(float))
    counts = defaultdict(int)
    by_section = defaultdict(lambda: defaultdict(float))
    parties = defaultdict(set)

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        m = re.search(r"(PART-[IVX]+)\s*-?\s*:?\s*(.*)", stripped)
        if m and DELIM in line and len(line.split(DELIM)) < 4:
            part = f"{m.group(1)} {m.group(2)[:60]}".strip()
            headers = {}
            continue

        fields = line.split(DELIM)
        if is_header(fields):
            low = [f.strip().lower() for f in fields]
            # Two row shapes per part: a per-deductor SUMMARY and a
            # per-transaction DETAIL. Both headers happen to have the same
            # field count, so classify by content, not width.
            kind = "detail" if "section" in low else "summary"
            headers[kind] = low
            continue

        # Summary rows begin with the serial number; detail rows begin with
        # an empty field. That is what distinguishes them.
        kind = "summary" if fields[0].strip().isdigit() else "detail"
        header = headers.get(kind)
        if not header or len(fields) < 3:
            continue
        serial = fields[0].strip() if kind == "summary" else fields[1].strip()
        if not serial.isdigit():
            continue

        rec = {}
        for name, val in zip(header, fields):
            if not name:
                continue
            if name in IDENT:
                if val.strip():
                    rec[name] = tag(IDENT[name], val.strip())
                    parties[part].add(val.strip())
                continue
            if name not in SHOW:
                continue                      # fail closed
            rec[name] = val.strip()
            n = num(val)
            if n is not None and name in MONEY:
                totals[part][name] += n

        if rec:
            counts[part] += 1
            sec = rec.get("section")
            if sec and re.fullmatch(r"\d{3}[A-Z]{0,3}", sec):
                for k in ("tax deducted(rs.)", "amount paid / credited(rs.)",
                          "tds deposited(rs.)"):
                    n = num(rec.get(k))
                    if n is not None:
                        by_section[sec][k] += n
            if show_rows:
                print("   ", safe(" | ".join(f"{k}={v}" for k, v in rec.items() if v)))

    print("# FORM 26AS - totals computed in code, identities pseudonymised\n")
    for part_name in totals:
        print("=" * 70)
        print(f"{part_name}   [{counts[part_name]} row(s), "
              f"{len(parties[part_name])} distinct part(y/ies)]")
        for col in sorted(totals[part_name]):
            print(f"    {col:<40} {totals[part_name][col]:>15,.2f}")

    if by_section:
        print("\n" + "=" * 70)
        print("BY SECTION")
        for sec in sorted(by_section):
            bits = "  ".join(f"{k.replace('(rs.)','')}={v:,.2f}"
                             for k, v in sorted(by_section[sec].items()))
            print(f"    {safe(sec):<10} {safe(bits)}")

    print("\n" + "=" * 70)
    for kind, b in _book.items():
        print(f"  {kind}: {len(b)} distinct value(s) pseudonymised")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
