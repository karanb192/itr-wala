"""Tests for validate_income.py - the deterministic gate between LLM document
extraction and tax_engine.py. Run: python3 test_validate_income.py
(or python3 -m unittest test_validate_income -v)

Several tests are regression locks for validator bugs that have since been
fixed: container-shape crashes, silently-accepted
house-property elements and amounts, undated payments, non-string enum
crashes, the AIS cross-check TypeError, ISO-date laxity on Python 3.11+, and
an unguarded file read in main(). If one of these regresses, its lock names
the original defect in a "Regression lock (fixed)" comment.
"""

import copy
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import date

from validate_income import check as validator_check


def check(inp, raw="", today=date(2026, 7, 20)):
    return validator_check(inp, raw, today=today)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
VALIDATOR = os.path.join(SCRIPT_DIR, "validate_income.py")
ENGINE = os.path.join(SCRIPT_DIR, "tax_engine.py")
EXAMPLE = os.path.join(SCRIPT_DIR, "..", "assets", "example-income.json")

# A fully cross-checked input that yields 0 errors AND 0 warnings.
CLEAN = {
    "financial_year": "2025-26",
    "regime": "both",
    "age_category": "regular",
    "residential_status": "resident",
    "due_date": "2026-07-31",
    "filing_date": "2026-07-28",
    "income": {
        "salary": {"gross": 1_500_000, "form16_17_1": 1_450_000,
                   "form16_17_2": 50_000, "form16_17_3": 0},
        "other_sources": {"savings_interest": 9_000, "dividends": 4_000},
    },
    "taxes_paid": {"tds": 120_000},
    "source_totals": {"form16_gross_salary": 1_500_000,
                      "form16_total_tds": 120_000,
                      "form26as_total_tds": 120_000,
                      "ais_total_tds": 120_000,
                      "ais_savings_interest": 9_000,
                      "ais_dividends": 4_000},
}


def clean():
    return copy.deepcopy(CLEAN)


def vcheck(obj):
    """Round-trip through JSON exactly like production: check(parsed, raw)."""
    raw = json.dumps(obj)
    return check(json.loads(raw), raw)


def vcheck_raw(raw):
    return check(json.loads(raw), raw)


def has(msgs, *needles):
    """True if any single message contains all the needles."""
    return any(all(n in m for n in needles) for m in msgs)


def run_cli(script, *args, stdin=None):
    return subprocess.run([sys.executable, script, *args],
                          capture_output=True, text=True, input=stdin)


class TempFileMixin:
    def setUp(self):
        self._tmpdir = tempfile.mkdtemp(prefix="itr-wala-test-")
        self.addCleanup(shutil.rmtree, self._tmpdir, True)

    def write(self, name, content):
        path = os.path.join(self._tmpdir, name)
        with open(path, "w") as f:
            f.write(content if isinstance(content, str) else json.dumps(content))
        return path


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

class TestHappyPath(unittest.TestCase):
    def test_shipped_example_has_zero_errors(self):
        with open(EXAMPLE) as f:
            raw = f.read()
        errors, warnings = check(json.loads(raw), raw)
        self.assertEqual(errors, [])
        # The example deliberately carries one expected warning: TDS claimed
        # (26AS grand total) differs from Form 16's employer-only total.
        self.assertTrue(has(warnings, "form16_total_tds"), warnings)

    def test_fully_cross_checked_input_is_silent(self):
        errors, warnings = vcheck(clean())
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])

    def test_empty_object_valid_with_source_totals_warning(self):
        errors, warnings = vcheck({})
        self.assertEqual(errors, [])
        self.assertTrue(has(warnings, "source_totals absent"), warnings)


# ---------------------------------------------------------------------------
# Unknown / misspelled keys at every nesting level
# ---------------------------------------------------------------------------

class TestUnknownKeys(unittest.TestCase):
    def test_top_level_typo_lists_valid_keys(self):
        errors, _ = vcheck({"salary_gross": 2_500_000})
        self.assertTrue(has(errors, "Unknown key 'salary_gross'",
                            "Valid keys here"), errors)
        self.assertTrue(has(errors, "Unknown key 'salary_gross'", "income"),
                        errors)

    def test_deductions_typo_80ccd2(self):
        errors, _ = vcheck({"deductions": {"80ccd2": 100_000}})
        self.assertTrue(has(errors, "Unknown key 'deductions.80ccd2'",
                            "80ccd_2"), errors)

    def test_income_level_unknown_key(self):
        errors, _ = vcheck({"income": {"rental": 100_000}})
        self.assertTrue(has(errors, "Unknown key 'income.rental'"), errors)

    def test_salary_level_typo(self):
        errors, _ = vcheck({"income": {"salary": {"grosss": 1_000_000}}})
        self.assertTrue(has(errors, "Unknown key 'income.salary.grosss'"),
                        errors)

    def test_capital_gains_typo(self):
        errors, _ = vcheck({"income": {"capital_gains": {"ltcg112a": 160_000}}})
        self.assertTrue(has(errors, "Unknown key 'income.capital_gains.ltcg112a'",
                            "ltcg_112a"), errors)

    def test_source_totals_unknown_key(self):
        errors, _ = vcheck({"source_totals": {"form16_gross": 1_000_000}})
        self.assertTrue(has(errors, "Unknown key 'source_totals.form16_gross'"),
                        errors)

    def test_house_property_element_unknown_key(self):
        errors, _ = vcheck({"income": {"house_property": [
            {"type": "let_out", "rent": 240_000}]}})
        self.assertTrue(has(errors, "house_property[0]", "unknown keys",
                            "rent"), errors)

    def test_payment_item_unknown_key(self):
        errors, _ = vcheck({"taxes_paid": {"advance_tax": [
            {"date": "2025-12-14", "amount": 20_000, "challan": "x"}]}})
        self.assertTrue(has(errors, "advance_tax[0]", "unknown keys",
                            "challan"), errors)


# ---------------------------------------------------------------------------
# Type errors
# ---------------------------------------------------------------------------

class TestTypeErrors(unittest.TestCase):
    def test_string_number_rejected(self):
        errors, _ = vcheck({"income": {"salary": {"gross": "2500000"}}})
        self.assertTrue(has(errors, "income.salary.gross",
                            "finite number", "'2500000'"), errors)

    def test_bool_rejected_for_num_field(self):
        # bools are ints in Python - must still be refused.
        errors, _ = vcheck_raw('{"deductions": {"80c": true}}')
        self.assertTrue(has(errors, "deductions.80c", "finite number"), errors)

    def test_null_rejected_for_num_field(self):
        errors, _ = vcheck_raw('{"taxes_paid": {"tds": null}}')
        self.assertTrue(has(errors, "taxes_paid.tds", "finite number"), errors)

    def test_non_string_name(self):
        errors, _ = vcheck({"name": 123})
        self.assertTrue(has(errors, "name", "must be a string"), errors)

    def test_house_property_dict_not_list(self):
        errors, _ = vcheck({"income": {"house_property":
                            {"type": "self_occupied", "interest_paid": 5}}})
        self.assertTrue(has(errors, "income.house_property", "must be a list"),
                        errors)

    def test_advance_tax_dict_not_list(self):
        errors, _ = vcheck({"taxes_paid": {"advance_tax":
                            {"date": "2025-12-14", "amount": 20_000}}})
        self.assertTrue(has(errors, "taxes_paid.advance_tax", "must be a list"),
                        errors)

    def test_capital_gains_list_not_object(self):
        errors, _ = vcheck({"income": {"capital_gains": [1, 2]}})
        self.assertTrue(has(errors, "income.capital_gains",
                            "expected an object"), errors)


# ---------------------------------------------------------------------------
# Non-finite numbers (valid JSON for Python's parser, must be refused)
# ---------------------------------------------------------------------------

class TestNonFinite(unittest.TestCase):
    def test_infinity_rejected(self):
        errors, _ = vcheck_raw('{"income": {"salary": {"gross": Infinity}}}')
        self.assertTrue(has(errors, "income.salary.gross", "finite number"),
                        errors)

    def test_negative_infinity_rejected(self):
        errors, _ = vcheck_raw('{"income": {"salary": {"gross": -Infinity}}}')
        self.assertTrue(has(errors, "income.salary.gross", "finite number"),
                        errors)

    def test_nan_rejected(self):
        errors, _ = vcheck_raw('{"deductions": {"80d": NaN}}')
        self.assertTrue(has(errors, "deductions.80d", "finite number"), errors)


# ---------------------------------------------------------------------------
# Amount bounds
# ---------------------------------------------------------------------------

class TestAmountBounds(unittest.TestCase):
    def test_negative_amount_is_error(self):
        errors, _ = vcheck({"deductions": {"80c": -5}})
        self.assertTrue(has(errors, "deductions.80c", "negative amount"),
                        errors)

    def test_negative_salary_gross_is_error(self):
        errors, _ = vcheck({"income": {"salary": {"gross": -1_000_000}}})
        self.assertTrue(has(errors, "income.salary.gross", "negative amount"),
                        errors)

    def test_above_100_crore_is_warning_not_error(self):
        # 2e9 = 200 crore (10 digits - deliberately NOT 12, see Aadhaar tests)
        errors, warnings = vcheck({"income": {"other_sources":
                                              {"other": 2_000_000_000}}})
        self.assertEqual(errors, [])
        self.assertTrue(has(warnings, "exceeds 100 crore"), warnings)

    def test_exactly_100_crore_is_silent(self):
        errors, warnings = vcheck({"income": {"other_sources":
                                              {"other": 1_00_00_00_000}}})
        self.assertEqual(errors, [])
        self.assertFalse(has(warnings, "exceeds 100 crore"), warnings)


# ---------------------------------------------------------------------------
# Identity data (PAN / Aadhaar) is refused wherever it appears
# ---------------------------------------------------------------------------

class TestIdentityScrubbing(unittest.TestCase):
    def test_pan_field_rejected(self):
        errors, _ = vcheck({"pan": "redacted"})
        self.assertTrue(has(errors, "Remove the 'pan' field"), errors)

    def test_pan_shaped_value_rejected(self):
        errors, _ = vcheck({"name": "FAKEP1234Z"})
        self.assertTrue(has(errors, "PAN-shaped"), errors)

    def test_pan_shaped_key_rejected(self):
        errors, _ = vcheck({"FAKEP1234Z": 1})
        self.assertTrue(has(errors, "PAN-shaped"), errors)

    def test_12_digit_number_value_rejected(self):
        errors, _ = vcheck({"income": {"other_sources":
                                       {"other": 123456789012}}})
        self.assertTrue(has(errors, "12-digit number"), errors)

    def test_12_digit_string_rejected(self):
        errors, _ = vcheck({"name": "id 123456789012"})
        self.assertTrue(has(errors, "12-digit number"), errors)

    def test_10_digit_amount_not_mistaken_for_aadhaar(self):
        errors, _ = vcheck({"income": {"other_sources":
                                       {"other": 2_000_000_000}}})
        self.assertFalse(has(errors, "12-digit number"), errors)


# ---------------------------------------------------------------------------
# Dates
# ---------------------------------------------------------------------------

class TestDates(unittest.TestCase):
    def test_dd_mm_yyyy_due_date_rejected(self):
        errors, _ = vcheck({"due_date": "31-07-2026"})
        self.assertTrue(has(errors, "due_date", "must be YYYY-MM-DD"), errors)

    def test_word_filing_date_rejected(self):
        errors, _ = vcheck({"filing_date": "tomorrow"})
        self.assertTrue(has(errors, "filing_date", "must be YYYY-MM-DD"),
                        errors)

    def test_integer_due_date_rejected(self):
        # 20260731 as a bare int is a type error; the compact string form is
        # rejected separately by _valid_iso_date's strict YYYY-MM-DD regex.
        errors, _ = vcheck({"due_date": 20260731})
        self.assertTrue(has(errors, "due_date", "must be a string"), errors)

    def test_compact_string_date_rejected(self):
        errors, _ = vcheck({"due_date": "20260731"})
        self.assertTrue(has(errors, "due_date", "must be YYYY-MM-DD"), errors)

    def test_valid_iso_dates_accepted(self):
        errors, _ = vcheck({"due_date": "2026-07-31",
                            "filing_date": "2026-07-28"})
        self.assertEqual(errors, [])

    def test_payment_bad_date(self):
        errors, _ = vcheck({"taxes_paid": {"advance_tax": [
            {"date": "15-06-2025", "amount": 10_000}]}})
        self.assertTrue(has(errors, "advance_tax[0].date",
                            "must be YYYY-MM-DD"), errors)

    def test_self_assessment_bad_date(self):
        errors, _ = vcheck({"taxes_paid": {"self_assessment": [
            {"date": "sometime", "amount": 10_000}]}})
        self.assertTrue(has(errors, "self_assessment[0].date",
                            "must be YYYY-MM-DD"), errors)

    def test_payment_non_dict_item(self):
        errors, _ = vcheck({"taxes_paid": {"advance_tax": ["20000 on 14 Dec"]}})
        self.assertTrue(has(errors, "advance_tax[0]", "must be an object"),
                        errors)

    def test_payment_missing_amount(self):
        errors, _ = vcheck({"taxes_paid": {"self_assessment": [
            {"date": "2026-07-20"}]}})
        self.assertTrue(has(errors, "self_assessment[0].amount",
                            "non-negative number"), errors)

    def test_payment_negative_amount(self):
        errors, _ = vcheck({"taxes_paid": {"advance_tax": [
            {"date": "2025-12-14", "amount": -100}]}})
        self.assertTrue(has(errors, "advance_tax[0].amount",
                            "non-negative number"), errors)

    def test_payment_string_amount(self):
        errors, _ = vcheck({"taxes_paid": {"advance_tax": [
            {"date": "2025-12-14", "amount": "20000"}]}})
        self.assertTrue(has(errors, "advance_tax[0].amount",
                            "non-negative number"), errors)

    def test_valid_payment_item_is_silent(self):
        errors, _ = vcheck({"taxes_paid": {"advance_tax": [
            {"date": "2025-12-14", "amount": 20_000}]}})
        self.assertEqual(errors, [])

    def test_payment_missing_date_flagged(self):
        # Regression lock (fixed): a payment item with no "date" passes silently, but the
        # engine then treats it as paid-at-filing (losing 234C credit) - the
        # very consequence the validator errors about for unparseable dates.
        errors, _ = vcheck({"taxes_paid": {"advance_tax": [{"amount": 20_000}]}})
        self.assertTrue(has(errors, "advance_tax[0]", "date"), errors)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class TestEnums(unittest.TestCase):
    def test_bad_regime(self):
        errors, _ = vcheck({"regime": "New"})
        self.assertTrue(has(errors, "regime must be"), errors)

    def test_valid_regimes(self):
        for r in ("new", "old", "both"):
            errors, _ = vcheck({"regime": r})
            self.assertFalse(has(errors, "regime must be"), (r, errors))

    def test_bad_age_category(self):
        errors, _ = vcheck({"age_category": "elderly"})
        self.assertTrue(has(errors, "age_category must be"), errors)

    def test_valid_age_categories(self):
        for a in ("regular", "senior", "super_senior"):
            errors, _ = vcheck({"age_category": a})
            self.assertFalse(has(errors, "age_category must be"), (a, errors))

    def test_nri_is_hard_error(self):
        errors, _ = vcheck({"residential_status": "NRI"})
        self.assertTrue(has(errors, "out of scope"), errors)

    def test_rnor_is_hard_error(self):
        errors, _ = vcheck({"residential_status": "RNOR"})
        self.assertTrue(has(errors, "out of scope"), errors)

    def test_resident_spellings_accepted(self):
        for rs in ("resident", "Resident", "ROR",
                   "resident and ordinarily resident"):
            errors, _ = vcheck({"residential_status": rs})
            self.assertEqual(errors, [], rs)

    def test_non_string_residential_status_no_crash(self):
        # Regression lock (fixed): rs.lower() raises AttributeError on a truthy non-string
        # (walk() records "must be a string" but check() keeps going and dies).
        errors, _ = vcheck({"residential_status": 123})
        self.assertTrue(has(errors, "residential_status", "must be a string"),
                        errors)


# ---------------------------------------------------------------------------
# Cross-checks against document totals
# ---------------------------------------------------------------------------

class TestCrossChecks(unittest.TestCase):
    def test_form16_component_sum_mismatch(self):
        inp = clean()
        inp["income"]["salary"]["form16_17_3"] = 100  # sum now 1,500,100
        errors, _ = vcheck(inp)
        self.assertTrue(has(errors, "17(1)+17(2)+17(3)", "Re-read Form 16"),
                        errors)

    def test_form16_component_sum_match_is_silent(self):
        errors, _ = vcheck(clean())
        self.assertEqual(errors, [])

    def test_partial_components_still_checked(self):
        # Even a single 17(x) component present must reconcile with gross.
        errors, _ = vcheck({"income": {"salary":
                            {"gross": 1_500_000, "form16_17_1": 1_000_000}}})
        self.assertTrue(has(errors, "Re-read Form 16"), errors)

    def test_gross_vs_form16_gross_salary_mismatch(self):
        inp = clean()
        inp["source_totals"]["form16_gross_salary"] = 1_400_000
        errors, _ = vcheck(inp)
        self.assertTrue(has(errors, "!= Form 16 gross salary"), errors)

    def test_tds_exceeding_26as_is_error(self):
        inp = clean()
        inp["taxes_paid"]["tds"] = 125_000  # 26AS says 120,000
        errors, _ = vcheck(inp)
        self.assertTrue(has(errors, "exceeds 26AS"), errors)

    def test_tds_below_26as_is_warning_not_error(self):
        inp = clean()
        inp["taxes_paid"]["tds"] = 100_000  # under-claiming: warn, don't block
        errors, warnings = vcheck(inp)
        self.assertFalse(has(errors, "exceeds 26AS"), errors)
        self.assertTrue(has(warnings, "form26as_total_tds",
                            "reconcile before filing"), warnings)

    def test_tds_vs_form16_gap_over_10_is_warning(self):
        inp = clean()
        inp["source_totals"]["form16_total_tds"] = 105_000  # claimed 120,000
        _, warnings = vcheck(inp)
        self.assertTrue(has(warnings, "form16_total_tds",
                            "reconcile before filing"), warnings)

    def test_tds_vs_form16_gap_of_10_is_silent(self):
        inp = clean()
        inp["source_totals"]["form16_total_tds"] = 119_990  # |diff| == 10
        errors, warnings = vcheck(inp)
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])

    def test_ais_savings_interest_underreported(self):
        inp = clean()
        inp["income"]["other_sources"]["savings_interest"] = 2_000  # AIS 9,000
        errors, _ = vcheck(inp)
        self.assertTrue(has(errors, "savings_interest", "invites a notice"),
                        errors)

    def test_ais_dividends_underreported_when_absent(self):
        errors, _ = vcheck({"source_totals": {"ais_dividends": 8_200}})
        self.assertTrue(has(errors, "dividends", "invites a notice"), errors)

    def test_ais_gap_within_100_tolerated(self):
        inp = clean()
        inp["income"]["other_sources"]["savings_interest"] = 8_950  # gap 50
        errors, _ = vcheck(inp)
        self.assertEqual(errors, [])

    def test_ais_cross_check_with_string_reported_value_no_crash(self):
        # Regression lock (fixed): `ais_v - (rep_v or 0)` raises TypeError when the
        # reported field is a non-numeric truthy value like "8200"; the walk()
        # type error is recorded but check() crashes before returning it.
        errors, _ = vcheck({"income": {"other_sources": {"dividends": "8200"}},
                            "source_totals": {"ais_dividends": 8_200}})
        self.assertTrue(has(errors, "dividends", "finite number"), errors)


# ---------------------------------------------------------------------------
# House property elements
# ---------------------------------------------------------------------------

class TestHouseProperty(unittest.TestCase):
    def test_valid_entries_are_silent(self):
        errors, _ = vcheck({"income": {"house_property": [
            {"type": "self_occupied", "interest_paid": 180_000},
            {"type": "let_out", "rent_received": 240_000,
             "municipal_taxes": 6_000, "interest_paid": 150_000}]}})
        self.assertEqual(errors, [])

    def test_bad_type_value(self):
        errors, _ = vcheck({"income": {"house_property": [
            {"type": "rented", "rent_received": 240_000}]}})
        self.assertTrue(has(errors, "house_property[0].type"), errors)

    def test_missing_type_value(self):
        errors, _ = vcheck({"income": {"house_property": [
            {"interest_paid": 180_000}]}})
        self.assertTrue(has(errors, "house_property[0].type"), errors)

    def test_non_dict_element_rejected(self):
        # Regression lock (fixed): a bare string inside house_property produces ZERO errors
        # (the element loop silently skips non-dicts, unlike the payment-item
        # loop) - and tax_engine.py then crashes with AttributeError.
        errors, _ = vcheck({"income": {"house_property": ["oops"]}})
        self.assertTrue(has(errors, "house_property[0]"), errors)

    def test_string_amount_rejected(self):
        # Regression lock (fixed): house_property element amounts get no type check; a
        # string rent passes validation but tax_engine.py exits 2 telling the
        # user to run validate_income.py - which had just passed the file.
        errors, _ = vcheck({"income": {"house_property": [
            {"type": "let_out", "rent_received": "not-a-number"}]}})
        self.assertTrue(has(errors, "house_property[0]"), errors)

    def test_negative_amount_rejected(self):
        # Regression lock (fixed): negative HP amounts passed validation and were
        # then silently clamped to 0 by the engine's _pos() - inconsistent
        # with the "negative amount" error every schema-typed field gets.
        errors, _ = vcheck({"income": {"house_property": [
            {"type": "let_out", "rent_received": -5_000}]}})
        self.assertTrue(has(errors, "house_property[0]"), errors)


# ---------------------------------------------------------------------------
# Completeness nudges (warnings)
# ---------------------------------------------------------------------------

class TestCompletenessWarnings(unittest.TestCase):
    def test_salary_without_bank_interest_warns(self):
        _, warnings = vcheck({"income": {"salary": {"gross": 1_000_000}},
                              "taxes_paid": {"tds": 60_000}})
        self.assertTrue(has(warnings, "bank interest"), warnings)

    def test_savings_interest_suppresses_bank_warning(self):
        _, warnings = vcheck({"income": {"salary": {"gross": 1_000_000},
                                         "other_sources":
                                             {"savings_interest": 5_000}},
                              "taxes_paid": {"tds": 60_000}})
        self.assertFalse(has(warnings, "bank interest"), warnings)

    def test_fd_interest_also_suppresses_bank_warning(self):
        _, warnings = vcheck({"income": {"salary": {"gross": 1_000_000},
                                         "other_sources":
                                             {"fd_interest": 5_000}},
                              "taxes_paid": {"tds": 60_000}})
        self.assertFalse(has(warnings, "bank interest"), warnings)

    def test_missing_tds_on_taxable_salary_warns(self):
        _, warnings = vcheck({"income": {"salary": {"gross": 500_000}}})
        self.assertTrue(has(warnings, "no TDS entered"), warnings)

    def test_missing_tds_below_basic_exemption_is_silent(self):
        _, warnings = vcheck({"income": {"salary": {"gross": 300_000}}})
        self.assertFalse(has(warnings, "no TDS entered"), warnings)

    def test_zero_tds_on_high_salary_warns(self):
        _, warnings = vcheck({"income": {"salary": {"gross": 1_300_000}},
                              "taxes_paid": {"tds": 0}})
        self.assertTrue(has(warnings, "exactly 0", "12,75,000"), warnings)

    def test_zero_tds_on_modest_salary_is_silent(self):
        _, warnings = vcheck({"income": {"salary": {"gross": 900_000}},
                              "taxes_paid": {"tds": 0}})
        self.assertFalse(has(warnings, "exactly 0"), warnings)

    def test_absent_source_totals_warns(self):
        _, warnings = vcheck({"income": {"salary": {"gross": 1_000_000}}})
        self.assertTrue(has(warnings, "source_totals absent"), warnings)


# ---------------------------------------------------------------------------
# check() must never crash on malformed shapes
# ---------------------------------------------------------------------------

class TestMalformedShapes(unittest.TestCase):
    def test_non_dict_root_reports_error(self):
        # Regression lock (fixed): walk() records "root: expected an object" but check()
        # then calls inp.get(...) - AttributeError on a list/str root,
        # TypeError ("pan" in 5) on a number root.
        for raw in ("[]", '"hello"', "5"):
            errors, _ = vcheck_raw(raw)
            self.assertTrue(has(errors, "expected an object"), (raw, errors))

    def test_non_dict_income_containers_report_error(self):
        # Regression lock (fixed): same pattern one level down - income, income.salary,
        # income.other_sources as truthy non-dicts crash the cross-check /
        # nudge sections (sal.get, os_.get) after walk() flagged them.
        for payload in ({"income": "salary"},
                        {"income": {"salary": [1, 2]}},
                        {"income": {"salary": "2400000"}},
                        {"income": {"salary": {"gross": 1_000_000},
                                    "other_sources": [1]}}):
            errors, _ = vcheck(payload)
            self.assertTrue(has(errors, "expected an object"),
                            (payload, errors))

    def test_non_dict_taxes_paid_and_source_totals_report_error(self):
        # Regression lock (fixed): `tp = inp.get("taxes_paid") or {}` / same for
        # source_totals keep a truthy non-dict, then .get() crashes.
        for payload in ({"taxes_paid": [1]}, {"source_totals": [1]}):
            errors, _ = vcheck(payload)
            self.assertTrue(has(errors, "expected an object"),
                            (payload, errors))

    def test_scalar_list_fields_report_error(self):
        # Regression lock (fixed): enumerate(5) raises TypeError when house_property or
        # advance_tax is a scalar, after walk() already said "must be a list".
        for payload in ({"income": {"house_property": 5}},
                        {"taxes_paid": {"advance_tax": 5}}):
            errors, _ = vcheck(payload)
            self.assertTrue(has(errors, "must be a list"), (payload, errors))


# ---------------------------------------------------------------------------
# CLI: exit codes and output shape
# ---------------------------------------------------------------------------

class TestCLI(TempFileMixin, unittest.TestCase):
    def test_explicit_date_survives_future_cli_clock(self):
        path = self.write("warn.json", {"financial_year": "2025-26", "filing_date": "2026-07-20"})
        source = """import sys
from datetime import date
sys.path.insert(0, sys.argv.pop(1))
import tax_years, validate_income
class FutureDate(date):
    @classmethod
    def today(cls): return cls(2027, 1, 5)
tax_years.date = validate_income.date = FutureDate
sys.exit(validate_income.main(sys.argv))
"""
        r = subprocess.run([sys.executable, "-c", source, SCRIPT_DIR, path], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_planning_payment_errors_exit_2_without_traceback(self):
        for extra in ({"advance_tax": [{"date": "2026-12-11", "amount": 100}]},
                      {"self_assessment": [{"date": "2026-12-10", "amount": 100}]}):
            inp = {"financial_year": "2026-27", "purpose": "advance_tax", "as_of_date": "2026-12-10",
                   "income": {"other_sources": {"other": 2_000_000}}, "taxes_paid": extra}
            r = run_cli(ENGINE, self.write("plan.json", inp))
            self.assertEqual(r.returncode, 2)
            self.assertNotIn("Traceback", r.stderr)

    def test_context_type_errors_are_not_duplicated(self):
        for inp, field in (({"financial_year": 2026}, "financial_year"),
                           ({"income": {"presumptive_section": 44}}, "income.presumptive_section")):
            errors, _ = check(inp)
            self.assertEqual(len(errors), 1, errors)
            self.assertIn(field + ": must be a string", errors[0])

    def test_presumptive_44ae_and_new_year_self_occupied_label(self):
        errors, _ = check({"income": {"business_presumptive_income": 100_000, "presumptive_section": "44AE"}})
        self.assertTrue(has(errors, "44AE is unsupported"))
        errors, _ = check({"financial_year": "2026-27", "filing_date": "2027-07-20",
                           "income": {"house_property": [{"type": "self_occupied"}] * 3}})
        self.assertTrue(has(errors, "s.21(7)"))

    def test_no_args_prints_usage_exit_0(self):
        r = run_cli(VALIDATOR)
        self.assertEqual(r.returncode, 0)
        self.assertIn("Usage:", r.stdout)

    def test_help_flag_prints_usage_exit_0(self):
        r = run_cli(VALIDATOR, "--help")
        self.assertEqual(r.returncode, 0)
        self.assertIn("Usage:", r.stdout)

    def test_example_file_exits_0(self):
        r = run_cli(VALIDATOR, EXAMPLE)
        self.assertEqual(r.returncode, 0)
        self.assertIn("OK", r.stdout)
        self.assertIn("0 error(s)", r.stdout)

    def test_warnings_only_exits_0(self):
        path = self.write("warn.json", {"financial_year": "2025-26", "filing_date": "2026-07-20"})
        r = run_cli(VALIDATOR, path)
        self.assertEqual(r.returncode, 0)
        self.assertIn("WARNING", r.stdout)
        self.assertIn("OK", r.stdout)

    def test_errors_exit_1(self):
        path = self.write("bad.json", {"salary_gross": 1})
        r = run_cli(VALIDATOR, path)
        self.assertEqual(r.returncode, 1)
        self.assertIn("ERROR", r.stdout)
        self.assertIn("FAILED", r.stdout)

    def test_malformed_json_exit_1(self):
        path = self.write("nojson.json", "{not json")
        r = run_cli(VALIDATOR, path)
        self.assertEqual(r.returncode, 1)
        self.assertIn("INVALID JSON", r.stdout)

    def test_stdin_dash(self):
        r = run_cli(VALIDATOR, "-", stdin=json.dumps(CLEAN))
        self.assertEqual(r.returncode, 0)

    def test_json_output_shape_valid(self):
        path = self.write("clean.json", CLEAN)
        r = run_cli(VALIDATOR, path, "--json")
        self.assertEqual(r.returncode, 0)
        out = json.loads(r.stdout)
        self.assertEqual(set(out), {"valid", "errors", "warnings"})
        self.assertIs(out["valid"], True)
        self.assertEqual(out["errors"], [])
        self.assertEqual(out["warnings"], [])

    def test_json_output_shape_invalid(self):
        path = self.write("bad.json", {"salary_gross": 1})
        r = run_cli(VALIDATOR, path, "--json")
        self.assertEqual(r.returncode, 1)
        out = json.loads(r.stdout)
        self.assertIs(out["valid"], False)
        self.assertTrue(out["errors"])
        self.assertTrue(all(isinstance(e, str) for e in out["errors"]))

    def test_missing_file_clean_error(self):
        # Regression lock (fixed): open() is unguarded - a missing file dies with a
        # FileNotFoundError traceback (tax_engine.py catches OSError, exit 2).
        r = run_cli(VALIDATOR, os.path.join(self._tmpdir, "absent.json"))
        self.assertNotEqual(r.returncode, 0)
        self.assertNotIn("Traceback", r.stderr)


# ---------------------------------------------------------------------------
# Pipeline contract: validator exit 0 => tax_engine.py runs cleanly
# ---------------------------------------------------------------------------

class TestPipelineContract(TempFileMixin, unittest.TestCase):
    def assert_contract(self, path):
        """If the validator passes a file, the engine must accept it too."""
        v = run_cli(VALIDATOR, path)
        if v.returncode == 0:
            e = run_cli(ENGINE, path)
            self.assertEqual(
                e.returncode, 0,
                f"validator passed but engine failed:\n{e.stderr[:500]}")

    def test_example_file_flows_through_engine(self):
        v = run_cli(VALIDATOR, EXAMPLE)
        self.assertEqual(v.returncode, 0)
        e = run_cli(ENGINE, EXAMPLE)
        self.assertEqual(e.returncode, 0, e.stderr[:500])
        self.assertIn("RECOMMENDED", e.stdout)

    def test_clean_file_flows_through_engine(self):
        path = self.write("clean.json", CLEAN)
        v = run_cli(VALIDATOR, path)
        self.assertEqual(v.returncode, 0)
        e = run_cli(ENGINE, path, "--json")
        self.assertEqual(e.returncode, 0, e.stderr[:500])
        out = json.loads(e.stdout)
        self.assertIn("comparison", out)

    def test_invalid_file_is_blocked_by_the_gate(self):
        path = self.write("typo.json", {"salary_gross": 2_500_000})
        v = run_cli(VALIDATOR, path)
        self.assertEqual(v.returncode, 1)  # gate closed; engine never runs

    def test_contract_holds_for_non_dict_hp_element(self):
        # Regression lock (fixed): validator exits 0 on this file, then the engine dies
        # with an uncaught AttributeError traceback (exit 1).
        path = self.write("hp_elem.json",
                          {"income": {"house_property": ["oops"]}})
        self.assert_contract(path)

    def test_contract_holds_for_string_hp_amount(self):
        # Regression lock (fixed): validator exits 0, engine exits 2 with "run
        # validate_income.py on this file first" - circular advice.
        path = self.write("hp_amt.json",
                          {"income": {"house_property": [
                              {"type": "let_out", "rent_received": "abc"}]}})
        self.assert_contract(path)


# ---------------------------------------------------------------------------
# Schema fields added in engine v1.2: exempt_retirement, winnings, relief_89,
# and the s.23(4) two-self-occupied-properties limit
# ---------------------------------------------------------------------------

class TestV12Fields(unittest.TestCase):
    def test_exempt_retirement_accepted(self):
        errors, _ = vcheck({"income": {"salary": {
            "gross": 2_000_000, "exempt_retirement": 500_000}}})
        self.assertFalse(any("exempt_retirement" in e for e in errors), errors)

    def test_winnings_accepted(self):
        errors, _ = vcheck({"income": {"other_sources": {"winnings": 50_000}}})
        self.assertFalse(any("winnings" in e for e in errors), errors)

    def test_negative_winnings_rejected(self):
        errors, _ = vcheck({"income": {"other_sources": {"winnings": -1}}})
        self.assertTrue(has(errors, "winnings"), errors)

    def test_relief_89_accepted(self):
        errors, _ = vcheck({"relief_89": 30_000,
                            "income": {"salary": {"gross": 2_000_000}}})
        self.assertFalse(any("relief_89" in e for e in errors), errors)

    def test_relief_89_wrong_type_rejected(self):
        errors, _ = vcheck({"relief_89": "thirty thousand"})
        self.assertTrue(has(errors, "relief_89"), errors)

    def test_two_self_occupied_ok(self):
        errors, _ = vcheck({"income": {"house_property": [
            {"type": "self_occupied", "interest_paid": 100_000},
            {"type": "self_occupied", "interest_paid": 50_000}]}})
        self.assertFalse(any("s.23(4)" in e for e in errors), errors)

    def test_three_self_occupied_rejected(self):
        errors, _ = vcheck({"income": {"house_property": [
            {"type": "self_occupied"}, {"type": "self_occupied"},
            {"type": "self_occupied"}]}})
        self.assertTrue(has(errors, "s.23(4)"), errors)


class TestIncomeYearsAndPlanning(TempFileMixin, unittest.TestCase):
    def plan(self, **fields):
        obj = {"financial_year": "2026-27", "purpose": "advance_tax",
               "as_of_date": "2026-12-10", "expected_tax_credits": {"tds": 10_000},
               "income": {"other_sources": {"other": 2_000_000}}}
        obj.update(fields)
        return obj

    def test_new_year_return_dates_accepted(self):
        obj = clean()
        obj.update(financial_year="2026-27", due_date="2027-07-31", filing_date="2027-07-28")
        self.assertEqual(vcheck(obj), ([], []))
        obj["due_date"] = "2026-07-31"
        self.assertTrue(has(vcheck(obj)[0], "due_date", "after the selected income year"))
        obj.update(financial_year="2025-26", due_date="2027-07-31")
        self.assertTrue(has(vcheck(obj)[0], "due_date", "does not belong"))

    def test_new_year_plan_accepted(self):
        self.assertEqual(vcheck(self.plan())[0], [])

    def test_old_year_plan_accepted(self):
        obj = self.plan(financial_year="2025-26", as_of_date="2025-12-10")
        self.assertEqual(vcheck(obj)[0], [])

    def test_unsupported_and_wrong_shaped_years_never_crash(self):
        for fy in ("2024-25", "2027-28", "2026-2027", "", None, 2026, [], {}, True):
            with self.subTest(fy=fy):
                errors, _ = vcheck({"financial_year": fy})
                self.assertTrue(has(errors, "financial_year"), errors)

    def test_wrong_shaped_purpose_never_crashes(self):
        for purpose in (None, 1, [], {}, True, "estimate"):
            with self.subTest(purpose=purpose):
                self.assertTrue(has(vcheck({"purpose": purpose})[0], "purpose"))

    def test_missing_year_is_warned_and_cannot_be_used_for_planning(self):
        errors, warnings = vcheck({})
        self.assertEqual(errors, [])
        self.assertTrue(has(warnings, "financial_year omitted", "2025-26"))
        obj = self.plan(as_of_date="2025-12-10")
        del obj["financial_year"]
        self.assertTrue(has(vcheck(obj)[0], "financial_year is required"))

    def test_as_of_date_required_strict_and_in_selected_year(self):
        for day in (None, [], "20261210", "2026-02-29", "2026-03-31", "2027-04-01"):
            with self.subTest(day=day):
                self.assertTrue(has(vcheck(self.plan(as_of_date=day))[0], "as_of_date"))
        for day in ("2026-04-01", "2027-03-31"):
            self.assertEqual(vcheck(self.plan(as_of_date=day))[0], [])

    def test_planning_rejects_return_fields(self):
        for field in ("due_date", "filing_date"):
            self.assertTrue(has(vcheck(self.plan(**{field: "2027-07-31"}))[0], field, "omit"))

    def test_returns_reject_planning_fields(self):
        for field, val in (("as_of_date", "2026-12-10"), ("expected_tax_credits", {"tds": 5_000})):
            self.assertTrue(has(vcheck({field: val})[0], field, "advance_tax"))

    def test_advance_payment_windows_are_selected_by_year(self):
        for fy, day in (("2025-26", "2025-12-15"), ("2026-27", "2026-12-15")):
            obj = {"financial_year": fy, "filing_date": str(int(fy[:4]) + 1) + "-07-20",
                   "taxes_paid": {"advance_tax": [{"date": day, "amount": 5_000}]}}
            self.assertEqual(vcheck(obj)[0], [])
            obj["financial_year"] = "2025-26" if fy == "2026-27" else "2026-27"
            self.assertTrue(has(vcheck(obj)[0], "outside", "FY"))

    def test_planning_refuses_future_payments(self):
        obj = self.plan(taxes_paid={"advance_tax": [{"date": "2026-12-15", "amount": 5_000}]})
        self.assertTrue(has(vcheck(obj)[0], "future payment"))
        obj["taxes_paid"]["advance_tax"][0]["date"] = "2026-12-10"
        self.assertEqual(vcheck(obj)[0], [])

    def test_planning_refuses_self_assessment(self):
        obj = self.plan(taxes_paid={"self_assessment": [{"date": "2026-12-01", "amount": 5_000}]})
        self.assertTrue(has(vcheck(obj)[0], "self_assessment", "omit"))

    def test_expected_credits_are_checked_independently_from_recorded_totals(self):
        obj = self.plan(expected_tax_credits={"tds": 20_000}, taxes_paid={"tds": 5_000},
                        source_totals={"form26as_total_tds": 5_000})
        self.assertEqual(vcheck(obj)[0], [])
        obj["expected_tax_credits"]["tds"] = 4_000
        self.assertTrue(has(vcheck(obj)[0], "expected_tax_credits.tds", "cannot be less"))

    def test_expected_credits_reject_invalid_values_and_unknown_keys(self):
        for val in (-1, True, "5000", None, float("nan"), float("inf")):
            self.assertTrue(has(vcheck(self.plan(expected_tax_credits={"tds": val}))[0],
                                "expected_tax_credits.tds"))
        self.assertTrue(has(vcheck(self.plan(expected_tax_credits={"tds_total": 5_000}))[0], "Unknown key"))
        for val in ([], None, 5_000):
            self.assertTrue(has(vcheck(self.plan(expected_tax_credits=val))[0], "expected_tax_credits"))

    def test_no_expected_credit_estimate_warns(self):
        obj = self.plan()
        del obj["expected_tax_credits"]
        self.assertTrue(has(vcheck(obj)[1], "expected_tax_credits absent"))

    def test_new_year_cannot_file_before_year_end(self):
        errors, _ = vcheck({"financial_year": "2026-27", "filing_date": "2027-03-31"})
        self.assertTrue(has(errors, "after the selected income year"))
        self.assertEqual(vcheck({"financial_year": "2026-27", "filing_date": "2027-04-01"})[0], [])

    def test_annual_salary_forecast_is_not_forced_to_source_period(self):
        obj = self.plan(income={"salary": {"gross": 2_400_000, "form16_17_1": 1_200_000}},
                        source_totals={"form16_gross_salary": 1_200_000})
        errors, warnings = vcheck(obj)
        self.assertEqual(errors, [])
        self.assertTrue(has(warnings, "full-year forecast", "period"))

    def test_professional_tax_sanity_is_a_warning(self):
        errors, warnings = vcheck(self.plan(income={"salary": {"gross": 2_000_000, "professional_tax": 6_000}}))
        self.assertEqual(errors, [])
        self.assertTrue(has(warnings, "Professional tax exceeds 2,500"))

    def test_planning_undated_payment_message(self):
        errors, _ = vcheck(self.plan(taxes_paid={"advance_tax": [{"amount": 5_000}]}))
        self.assertTrue(has(errors, "on or before as_of_date"))
        self.assertFalse(has(errors, "paid-at-filing"))

    def test_bad_filing_date_is_reported_once(self):
        errors, _ = vcheck({"filing_date": "2026-02-30"})
        self.assertEqual(len([e for e in errors if "filing_date" in e]), 1)

    def test_cli_invalid_planning_date_has_no_traceback(self):
        path = self.write("bad-plan.json", self.plan(as_of_date="2028-01-01"))
        result = subprocess.run([sys.executable, ENGINE, path], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn("ERROR", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_cli_rejects_unsupported_year_in_both_tools(self):
        path = self.write("unknown.json", {"financial_year": "2027-28"})
        for script in (VALIDATOR, ENGINE):
            r = run_cli(script, path, "--json")
            self.assertNotEqual(r.returncode, 0)
            self.assertNotIn("Traceback", r.stdout + r.stderr)

    def test_cli_planning_output_is_not_a_return(self):
        path = self.write("plan.json", self.plan())
        self.assertEqual(run_cli(VALIDATOR, path).returncode, 0)
        r = run_cli(ENGINE, path, "--json")
        self.assertEqual(r.returncode, 0, r.stderr)
        result = json.loads(r.stdout)
        self.assertEqual(result["purpose"], "advance_tax")
        self.assertNotIn("interest_and_fees", result["new"])
        rendered = run_cli(ENGINE, path).stdout
        self.assertIn("TY 2026-27", rendered)
        self.assertIn("2026-12-15", rendered)
        self.assertNotIn("NET PAYABLE", rendered)


if __name__ == "__main__":
    unittest.main()
