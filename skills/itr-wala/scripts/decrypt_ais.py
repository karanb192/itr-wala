#!/usr/bin/env python3
"""Decrypt an AIS JSON download from the Indian income-tax AIS portal.

Runs fully offline. Nothing is sent anywhere. Your PAN and date of birth are
read without echoing, used only to derive the decryption key, and are never
printed, logged, or written to disk.

Scheme (as implemented by the AIS portal / AIS Utility):

    file   = IV(32 hex) || salt(32 hex) || base64(ciphertext)
    passwd = PAN || "GQ39%*g" || DDMMYYYY
    key    = PBKDF2-HMAC-SHA256(passwd, salt, 1000 iterations, 32 bytes)
    cipher = AES-256-CBC with PKCS7 padding

Usage:  python3 decrypt-ais.py <encrypted.json> [output.json]
"""

import base64
import getpass
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

if sys.version_info < (3, 9):
    sys.exit("itr-wala needs Python 3.9 or newer (found %d.%d)."
             % sys.version_info[:2])

SEP = "GQ39%*g"   # constant the portal wedges between PAN and DOB
ITERATIONS = 1000
KEY_LEN = 32


def decrypt(blob, pan, dob):
    iv_hex, salt_hex, body = blob[:32], blob[32:64], blob[64:]
    salt = bytes.fromhex(salt_hex)

    password = f"{pan}{SEP}{dob}"
    key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITERATIONS, KEY_LEN)

    ciphertext = base64.b64decode(body)

    # OpenSSL handles AES-CBC + PKCS7; key/iv passed as hex, plaintext via stdout.
    # Tradeoff, made knowingly: the DERIVED key rides on argv, visible to a
    # concurrent `ps` on a shared host for the sub-second run (PAN and DOB
    # never do). stdlib has no AES, and a pip dependency is off the table for
    # this project, so the alternative costs more than the exposure.
    proc = subprocess.run(
        ["openssl", "enc", "-d", "-aes-256-cbc",
         "-K", key.hex(), "-iv", iv_hex],
        input=ciphertext, capture_output=True,
    )
    if proc.returncode != 0:
        raise ValueError(proc.stderr.decode().strip() or "bad padding")
    return proc.stdout


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2

    src = Path(argv[1])
    dst = Path(argv[2]) if len(argv) > 2 else src.with_name("AIS-decrypted.json")

    blob = src.read_text().strip()
    if len(blob) < 65 or not re.fullmatch(r"[0-9a-fA-F]{64}", blob[:64]):
        print("This does not look like an encrypted AIS file "
              "(expected 64 hex chars of IV+salt at the start).", file=sys.stderr)
        return 1

    print(f"Input : {src.name}  ({len(blob):,} chars)")
    print("Your PAN and DOB stay on this machine and are never displayed.\n")

    pan = getpass.getpass("PAN (10 chars, hidden): ").strip()
    dob = getpass.getpass("DOB as DDMMYYYY (hidden): ").strip()

    if not re.fullmatch(r"[A-Za-z]{5}[0-9]{4}[A-Za-z]", pan):
        print("\nThat PAN is not in the expected AAAAA9999A shape.", file=sys.stderr)
        return 1
    if not re.fullmatch(r"\d{8}", dob):
        print("\nDOB must be exactly 8 digits, DDMMYYYY (e.g. 09081962).", file=sys.stderr)
        return 1

    # Sources disagree on PAN case; try both rather than make you guess.
    for label, candidate in (("uppercase", pan.upper()), ("lowercase", pan.lower())):
        try:
            plain = decrypt(blob, candidate, dob)
            data = json.loads(plain)
        except Exception:
            continue

        dst.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        print(f"\n[ok] Decrypted with {label} PAN.")
        print(f"[ok] Wrote {dst}  ({dst.stat().st_size:,} bytes)")
        top = list(data)[:8] if isinstance(data, dict) else f"array[{len(data)}]"
        print(f"[ok] Valid JSON. Top-level keys: {top}")
        return 0

    print("\nDecryption failed with both PAN cases.\n"
          "Most likely the DOB is wrong (it must match the PAN record exactly,\n"
          "DDMMYYYY with leading zeros), or the file is truncated.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
