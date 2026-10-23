#!/usr/bin/env python3
"""Decrypt an AIS/TIS PDF using qpdf and a hidden password prompt.

Usage: python3 decrypt_pdf.py input.pdf output.pdf
The password travels over stdin, never in command-line arguments.
"""

import getpass
import subprocess
import sys

from private_output import write_private


def main(argv):
    if len(argv) != 3:
        print(__doc__)
        return 2
    password = getpass.getpass("PDF password (lowercase PAN + DDMMYYYY, hidden): ")
    try:
        result = subprocess.run(
            ["qpdf", "--password-file=-", "--decrypt", argv[1], "-"],
            input=(password + "\n").encode("utf-8"), capture_output=True)
    except FileNotFoundError:
        print("qpdf not found. Install qpdf and retry.", file=sys.stderr)
        return 1
    if result.returncode not in (0, 3):
        print("PDF decryption failed. Check the password and input file.", file=sys.stderr)
        return 1
    if not result.stdout.startswith(b"%PDF-"):
        print("qpdf did not produce a PDF; no output written.", file=sys.stderr)
        return 1
    write_private(argv[2], result.stdout)
    if result.returncode == 3:
        print("qpdf reported PDF warnings; inspect the decrypted file before extraction.",
              file=sys.stderr)
    print("Decrypted PDF written. Treat it as an unredacted tax document.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
