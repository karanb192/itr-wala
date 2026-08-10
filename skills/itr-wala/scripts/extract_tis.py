#!/usr/bin/env python3
"""Extract the category totals from a decrypted TIS PDF, with identifiers masked.

TIS is a summary: one derived figure per income category, with no payer names.
The only identifying content is the header block, which this drops.

Masks before printing: PAN, Aadhaar-shaped and phone-shaped digit runs, long
digit runs (account numbers), and email addresses. Header lines preceding the
first category/value heading are skipped entirely.

Usage:  python3 tis_extract.py <TIS-decrypted.pdf> [--all]
        --all  print every line (still masked) rather than skipping the header
"""

import re
import subprocess
import sys

if sys.version_info < (3, 9):
    sys.exit("itr-wala needs Python 3.9 or newer (found %d.%d)."
             % sys.version_info[:2])

MASKS = [
    (re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b"), "[PAN]"),
    (re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b"), "[EMAIL]"),
    (re.compile(r"\b\d{12}\b"), "[AADHAAR?]"),
    (re.compile(r"\b\d{9,18}\b"), "[LONG-DIGITS]"),
    (re.compile(r"\b[6-9]\d{9}\b"), "[PHONE]"),
]

# Where the real content starts.
START = re.compile(
    r"information\s+category|derived\s+value|processed\s+value|part[- ]?b",
    re.I,
)

# Category whitelist. These are the standard TIS income-category names -
# public knowledge, not derived from any user document. Only lines matching
# one of these (or a table heading) are shown; everything else is counted and
# withheld. This is the semantic equivalent of the AIS column whitelist.
CATEGORIES = [
    "salary", "rent received", "dividend", "interest from savings",
    "interest from deposit", "interest from term deposit", "interest from others",
    "interest from income tax refund", "sale of securities", "purchase of securities",
    "sale of immovable property", "purchase of immovable property",
    "off market", "business receipts", "business expenses", "gst turnover",
    "cash deposit", "cash withdrawal", "cash payment", "credit card", "debit card",
    "outward foreign remittance", "receipt of foreign remittance",
    "purchase of foreign currency", "purchase of vehicle", "purchase of time deposit",
    "income distributed by", "winnings from", "miscellaneous", "donation",
    "rent payment", "tds", "tcs", "advance tax", "self assessment tax",
    "refund", "demand", "total",
]
HEADING = re.compile(
    r"information\s+category|derived\s+value|processed\s+value|reported\s+value"
    r"|part[- ]?[ab]|information\s+source|^\s*sl\.?\s*no",
    re.I,
)


def is_wanted(line):
    low = line.lower()
    return bool(HEADING.search(line)) or any(c in low for c in CATEGORIES)


# TIS detail rows carry an INFORMATION SOURCE column holding payer names in
# caps. Column headings are also in caps, so they are excluded by name.
HEADER_WORDS = {
    "SR", "NO", "PART", "INFORMATION", "CATEGORY", "SOURCE", "AMOUNT",
    "REPORTED", "PROCESSED", "ACCEPTED", "DERIVED", "VALUE", "BY", "TOTAL",
    "DIVIDEND", "INTEREST", "SAVINGS", "BANK", "TDS", "TCS", "SFT", "AND",
    "OF", "THE", "FROM", "PAID", "CREDITED", "SECTION", "OUTWARD", "FOREIGN",
    "REMITTANCE", "PURCHASE", "CURRENCY", "INCOME", "RECEIVED", "TAX",
    # Document/category tokens that appear alone on whitelisted lines and
    # must survive the single-token payer pass below.
    "AY", "FY", "ITR", "AIS", "TIS", "PAN", "NRO", "NRE", "FD", "RD",
}
# A payer name is a run of two or more capitalised words. Matching only
# ALL-CAPS runs missed mixed-case names such as "SomeCement India Limited".
CAPS_RUN = re.compile(r"\b(?:[A-Z][A-Za-z&.\-]+(?:\s+|$)){2,}")
_payers = {}


def _is_header_word(w):
    return re.sub(r"[^A-Z]", "", w.upper()) in HEADER_WORDS


def _pseudo(match):
    raw = match.group(0)
    words = [w for w in re.split(r"\s+", raw.strip()) if w]
    # Compare case-insensitively: "Total Dividend" is a column value, not a
    # payer, and must survive the same test that protects ALL-CAPS headings.
    if all(_is_header_word(w) for w in words):
        return raw                      # a heading or column label, not a payer
    # Keep a leading run of known label words ("Dividend RELIANCE INDUSTRIES
    # LTD" keeps "Dividend"), so masking a payer never swallows the category
    # label the figure needs to stay classifiable.
    keep = 0
    while keep < len(words) - 1 and _is_header_word(words[keep]):
        keep += 1
    prefix = " ".join(words[:keep])
    payer = words[keep:]
    key = " ".join(payer)
    if key not in _payers:
        _payers[key] = f"[PAYER-{len(_payers) + 1:02d}]"
    trailing = "" if raw == raw.rstrip() else " "
    joined = (prefix + " " if prefix else "") + _payers[key]
    return joined + trailing


# A single-token payer ("HDFC", "SBI") preceded by lowercase text escapes
# CAPS_RUN's two-word minimum and would leak verbatim - catch stand-alone
# caps tokens separately. Anything all-caps, 2+ letters, not a known label.
# The lookbehind skips tokens inside already-emitted masks like [PAYER-01].
SINGLE_CAPS = re.compile(r"(?<!\[)\b[A-Z][A-Z&.\-]{1,}\b")


def _pseudo_single(match):
    w = match.group(0)
    if _is_header_word(w):
        return w
    if w not in _payers:
        _payers[w] = f"[PAYER-{len(_payers) + 1:02d}]"
    return _payers[w]


def mask(line):
    for pattern, repl in MASKS:
        line = pattern.sub(repl, line)
    line = re.sub(r"\b[A-Z]{4}\d{5}[A-Z]\b", "[TAN]", line)   # deductor TAN
    line = CAPS_RUN.sub(_pseudo, line)
    return SINGLE_CAPS.sub(_pseudo_single, line)


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2

    pdf = argv[1]
    show_all = "--all" in argv

    try:
        out = subprocess.run(["pdftotext", "-layout", pdf, "-"],
                             capture_output=True, text=True, check=True).stdout
    except subprocess.CalledProcessError as exc:
        err = (exc.stderr or "").strip()
        if "password" in err.lower() or "encrypt" in err.lower():
            print("PDF is still encrypted - decrypt it first:\n"
                  "  qpdf --password='<PAN><DDMMYYYY>' --decrypt in.pdf out.pdf",
                  file=sys.stderr)
        else:
            print(f"pdftotext failed: {err}", file=sys.stderr)
        return 1
    except FileNotFoundError:
        print("pdftotext not found (brew install poppler).", file=sys.stderr)
        return 1

    lines = out.splitlines()
    text_chars = sum(len(l.strip()) for l in lines)
    if text_chars < 200:
        print(f"WARNING: only {text_chars} characters of text extracted.\n"
              "This PDF is probably image-only (scanned). Its numbers cannot be\n"
              "read reliably without OCR - do not transcribe from it.",
              file=sys.stderr)
        return 1

    started = show_all
    shown = withheld = 0
    for line in lines:
        if not started:
            if START.search(line):
                started = True
            else:
                continue
        if not line.strip():
            continue
        if show_all or is_wanted(line):
            print(mask(line))
            shown += 1
        else:
            withheld += 1

    if not shown:
        print("No category section found. Re-run with --all to see the whole "
              "document (still masked).", file=sys.stderr)
        return 1

    print(f"\n# {shown} line(s) shown - matched the standard TIS category "
          f"whitelist, identifiers masked, header skipped.")
    if withheld:
        print(f"# {withheld} line(s) WITHHELD (no whitelist match). Content not "
              f"read. Re-run with --all if a figure appears to be missing.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
