"""Supported income years and their statutory dates, independent of the clock."""

import re
from datetime import date


YEARS = {
    "2025-26": {
        "fy": "2025-26", "ay": "2026-27", "tax_year": None,
        "act": "Income-tax Act, 1961", "start_year": 2025,
        "sections": {"rebate": "87A", "regime": "115BAC", "return": "139",
                     "advance_tax": "211", "late_interest": "234A",
                     "advance_interest": "234B", "deferment_interest": "234C",
                     "late_fee": "234F", "round_income": "288A", "round_tax": "288B"},
    },
    "2026-27": {
        "fy": "2026-27", "ay": None, "tax_year": "2026-27",
        "act": "Income-tax Act, 2025", "start_year": 2026,
        "sections": {"rebate": "156", "regime": "202", "return": "263",
                     "advance_tax": "408", "late_interest": "423",
                     "advance_interest": "424", "deferment_interest": "425",
                     "late_fee": "428(a)", "round_income": "516", "round_tax": "516"},
    },
}


def year_rules(inp):
    fy = inp.get("financial_year", "2025-26")
    if not isinstance(fy, str) or fy not in YEARS:
        raise ValueError("financial_year must be '2025-26' or '2026-27'; "
                         "other years are not supported")
    return YEARS[fy]


def fy_dates(rules):
    y = rules["start_year"]
    return date(y, 4, 1), date(y + 1, 3, 31)


def return_due_date(rules, business=False):
    return date(rules["start_year"] + 1, 8 if business else 7, 31)


def advance_schedule(rules, presumptive=False):
    y = rules["start_year"]
    if presumptive:
        return [(date(y + 1, 3, 15), 1.00, 1, None)]
    return [(date(y, 6, 15), 0.15, 3, 0.12),
            (date(y, 9, 15), 0.45, 3, 0.36),
            (date(y, 12, 15), 0.75, 3, None),
            (date(y + 1, 3, 15), 1.00, 1, None)]


def context_errors(inp):
    errors = []
    try:
        rules = year_rules(inp)
    except ValueError as e:
        return [str(e)]
    purpose = inp.get("purpose", "return")
    if purpose not in ("return", "advance_tax"):
        return ["purpose must be 'return' or 'advance_tax'"]
    if purpose == "advance_tax":
        if "financial_year" not in inp:
            errors.append("financial_year is required for advance-tax planning")
        raw = inp.get("as_of_date")
        if not isinstance(raw, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
            errors.append("as_of_date is required as YYYY-MM-DD for advance-tax planning")
        else:
            try:
                as_of = date.fromisoformat(raw)
                start, end = fy_dates(rules)
                if not start <= as_of <= end:
                    errors.append("as_of_date must be within the selected financial_year")
            except ValueError:
                errors.append("as_of_date must be a real YYYY-MM-DD date")
        for field in ("due_date", "filing_date"):
            if field in inp:
                errors.append(field + " is a return field; omit it for advance-tax planning")
    else:
        for field in ("as_of_date", "expected_tax_credits"):
            if field in inp:
                errors.append(field + " is only allowed with purpose 'advance_tax'")
        for field in ("due_date", "filing_date"):
            raw = inp.get(field)
            if raw is None:
                continue
            if not isinstance(raw, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
                errors.append(field + ": must be YYYY-MM-DD")
                continue
            try:
                d = date.fromisoformat(raw)
                if d <= fy_dates(rules)[1]:
                    errors.append(field + ": must be after the selected income year; "
                                  "use purpose 'advance_tax' for current-year estimates")
                elif field == "due_date" and d > date(rules["start_year"] + 2, 3, 31):
                    errors.append("due_date: does not belong to the selected income year")
            except ValueError:
                errors.append(field + ": must be a real YYYY-MM-DD date")
    return errors
