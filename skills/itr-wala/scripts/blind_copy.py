#!/usr/bin/env python3
"""Copy JSON fields source -> destination without ever printing their values.

Reads a mapping of source/destination key paths, copies each value across, and
verifies the copy by comparing SHA-256 digests. Output is structural only:
key paths, types, lengths, PASS/FAIL. No value is printed on any code path,
including errors - exception text is sanitised before display.

Usage:
    python3 blind_copy.py <source.json> <mapping.json> <dest.json>
    python3 blind_copy.py --verify <source.json> <mapping.json> <dest.json>

mapping.json:
    [{"from": "accounts[0].accountNumber", "to": "schedule[0].accountNumber"}]

Key paths use dots for object keys and [i] for array indices.
"""

import hashlib
import json
import re
import sys

if sys.version_info < (3, 9):
    sys.exit("itr-wala needs Python 3.9 or newer (found %d.%d)."
             % sys.version_info[:2])

TOKEN = re.compile(r"([^.\[\]]+)|\[(\d+)\]")


def parse_path(path):
    """'a.b[0].c' -> ['a', 'b', 0, 'c']"""
    tokens = []
    pos = 0
    for m in TOKEN.finditer(path):
        if m.start() > pos and path[pos:m.start()] not in ".":
            raise ValueError(f"malformed key path: {path!r}")
        pos = m.end()
        key, idx = m.group(1), m.group(2)
        tokens.append(key if key is not None else int(idx))
    if not tokens:
        raise ValueError(f"empty key path: {path!r}")
    return tokens


def get_in(obj, tokens, path):
    cur = obj
    for tok in tokens:
        try:
            cur = cur[tok]
        except (KeyError, IndexError, TypeError):
            raise KeyError(f"source path not found: {path}") from None
    return cur


def set_in(obj, tokens, value, path):
    """Set, creating intermediate dicts/lists as needed."""
    cur = obj
    for i, tok in enumerate(tokens[:-1]):
        nxt = tokens[i + 1]
        default = [] if isinstance(nxt, int) else {}
        if isinstance(tok, int):
            if not isinstance(cur, list):
                raise TypeError(f"destination path expects an array at {path}")
            while len(cur) <= tok:
                cur.append(None)
            if cur[tok] is None:
                cur[tok] = default
            cur = cur[tok]
        else:
            if not isinstance(cur, dict):
                raise TypeError(f"destination path expects an object at {path}")
            if cur.get(tok) is None:
                cur[tok] = default
            cur = cur[tok]

    last = tokens[-1]
    if isinstance(last, int):
        if not isinstance(cur, list):
            raise TypeError(f"destination path expects an array at {path}")
        while len(cur) <= last:
            cur.append(None)
        cur[last] = value
    else:
        cur[last] = value


def digest(value):
    """Stable digest of a JSON value. Reveals nothing about the content."""
    canon = json.dumps(value, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False)
    return hashlib.sha256(canon.encode()).hexdigest()


def describe(value):
    """Type and length only - never the value."""
    if isinstance(value, str):
        return f"string ({len(value)} chars)"
    if isinstance(value, bool):
        return "bool"
    if value is None:
        return "null"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, list):
        return f"array[{len(value)}]"
    if isinstance(value, dict):
        return f"object[{len(value)} keys]"
    return type(value).__name__


def load(path):
    try:
        with open(path) as fh:
            return json.load(fh)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"{path}: not valid JSON (line {exc.lineno}, "
                         f"col {exc.colno}).")
    except OSError as exc:
        raise SystemExit(f"{path}: {exc.strerror}")


def main(argv):
    args = [a for a in argv[1:] if not a.startswith("--")]
    verify_only = "--verify" in argv

    if len(args) != 3:
        print(__doc__)
        return 2

    src_path, map_path, dst_path = args
    source = load(src_path)
    mapping = load(map_path)

    if not isinstance(mapping, list):
        raise SystemExit("mapping.json must be a list of {from, to} objects.")

    if verify_only:
        dest = load(dst_path)
    else:
        try:
            dest = load(dst_path)
        except SystemExit:
            dest = {}   # destination may not exist yet

    mode = "VERIFY" if verify_only else "COPY"
    print(f"# {mode}: {len(mapping)} mapped field(s). Values are never shown.\n")

    width = max((len(str(m.get("from", ""))) for m in mapping), default=10)
    failures = 0

    for entry in mapping:
        frm, to = entry.get("from"), entry.get("to")
        if not frm or not to:
            print(f"{'?':<{width}}  FAIL  mapping entry missing 'from' or 'to'")
            failures += 1
            continue

        try:
            src_tokens = parse_path(frm)
            dst_tokens = parse_path(to)
            value = get_in(source, src_tokens, frm)

            if not verify_only:
                set_in(dest, dst_tokens, value, to)

            written = get_in(dest, dst_tokens, to)
            ok = digest(value) == digest(written)
            empty = value in ("", None, [], {})

            status = "PASS" if ok else "FAIL"
            flag = "  [empty source value]" if empty else ""
            if ok:
                detail = describe(value)
            else:
                # Show both sides so a truncation is diagnosable - still no values.
                failures += 1
                detail = f"source={describe(value)} dest={describe(written)}"
            print(f"{frm:<{width}}  {status}  -> {to}  {detail}{flag}")

        except (KeyError, TypeError, ValueError) as exc:
            # exc text is built from key paths only, never from values
            failures += 1
            print(f"{frm:<{width}}  FAIL  {exc}")

    if not verify_only and failures == 0:
        with open(dst_path, "w") as fh:
            json.dump(dest, fh, indent=2, ensure_ascii=False)
        print(f"\nWrote {dst_path}")

    if failures:
        print(f"\n{failures} of {len(mapping)} field(s) FAILED. "
              f"{'Nothing written.' if not verify_only else ''}", file=sys.stderr)
        return 1

    print(f"\nAll {len(mapping)} field(s) verified by SHA-256 digest match.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
