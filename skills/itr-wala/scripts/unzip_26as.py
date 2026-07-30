#!/usr/bin/env python3
"""Extract a TRACES Form 26AS text download (ZipCrypto zip).

macOS Archive Utility mishandles ZipCrypto and reports a wrong password even
when it is correct. This uses Python's zipfile, which handles it properly.

PAN and DOB are read without echoing, used only to build candidate passwords,
and never printed or written anywhere.

Usage:  python3 unzip-26as.py <file.zip> [output-dir]
"""

import getpass
import re
import sys
import zipfile
from pathlib import Path

if sys.version_info < (3, 9):
    sys.exit("itr-wala needs Python 3.9 or newer (found %d.%d)."
             % sys.version_info[:2])


def candidates(pan, dob):
    """TRACES password format varies by download type - try the known shapes."""
    p_up, p_lo = pan.upper(), pan.lower()
    seen = []
    for c in (dob, p_up + dob, p_lo + dob, p_up, p_lo,
              p_up + dob[:4], dob[:4] + p_up):
        if c and c not in seen:
            seen.append(c)
    return seen


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2

    src = Path(argv[1])
    outdir = Path(argv[2]) if len(argv) > 2 else src.parent

    try:
        zf = zipfile.ZipFile(src)
    except (OSError, zipfile.BadZipFile) as exc:
        print(f"Cannot open zip: {exc}", file=sys.stderr)
        return 1

    names = zf.namelist()
    if not names:
        print("Zip is empty.", file=sys.stderr)
        return 1

    info = zf.getinfo(names[0])
    if info.flag_bits & 0x40:
        print("This zip uses AES encryption, which Python's zipfile cannot "
              "read.\nInstall p7zip and use:  7z x -p'<password>' file.zip",
              file=sys.stderr)
        return 1
    if not (info.flag_bits & 0x1):
        zf.extractall(outdir)
        print(f"Not encrypted. Extracted {len(names)} file(s) to {outdir}")
        return 0

    print(f"Archive: {src.name}  ({len(names)} file(s), ZipCrypto)")
    print("PAN and DOB are hidden as you type and are never stored.\n")

    pan = getpass.getpass("PAN (10 chars, hidden): ").strip()
    dob = getpass.getpass("DOB as DDMMYYYY (hidden): ").strip()

    if not re.fullmatch(r"[A-Za-z]{5}[0-9]{4}[A-Za-z]", pan):
        print("\nThat PAN is not in the expected AAAAA9999A shape.",
              file=sys.stderr)
        return 1
    if not re.fullmatch(r"\d{8}", dob):
        print("\nDOB must be exactly 8 digits, DDMMYYYY (e.g. 09081962).",
              file=sys.stderr)
        return 1

    for n, pw in enumerate(candidates(pan, dob), 1):
        try:
            data = zf.read(names[0], pwd=pw.encode())
        except (RuntimeError, zipfile.BadZipFile):
            continue
        except Exception:
            continue

        # A correct 26AS extraction is readable text, not binary noise.
        try:
            text = data.decode("utf-8", errors="strict")
        except UnicodeDecodeError:
            continue
        if "PAN" not in text.upper() and "TDS" not in text.upper():
            continue

        for name in names:
            (outdir / Path(name).name).write_bytes(zf.read(name, pwd=pw.encode()))
        print(f"\n[ok] Opened on password variant #{n}.")
        print(f"[ok] Extracted {len(names)} file(s) to {outdir}")
        print(f"[ok] {len(text):,} characters of readable text.")
        return 0

    print("\nNone of the password variants worked.\n"
          "Most likely the DOB does not match the PAN record exactly "
          "(DDMMYYYY, with leading zeros).\n"
          "If you are certain of both, re-download - TRACES text files are "
          "occasionally served truncated.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
