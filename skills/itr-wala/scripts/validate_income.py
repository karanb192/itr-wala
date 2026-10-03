#!/usr/bin/env python3
"""Strict validator for the income JSON consumed by tax_engine.py.

The LLM extracts numbers from documents (Form 16, AIS, broker statements)
into income.json. This validator is the deterministic gate between that
extraction and the tax computation:

  * rejects unknown/misspelled keys (a typo like "80ccd2" would otherwise be
    silently ignored by the engine and cost the user a deduction)
  * type/sign checks on every amount
  * cross-checks: Form 16 component sums, TDS claimed vs AIS/26AS totals
  * completeness nudges (salary but no savings interest, etc.)

Exit 0 = valid (warnings allowed). Exit 1 = errors; fix income.json and rerun.

Usage: python3 validate_income.py income.json [--json]
"""

import json
import math
import re
import sys
from datetime import date

from tax_years import context_errors, fy_dates, year_rules

if sys.version_info < (3, 9):
    sys.exit("itr-wala needs Python 3.9 or newer (found %d.%d)." % sys.version_info[:2])

PAN_RE = re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b")
AADHAAR_RE = re.compile(r"\b\d{12}\b")

# Canonical input schema: nested dict of key -> type ("num", "str", "list", dict)
SCHEMA = {
    "financial_year": "str",    # "2025-26" | "2026-27"
    "purpose": "str",           # "return" | "advance_tax"
    "as_of_date": "str",        # advance-tax planning only
    "expected_tax_credits": {"tds": "num", "tcs": "num"},
    "regime": "str",            # "new" | "old" | "both" (default both)
    "age_category": "str",      # "regular" | "senior" | "super_senior"
    "relief_89": "num",         # s.89(1) relief per Form 10E computation
    "residential_status": "str",  # informational; engine supports resident only
    "name": "str",                # optional; PAN/Aadhaar are deliberately NOT accepted
    "due_date": "str", "filing_date": "str",
    "income": {
        "salary": {
            "gross": "num",              # 17(1)+17(2)+17(3) total from Form 16 Part B
            "exempt_allowances": "num",  # HRA/LTA etc. exempt u/s 10 (old regime only)
            "exempt_retirement": "num",  # gratuity/leave encashment/commuted pension
                                         # u/s 10(10)/(10A)/(10AA)/(10B)/(10C) - both regimes
            "professional_tax": "num",
            "basic_plus_da": "num",      # optional, enables 80CCD(2) cap check
            "form16_17_1": "num", "form16_17_2": "num", "form16_17_3": "num",
        },
        "house_property": "list",        # [{type, rent_received, municipal_taxes, interest_paid}]
        "capital_gains": {
            "stcg_111a": "num", "ltcg_112a": "num", "ltcg_other": "num",
            "stcg_slab": "num", "vda": "num",
        },
        "other_sources": {
            "savings_interest": "num", "fd_interest": "num", "dividends": "num",
            "family_pension": "num", "winnings": "num", "other": "num",
        },
        "business_presumptive_income": "num",
        "presumptive_section": "str",
    },
    "deductions": {
        "80c": "num", "80ccd_1b": "num", "80ccd_2": "num", "80d": "num",
        "80tta_ttb": "num", "80g": "num", "other": "num",
    },
    "taxes_paid": {
        "tds": "num", "tcs": "num",
        "advance_tax": "list",           # [{date: "YYYY-MM-DD", amount}]
        "self_assessment": "list",
    },
    "source_totals": {                   # verbatim totals read from documents
        "form16_gross_salary": "num",
        "form16_total_tds": "num",
        "ais_total_tds": "num",
        "form26as_total_tds": "num",
        "ais_savings_interest": "num",
        "ais_dividends": "num",
    },
}

HP_KEYS = {"type", "rent_received", "municipal_taxes", "interest_paid"}
PAYMENT_KEYS = {"date", "amount"}


def _is_num(v):
    # bools are ints in Python; Infinity/NaN are valid JSON in Python's parser -
    # both must be refused before they reach the engine.
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _valid_iso_date(s):
    # Strict YYYY-MM-DD only: Python 3.11+ fromisoformat also accepts other
    # ISO-8601 forms, which would make the gate interpreter-dependent.
    if not isinstance(s, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        return False
    try:
        date.fromisoformat(s)
        return True
    except ValueError:
        return False


def _dct(x):
    return x if isinstance(x, dict) else {}


def _lst(x):
    return x if isinstance(x, list) else []


def check(inp, raw="", today=None):
    errors, warnings = [], []

    # Everything below assumes a dict root; bail out cleanly otherwise.
    if not isinstance(inp, dict):
        return ["root: expected an object - see references/input-schema.md"], []

    # Identity data is refused, not just discouraged: computation never needs it.
    if "pan" in inp:
        errors.append("Remove the 'pan' field - PAN is not needed for computation "
                      "and must stay out of this file.")
    if raw and PAN_RE.search(raw):
        errors.append("A PAN-shaped string (AAAAA9999A) appears in this file - redact it. "
                      "Tax computation does not need anyone's PAN.")
    if raw and AADHAAR_RE.search(raw):
        errors.append("A 12-digit number appears in this file - if that is an Aadhaar, "
                      "redact it; if it is an amount above 99,99,99,99,999 it is "
                      "almost certainly a transcription error.")

    def walk(node, schema, path):
        if not isinstance(node, dict):
            errors.append(f"{path or 'root'}: expected an object")
            return
        for key, val in node.items():
            if key not in schema:
                candidates = ", ".join(sorted(schema.keys()))
                errors.append(f"Unknown key '{path}{key}' - the engine would silently "
                              f"ignore it. Valid keys here: {candidates}")
                continue
            spec = schema[key]
            if isinstance(spec, dict):
                walk(val, spec, f"{path}{key}.")
            elif spec == "num":
                if not _is_num(val):
                    errors.append(f"{path}{key}: must be a finite number, got {val!r}")
                elif val < 0:
                    errors.append(f"{path}{key}: negative amount ({val}) - enter losses "
                                  "via house_property, not negative income")
                elif val > 100_00_00_000:
                    warnings.append(f"{path}{key}: {val:,.0f} exceeds 100 crore - confirm "
                                    "this is not a paise/decimal slip")
            elif spec == "str":
                if not isinstance(val, str):
                    errors.append(f"{path}{key}: must be a string")
            elif spec == "list":
                if not isinstance(val, list):
                    errors.append(f"{path}{key}: must be a list")

    walk(inp, SCHEMA, "")
    errors.extend(context_errors(inp, today))
    try:
        rules = year_rules(inp)
    except ValueError:
        rules = None
    if "financial_year" not in inp:
        warnings.append("financial_year omitted: using FY 2025-26 for backward "
                        "compatibility. Confirm the income year.")
    start, end = fy_dates(rules) if rules else (None, None)
    planning = inp.get("purpose") == "advance_tax"
    as_of = (date.fromisoformat(inp["as_of_date"])
             if _valid_iso_date(inp.get("as_of_date")) else None)

    # -- list element checks --
    for i, p in enumerate(_lst(_dct(inp.get("income")).get("house_property"))):
        if not isinstance(p, dict):
            errors.append(f"income.house_property[{i}]: must be an object "
                          '{"type", "rent_received", "municipal_taxes", "interest_paid"}')
            continue
        extra = set(p) - HP_KEYS
        if extra:
            errors.append(f"income.house_property[{i}]: unknown keys {sorted(extra)}")
        if p.get("type") not in ("self_occupied", "let_out"):
            errors.append(f"income.house_property[{i}].type must be "
                          "'self_occupied' or 'let_out'")
        for amt_key in ("rent_received", "municipal_taxes", "interest_paid"):
            if amt_key in p and (not _is_num(p[amt_key]) or p[amt_key] < 0):
                errors.append(f"income.house_property[{i}].{amt_key}: must be a "
                              f"non-negative finite number, got {p[amt_key]!r}")
    sop_count = sum(1 for p in _lst(_dct(inp.get("income")).get("house_property"))
                    if isinstance(p, dict) and p.get("type") == "self_occupied")
    if sop_count > 2:
        section = "21(7)" if rules and rules["tax_year"] else "23(4)"
        errors.append(f"income.house_property: {sop_count} self-occupied properties - "
                      f"s.{section} allows at most TWO; every additional house is deemed "
                      "let-out and taxed on expected rent. Mark the extras 'let_out' "
                      "with the expected rent (from the documents) as rent_received.")
    for field in ("advance_tax", "self_assessment"):
        for i, p in enumerate(_lst(_dct(inp.get("taxes_paid")).get(field))):
            if not isinstance(p, dict):
                errors.append(f"taxes_paid.{field}[{i}]: must be an object "
                              '{"date": "YYYY-MM-DD", "amount": N}')
                continue
            if set(p) - PAYMENT_KEYS:
                errors.append(f"taxes_paid.{field}[{i}]: unknown keys "
                              f"{sorted(set(p) - PAYMENT_KEYS)}")
            if not _is_num(p.get("amount")) or p.get("amount", 0) < 0:
                errors.append(f"taxes_paid.{field}[{i}].amount: must be a "
                              "non-negative number")
            if "date" not in p:
                errors.append(f"taxes_paid.{field}[{i}].date is required - " +
                              ("use the challan date, within this FY and on or before as_of_date"
                               if planning else "use the challan date so interest reflects when tax was paid"))
            elif not _valid_iso_date(p["date"]):
                errors.append(f"taxes_paid.{field}[{i}].date: must be YYYY-MM-DD "
                              f"(got {p['date']!r})")
            elif field == "advance_tax" and rules and not (
                    start <= date.fromisoformat(p["date"]) <= end):
                errors.append(f"taxes_paid.advance_tax[{i}].date {p['date']}: outside "
                              f"FY {rules['fy']} - advance tax must be paid within the FY "
                              f"(s.{rules['sections']['advance_tax']}); if this was paid "
                              f"after {end.isoformat()}, move it to self_assessment")
            elif planning and as_of and date.fromisoformat(p["date"]) > as_of:
                errors.append(f"taxes_paid.{field}[{i}].date: a future payment cannot "
                              "be counted as already paid on as_of_date")
            elif field == "self_assessment" and end and date.fromisoformat(p["date"]) <= end:
                warnings.append(f"taxes_paid.self_assessment[{i}].date {p['date']}: "
                                "before the FY ended - self-assessment tax is normally "
                                f"paid after {end.isoformat()}; double-check the challan")
    if planning and _lst(_dct(inp.get("taxes_paid")).get("self_assessment")):
        errors.append("taxes_paid.self_assessment: omit self-assessment payments "
                      "from advance-tax planning")

    # -- enum checks --
    if inp.get("regime") not in (None, "new", "old", "both"):
        errors.append("regime must be 'new', 'old' or 'both'")
    if inp.get("age_category") not in (None, "regular", "senior", "super_senior"):
        errors.append("age_category must be 'regular', 'senior' or 'super_senior'")
    rs = inp.get("residential_status")
    if isinstance(rs, str) and rs and rs.lower() not in (
            "resident", "ror", "resident and ordinarily resident"):
        errors.append(f"residential_status '{rs}': this engine only supports resident "
                      "individuals - NRI/RNOR filing is out of scope, stop and tell the user")

    # Cross-checks must survive wrong-shaped containers (walk() already
    # reported the type error; don't crash before returning it).
    inc = _dct(inp.get("income"))
    sal = _dct(inc.get("salary"))
    st = _dct(inp.get("source_totals"))
    tp = _dct(inp.get("taxes_paid"))
    business = inc.get("business_presumptive_income", 0)
    if _is_num(business) and business > 0 and not inc.get("presumptive_section"):
        warnings.append("Confirm presumptive eligibility and set income.presumptive_section "
                        "to 44AD or 44ADA; until then the engine uses quarterly instalments. "
                        "44AE is unsupported.")
    ptax = sal.get("professional_tax", 0)
    if _is_num(ptax) and ptax > 2_500:
        warnings.append("Professional tax exceeds 2,500: confirm actual payments, including "
                        "any arrears or multiple-State payments. This is a check, not a deduction cap.")
    if planning:
        expected = _dct(inp.get("expected_tax_credits"))
        if "expected_tax_credits" not in inp:
            warnings.append("expected_tax_credits absent: the plan uses recorded "
                            "TDS/TCS only. Confirm expected withholding for the full year.")
        for key in ("tds", "tcs"):
            recorded = tp.get(key, 0)
            annual = expected.get(key, 0)
            if "expected_tax_credits" in inp and _is_num(recorded) and _is_num(annual) and annual < recorded:
                errors.append(f"expected_tax_credits.{key}: full-year expected credit "
                              "cannot be less than taxes_paid." + key)

    # -- cross-checks against document totals --
    parts = [sal.get(k) for k in ("form16_17_1", "form16_17_2", "form16_17_3")]
    if planning and (any(_is_num(x) for x in parts) or "form16_gross_salary" in st):
        warnings.append("Advance-tax salary.gross is a full-year forecast. Form 16/source salary "
                        "totals may cover a different period; reconcile periods separately and "
                        "do not reduce the annual forecast to match year-to-date or prior-year totals.")
    if not planning and any(_is_num(x) for x in parts) and _is_num(sal.get("gross")):
        total = sum(x for x in parts if _is_num(x))
        if abs(total - sal["gross"]) > 1:
            errors.append(f"Form 16 components 17(1)+17(2)+17(3) = {total:,.0f} but "
                          f"salary.gross = {sal['gross']:,.0f}. Re-read Form 16 Part B.")
    if not planning and _is_num(st.get("form16_gross_salary")) and _is_num(sal.get("gross")):
        if abs(st["form16_gross_salary"] - sal["gross"]) > 1:
            errors.append(f"salary.gross ({sal['gross']:,.0f}) != Form 16 gross salary "
                          f"({st['form16_gross_salary']:,.0f})")
    claimed_tds = tp.get("tds")
    for src in ("form26as_total_tds", "ais_total_tds", "form16_total_tds"):
        if _is_num(st.get(src)) and _is_num(claimed_tds):
            if claimed_tds - st[src] > 1 and src == "form26as_total_tds":
                errors.append(f"TDS claimed ({claimed_tds:,.0f}) exceeds 26AS total "
                              f"({st[src]:,.0f}) - the department will flag this")
            elif abs(claimed_tds - st[src]) > 10:
                warnings.append(f"TDS claimed ({claimed_tds:,.0f}) differs from {src} "
                                f"({st[src]:,.0f}) by {abs(claimed_tds - st[src]):,.0f} - "
                                "reconcile before filing (multiple deductors?)")
    for ais_key, inc_key in (("ais_savings_interest", "savings_interest"),
                             ("ais_dividends", "dividends")):
        ais_v = st.get(ais_key)
        rep_raw = _dct(inc.get("other_sources")).get(inc_key, 0)
        rep_v = rep_raw if _is_num(rep_raw) else 0
        if _is_num(ais_v) and ais_v - (rep_v or 0) > 100:
            errors.append(f"AIS shows {ais_key.replace('ais_', '')} of {ais_v:,.0f} but "
                          f"income reports only {rep_v or 0:,.0f} - omitting AIS-visible "
                          "income invites a notice")

    # -- completeness nudges --
    if _is_num(sal.get("gross")) and sal["gross"] > 0:
        os_ = _dct(inc.get("other_sources"))
        if not os_.get("savings_interest") and not os_.get("fd_interest"):
            warnings.append("No bank interest reported. Almost every account earns some - "
                            "check AIS / bank statements before accepting zero.")
        if not _is_num(claimed_tds) and sal["gross"] > 400_000:
            warnings.append("Salary above basic exemption but no TDS entered - "
                            "check Form 16 Part A / 26AS.")
        elif _is_num(claimed_tds) and claimed_tds == 0 and sal["gross"] > 1_275_000:
            warnings.append("TDS of exactly 0 on a salary above 12,75,000 is unusual - "
                            "confirm against Form 16 Part A.")
    if not st:
        warnings.append("source_totals absent: extracted numbers were not cross-checked "
                        "against any document totals. Fill source_totals from Form 16 / "
                        "AIS / 26AS for a stronger guarantee.")

    return errors, warnings


def main(argv):
    if len(argv) < 2 or argv[1] in ("-h", "--help"):
        print(__doc__)
        return 0
    try:
        raw = sys.stdin.read() if argv[1] == "-" else open(argv[1]).read()
    except OSError as e:
        print(f"ERROR: cannot read input file: {e}")
        return 2
    try:
        inp = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"INVALID JSON: {e}")
        return 1
    errors, warnings = check(inp, raw)
    if "--json" in argv:
        print(json.dumps({"valid": not errors, "errors": errors, "warnings": warnings}, indent=2))
    else:
        for e in errors:
            print(f"ERROR   {e}")
        for w in warnings:
            print(f"WARNING {w}")
        print(f"\n{'FAILED' if errors else 'OK'} - {len(errors)} error(s), "
              f"{len(warnings)} warning(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
