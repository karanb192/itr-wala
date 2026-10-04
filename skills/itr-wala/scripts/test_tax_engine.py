"""Golden tests for tax_engine.py - every expected value hand-derived from
FY 2025-26 (AY 2026-27) rules. Run: python3 -m unittest test_tax_engine -v
"""

import unittest
from datetime import date

from tax_engine import compute as engine_compute


def compute(inp, today=date(2026, 7, 20)):
    return engine_compute(inp, today=today)


def new_liab(r):
    return r["new"]["tax"]["total_tax_liability"]


def old_liab(r):
    return r["old"]["tax"]["total_tax_liability"]


class TestNewRegime(unittest.TestCase):
    def test_salary_1275k_is_zero(self):
        # 12.75L - 75k std = 12L slab income -> tax 60k, 87A rebate 60k -> 0
        r = compute({"income": {"salary": {"gross": 1_275_000}}})
        self.assertEqual(new_liab(r), 0)

    def test_salary_25l(self):
        # 24.25L -> 300000 + 30%*25000 = 307500; *1.04 = 319800
        r = compute({"income": {"salary": {"gross": 2_500_000}}})
        self.assertEqual(new_liab(r), 319_800)

    def test_marginal_relief_at_121l(self):
        # Other income 12.1L (no std ded): slab tax 61500 > excess 10000
        # -> pay 10000 + 4% cess = 10400
        r = compute({"income": {"other_sources": {"other": 1_210_000}}})
        self.assertEqual(new_liab(r), 10_400)

    def test_ltcg_counts_toward_rebate_income_threshold(self):
        r = compute({"income": {"salary": {"gross": 1_275_000},
                                "capital_gains": {"ltcg_112a": 200_000}}})
        # Total income 14L: no rebate or marginal relief. Slab tax 60,000
        # plus (2L - 1.25L) * 12.5% = 9,375; with cess = 72,150.
        self.assertEqual(new_liab(r), 72_150)

    def test_stcg_kept_out_of_rebate(self):
        # Salary 6.75L (slab 6L) + STCG 111A 1L; total 7L <= 12L so rebate applies
        # but only to slab tax (10000). STCG 20% = 20000 stays. *1.04 = 20800
        r = compute({"income": {"salary": {"gross": 675_000},
                                "capital_gains": {"stcg_111a": 100_000}}})
        self.assertEqual(new_liab(r), 20_800)

    def test_ltcg_only_absorbed_by_basic_exemption(self):
        # Only income: LTCG 112A 3L. Taxable after 1.25L exemption = 1.75L,
        # fully absorbed by unused 4L basic exemption -> 0
        r = compute({"income": {"capital_gains": {"ltcg_112a": 300_000}}})
        self.assertEqual(new_liab(r), 0)

    def test_surcharge_10pct_at_60l_salary(self):
        # 59.25L slab: 300000 + 30%*3525000 = 1357500; +10% surcharge = 1493250
        # no marginal relief (excess income 925000 > extra tax); *1.04 = 1552980
        r = compute({"income": {"salary": {"gross": 6_000_000}}})
        self.assertEqual(new_liab(r), 1_552_980)

    def test_surcharge_marginal_relief_on_ltcg_heavy_income(self):
        # LTCG 112A 50,00,010 only. Taxable = 50,00,010 - 1,25,000 - 4,00,000(BE)
        # = 44,75,010 -> tax 5,59,376.25, surcharge 10% = 55,937.63.
        # Tax at the 50L threshold with the same mix = 44,75,000*12.5% = 5,59,375;
        # relief caps tax+surcharge at 5,59,375 + 10 -> 5,59,385 *1.04 = 5,81,760
        r = compute({"regime": "new",
                     "income": {"capital_gains": {"ltcg_112a": 5_000_010}}})
        self.assertEqual(new_liab(r), 581_760)
        self.assertGreater(r["new"]["tax"]["surcharge_marginal_relief"], 0)

    def test_surcharge_15pct_cap_and_relief_stcg_above_1cr(self):
        # STCG 111A 1,01,00,000: taxable 97,00,000 -> tax 19,40,000; 15% cap
        # surcharge 2,91,000; at 1cr threshold: 96,00,000*20%*1.10 = 21,12,000;
        # relief 19,000 -> 22,12,000 *1.04 = 23,00,480
        r = compute({"regime": "new",
                     "income": {"capital_gains": {"stcg_111a": 10_100_000}}})
        self.assertEqual(new_liab(r), 2_300_480)

    def test_surcharge_25pct_cap_new_regime_6cr(self):
        # Salary 6cr new regime: slab income 5,99,25,000 -> tax 1,75,57,500;
        # surcharge capped at 25% = 43,89,375 (no 37% tier in new regime);
        # no marginal relief (rate below 5cr threshold is also 25%);
        # *1.04 = 2,28,24,750
        r = compute({"regime": "new", "income": {"salary": {"gross": 60_000_000}}})
        self.assertEqual(new_liab(r), 22_824_750)
        self.assertEqual(r["new"]["tax"]["surcharge_rate"], 0.25)

    def test_vda_flat_30_no_rebate_no_basic_exemption(self):
        # Crypto only, 3L: 30% flat = 90000, no basic-exemption set-off,
        # no 87A against special income; *1.04 = 93600
        r = compute({"income": {"capital_gains": {"vda": 300_000}}})
        self.assertEqual(new_liab(r), 93_600)

    def test_sop_interest_ignored_in_new_but_allowed_in_old(self):
        # Salary 20L, self-occupied home-loan interest 2.5L
        # NEW: 19.25L -> 20k+40k+60k+65k = 185000 *1.04 = 192400
        # OLD: 19.5L - 2L(capped) = 17.5L -> 12500+100000+225000 = 337500 *1.04 = 351000
        r = compute({"income": {"salary": {"gross": 2_000_000},
                                "house_property": [{"type": "self_occupied",
                                                    "interest_paid": 250_000}]}})
        self.assertEqual(new_liab(r), 192_400)
        self.assertEqual(old_liab(r), 351_000)
        self.assertEqual(r["comparison"]["recommended_regime"], "new")


class TestOldRegime(unittest.TestCase):
    def test_salary_10l_with_80c(self):
        # 10L - 50k std = 9.5L; -1.5L 80C = 8L -> 12500 + 60000 = 72500 *1.04 = 75400
        r = compute({"income": {"salary": {"gross": 1_000_000}},
                     "deductions": {"80c": 150_000}})
        self.assertEqual(old_liab(r), 75_400)

    def test_80c_capped(self):
        r = compute({"income": {"salary": {"gross": 1_000_000}},
                     "deductions": {"80c": 300_000}})
        self.assertEqual(r["old"]["deductions"]["80c"], 150_000)

    def test_old_rebate_under_5l(self):
        # 5.4L - 50k std = 4.9L -> tax 12000 -> rebate 12000 -> 0
        r = compute({"income": {"salary": {"gross": 540_000}}})
        self.assertEqual(old_liab(r), 0)

    def test_rebate_survives_288a_rounding_band(self):
        # s.288A rounds total income to nearest 10: old-regime 5,00,004 -> 5,00,000
        # keeps the 12,500 rebate -> zero tax. New-regime slab 12,00,004 likewise.
        r = compute({"regime": "old",
                     "income": {"other_sources": {"other": 500_004}}})
        self.assertEqual(old_liab(r), 0)
        r2 = compute({"regime": "new", "income": {"salary": {"gross": 1_275_004}}})
        self.assertEqual(r2["new"]["tax"]["total_tax_liability"], 0)

    def test_senior_slabs(self):
        # Senior, FD interest 6L, 80TTB 50k -> TI 5.5L
        # slabs: 3L nil, 3-5L 5% = 10000, 5-5.5 20% = 10000 -> 20000 *1.04 = 20800
        r = compute({"age_category": "senior",
                     "income": {"other_sources": {"fd_interest": 600_000}}})
        self.assertEqual(old_liab(r), 20_800)


class TestRegressionLocks(unittest.TestCase):
    def test_234a_stops_at_self_assessment_payment(self):
        # Liability 2,08,000 fully paid by challan 5 days after the due date,
        # return filed months later: 234A = 1 month (2,080), not 4 (8,320).
        # 234B still runs Apr..Aug = 5 months on the same base = 10,400.
        r = compute({"regime": "new",
                     "income": {"salary": {"gross": 2_075_000}},
                     "taxes_paid": {"self_assessment": [
                         {"date": "2026-08-05", "amount": 208_000}]},
                     "due_date": "2026-07-31", "filing_date": "2026-11-30"})
        i = r["new"]["interest_and_fees"]
        self.assertEqual(i["234A"], 2_080)
        self.assertEqual(i["234B"], 10_400)

    def test_234ab_mid_month_partial_payment_charges_month_once(self):
        # Liability 1,92,400 (salary 20L), SA 50,000 paid 15-Aug, filed 20-Sep.
        # Months count once from the anchor: 234A = 1,92,400x1%x1 (Aug 1-15)
        # + 1,42,400x1%x1 (the one further month to 20-Sep) = 3,348 - NOT
        # 4,772, which would charge August twice on the balance. 234B =
        # 1,92,400x1%x5 (Apr..mid-Aug) + 1,42,400x1%x1 = 11,044.
        r = compute({"regime": "new", "income": {"salary": {"gross": 2_000_000}},
                     "taxes_paid": {"self_assessment": [
                         {"date": "2026-08-15", "amount": 50_000}]},
                     "due_date": "2026-07-31", "filing_date": "2026-09-20"})
        i = r["new"]["interest_and_fees"]
        self.assertEqual(i["234A"], 3_348)
        self.assertEqual(i["234B"], 11_044)

    def test_hp_loss_sets_off_against_ltcg(self):
        # s.71: let-out loss 2,00,000 + LTCG 112A 5,00,000 (old regime).
        # Loss absorbs the taxable gain; remainder soaked by basic exemption.
        # Total income 3,00,000 == GTI (never TI > GTI), tax = 0.
        r = compute({"regime": "old",
                     "income": {"house_property": [{"type": "let_out",
                                                    "interest_paid": 200_000}],
                                "capital_gains": {"ltcg_112a": 500_000}}})
        c = r["old"]
        self.assertEqual(c["tax"]["total_tax_liability"], 0)
        self.assertEqual(c["total_income"], 300_000)
        self.assertEqual(c["gross_total_income"], 300_000)

    def test_hp_muni_taxes_above_rent_make_no_loss(self):
        # s.23(2)/s.24(a): municipal taxes are deductible only up to the
        # annual value - NAV can never be negative. Rent 1L, muni 2L: the
        # NAV clamps to 0, so a let-out property with no interest produces
        # NO house-property loss at all (a negative NAV would have let a
        # 1L loss set off against other heads under s.71 - unlawful).
        r = compute({"regime": "old", "income": {"house_property": [
            {"type": "let_out", "rent_received": 100_000,
             "municipal_taxes": 200_000}]}})
        c = r["old"]
        self.assertEqual(c["heads"]["house_property"]["income"], 0)
        self.assertEqual(c["total_income"], 0)
        self.assertEqual(c["tax"]["total_tax_liability"], 0)
        self.assertTrue(any("Municipal taxes exceed rent" in w
                            for w in c["warnings"]))

    def test_hp_muni_taxes_above_rent_loss_limited_to_interest(self):
        # Same facts plus 50k interest: the loss is the interest ALONE
        # (50,000) - never 1,50,000. With salary 10L (old regime):
        # 10L - 50k std - 50k loss = 9L -> 92,500 + 4% = 96,200.
        r = compute({"regime": "old", "income": {
            "salary": {"gross": 1_000_000},
            "house_property": [{"type": "let_out", "rent_received": 100_000,
                                "municipal_taxes": 200_000,
                                "interest_paid": 50_000}]}})
        c = r["old"]
        self.assertEqual(c["heads"]["house_property"]["income"], -50_000)
        self.assertEqual(c["total_income"], 900_000)
        self.assertEqual(old_liab(r), 96_200)

    def test_hp_vacant_with_muni_taxes_no_loss(self):
        # Regression lock: a vacant let-out property (rent 0) paying muni
        # taxes 1L once booked a 1L loss. With the NAV clamp it contributes
        # nothing - only interest can create a house-property loss.
        r = compute({"income": {"house_property": [
            {"type": "let_out", "rent_received": 0,
             "municipal_taxes": 100_000}]}})
        for rk in ("new", "old"):
            self.assertEqual(r[rk]["heads"]["house_property"]["income"], 0)

    def test_hp_muni_taxes_equal_to_rent_income_is_interest_only(self):
        # Boundary: muni == rent -> NAV exactly 0; income is -interest only.
        r = compute({"regime": "old", "income": {"house_property": [
            {"type": "let_out", "rent_received": 100_000,
             "municipal_taxes": 100_000, "interest_paid": 100_000}]}})
        c = r["old"]
        self.assertEqual(c["heads"]["house_property"]["income"], -100_000)
        self.assertFalse(any("Municipal taxes exceed rent" in w
                             for w in c["warnings"]))

    def test_belated_return_forces_new_regime(self):
        # Old regime is cheaper here, but a belated return (s.139(4)) cannot
        # opt out of the new regime - recommendation must be forced to new.
        inp = {"income": {"salary": {"gross": 3_000_000,
                                     "exempt_allowances": 500_000},
                          "house_property": [{"type": "self_occupied",
                                              "interest_paid": 200_000}]},
               "deductions": {"80c": 150_000, "80ccd_1b": 50_000, "80d": 25_000},
               "due_date": "2026-07-31", "filing_date": "2026-09-10"}
        r = compute(inp)
        self.assertLess(r["comparison"]["old_total"], r["comparison"]["new_total"])
        self.assertEqual(r["comparison"]["recommended_regime"], "new")
        self.assertIn("belated", r["comparison"]["note"].lower())

    def test_old_rebate_not_applied_against_vda(self):
        # Old regime, slab 2,00,000 + VDA 1,00,000 (total 3L <= 5L): the 87A
        # rebate must NOT offset the 30% VDA tax -> 30,000 * 1.04 = 31,200
        r = compute({"regime": "old",
                     "income": {"other_sources": {"other": 200_000},
                                "capital_gains": {"vda": 100_000}}})
        self.assertEqual(old_liab(r), 31_200)

    def test_stray_advance_treated_as_self_assessment(self):
        # Advance tax dated after 31-Mar-2026 is not advance tax (s.211): it
        # must not suppress 234B/234C, but still counts as money paid.
        r = compute({"regime": "new",
                     "income": {"other_sources": {"other": 1_500_000}},
                     "taxes_paid": {"advance_tax": [
                         {"date": "2026-12-31", "amount": 100_000}]},
                     "due_date": "2026-09-15", "filing_date": "2026-07-20"})
        i = r["new"]["interest_and_fees"]
        self.assertEqual(i["234B"], 4_368)   # to the payment month, not zero
        self.assertEqual(i["234C"], 5_511)   # unaffected by the stray payment

    def test_r10_monotonic_at_float_epsilon_boundary(self):
        # Fuzzer-found: a true half-point (259,025.0) carried as ...4.999...97
        # used to round down, making more income cost less tax.
        base = {"regime": "new",
                "income": {"business_presumptive_income": 51_521,
                           "capital_gains": {"ltcg_other": 1_274_900,
                                             "vda": 299_000},
                           "salary": {"gross": 771_850}}}
        bumped = {"regime": "new",
                  "income": {"business_presumptive_income": 51_521,
                             "capital_gains": {"ltcg_other": 1_274_900,
                                               "vda": 299_000},
                             "salary": {"gross": 771_850 + 52_880}}}
        self.assertGreaterEqual(compute(bumped)["new"]["tax"]["total_tax_liability"],
                                compute(base)["new"]["tax"]["total_tax_liability"])


class TestInterestAndFees(unittest.TestCase):
    def test_234f_late_fee_5000(self):
        r = compute({"income": {"salary": {"gross": 1_000_000}},
                     "deductions": {"80c": 150_000},
                     "taxes_paid": {"tds": 75_400},
                     "due_date": "2026-09-15", "filing_date": "2026-10-01"})
        i = r["old"]["interest_and_fees"]
        self.assertEqual(i["234F"], 5_000)
        self.assertEqual(i["234A"], 0)  # nothing unpaid

    def test_234b_and_234c_no_prepaid(self):
        # New regime, other income 15L: tax 105000 *1.04 = 109200, nothing prepaid,
        # filed on time (2026-07-31).
        # 234B: 109200 * 1% * 4 months (Apr-Jul) = 4368
        # 234C: floor100 bases: Q1 16300*3%=489, Q2 49100*3%=1473,
        #       Q3 81900*3%=2457, Q4 109200*1%=1092 -> 5511
        r = compute({"regime": "new",
                     "income": {"other_sources": {"other": 1_500_000}},
                     "due_date": "2026-09-15", "filing_date": "2026-07-31"})
        i = r["new"]["interest_and_fees"]
        self.assertEqual(r["new"]["tax"]["total_tax_liability"], 109_200)
        self.assertEqual(i["234B"], 4_368)
        self.assertEqual(i["234C"], 5_511)
        self.assertEqual(i["234F"], 0)

    def test_234b_stops_at_self_assessment_payment(self):
        # Liability 1,09,200, nothing prepaid, full self-assessment challan paid
        # 2026-07-20, filed 2026-09-10 (on time). 234B runs Apr..Jul = 4 months
        # on 1,09,200 = 4,368 - NOT to the filing month (s.234B(2)).
        r = compute({"regime": "new",
                     "income": {"other_sources": {"other": 1_500_000}},
                     "taxes_paid": {"self_assessment": [
                         {"date": "2026-07-20", "amount": 109_200}]},
                     "due_date": "2026-09-15", "filing_date": "2026-09-10"})
        i = r["new"]["interest_and_fees"]
        self.assertEqual(i["234B"], 4_368)
        self.assertEqual(i["234A"], 0)

    def test_presumptive_only_single_march_installment(self):
        # Presumptive 20L only (tax 2,08,000), 100% advance paid 10-Mar:
        # fully compliant under the single 15-Mar installment rule -> no 234B/C
        r = compute({"regime": "new",
                     "income": {"business_presumptive_income": 2_000_000, "presumptive_section": "44AD"},
                     "taxes_paid": {"advance_tax": [
                         {"date": "2026-03-10", "amount": 208_000}]},
                     "due_date": "2026-08-31", "filing_date": "2026-08-30"})
        i = r["new"]["interest_and_fees"]
        self.assertEqual(i["234B"], 0)
        self.assertEqual(i["234C"], 0)

    def test_234a_one_month_when_due_date_is_month_end(self):
        # Due 30-Nov, filed 31-Dec: the period 1-Dec..31-Dec is exactly one
        # month -> 1% once on 1,09,200 = 1,092 (day-of-month comparison must
        # not double-count month-end)
        r = compute({"regime": "new",
                     "income": {"other_sources": {"other": 1_500_000}},
                     "due_date": "2026-11-30", "filing_date": "2026-12-31"})
        self.assertEqual(r["new"]["interest_and_fees"]["234A"], 1_092)

    def test_final_payable_rounded_to_10_288b(self):
        # Liability 1,09,200, TDS 1,00,013 -> raw net 9,187, s.288B -> 9,190
        r = compute({"regime": "new",
                     "income": {"other_sources": {"other": 1_500_000}},
                     "taxes_paid": {"tds": 100_013},
                     "due_date": "2026-09-15", "filing_date": "2026-07-31"})
        self.assertEqual(r["new"]["interest_and_fees"]["final_payable_or_refund"], 9_190)

    def test_senior_no_business_exempt_from_234bc(self):
        # s.207(2): resident senior with no business income owes no advance tax
        r = compute({"age_category": "senior", "regime": "old",
                     "income": {"other_sources": {"fd_interest": 1_500_000}},
                     "due_date": "2026-07-31", "filing_date": "2026-07-30"})
        i = r["old"]["interest_and_fees"]
        self.assertEqual(i["234B"], 0)
        self.assertEqual(i["234C"], 0)

    def test_no_234f_below_basic_exemption(self):
        # Total income under 4L (new regime basic exemption) filed late -> no fee
        r = compute({"regime": "new",
                     "income": {"other_sources": {"other": 350_000}},
                     "due_date": "2026-07-31", "filing_date": "2026-09-01"})
        self.assertEqual(r["new"]["interest_and_fees"]["234F"], 0)

    def test_no_234bc_when_tds_covers(self):
        r = compute({"regime": "new",
                     "income": {"salary": {"gross": 2_500_000}},
                     "taxes_paid": {"tds": 319_800},
                     "due_date": "2026-09-15", "filing_date": "2026-07-31"})
        i = r["new"]["interest_and_fees"]
        self.assertEqual(i["234B"], 0)
        self.assertEqual(i["234C"], 0)
        self.assertEqual(i["final_payable_or_refund"], 0)


class TestStructure(unittest.TestCase):
    def test_comparison_present_and_consistent(self):
        r = compute({"income": {"salary": {"gross": 1_800_000}},
                     "deductions": {"80c": 150_000, "80d": 25_000}})
        c = r["comparison"]
        self.assertIn(c["recommended_regime"], ("new", "old"))
        self.assertEqual(c["savings"], abs(c["new_total"] - c["old_total"]))

    def test_total_income_rounded_to_10(self):
        r = compute({"income": {"other_sources": {"other": 512_344}}})
        self.assertEqual(r["new"]["total_income"] % 10, 0)


class TestSurchargeTiers(unittest.TestCase):
    """First Schedule Part III Para A: the 25%/37% tiers are tested on total
    income EXCLUDING dividend and s.111A/112/112A income; when only the
    inclusive figure crosses 2cr, clause (e) applies a flat 15%."""

    def test_flat_15_when_cg_pushes_past_2cr(self):
        # Slab 1.5cr (salary 1,50,75,000) + 112A 1cr. Exclusive income 1.5cr
        # <= 2cr -> clause (e): 15% on ALL tax, not 25% on the slab part.
        # Slab tax 40,80,000 + 112A tax 12,34,375 = 53,14,375; surcharge 15%
        # = 7,97,156.25; cess 4% -> 63,55,992.5 -> r10 = 63,55,990.
        r = compute({"regime": "new", "income": {
            "salary": {"gross": 15_075_000},
            "capital_gains": {"ltcg_112a": 10_000_000}}, "filing_date": "2026-07-20"})
        t = r["new"]["tax"]
        self.assertEqual(t["surcharge_rate"], 0.15)
        self.assertEqual(new_liab(r), 6_355_990)

    def test_25pct_when_exclusive_income_past_2cr(self):
        # Slab 2.5cr + 112A 1cr: exclusive 2.5cr > 2cr -> 25% on slab tax
        # (70,80,000 -> 17,70,000) but 15% on the 112A tax (12,34,375 ->
        # 1,85,156.25). Cess 4% -> 1,06,80,312.5 -> r10 = 1,06,80,310.
        r = compute({"regime": "new", "income": {
            "salary": {"gross": 25_075_000},
            "capital_gains": {"ltcg_112a": 10_000_000}}, "filing_date": "2026-07-20"})
        t = r["new"]["tax"]
        self.assertEqual(t["surcharge_rate"], 0.25)
        self.assertEqual(new_liab(r), 10_680_310)

    def test_marginal_relief_at_2cr_exclusive(self):
        # Pure salary, slab 2,00,10,000: 25% tier by 10,000. Benchmark at the
        # threshold: slab_tax(2cr) = 55,80,000 at the flat 15% below-rate ->
        # 64,17,000, plus the 10,000 excess. Actual 55,83,000 * 1.25 =
        # 69,78,750 -> relief 5,51,750; capped total 64,27,000; cess ->
        # 66,84,080.
        r = compute({"regime": "new", "income": {"salary": {"gross": 20_085_000}},
                     "filing_date": "2026-07-20"})
        t = r["new"]["tax"]
        self.assertEqual(t["surcharge_marginal_relief"], 551_750)
        self.assertEqual(new_liab(r), 6_684_080)


class TestSetoffAndAbsorption(unittest.TestCase):
    def test_basic_exemption_prefers_112a_when_rebate_in_play(self):
        # Old regime: FD 2L (slab), 111A 50k, 112A 1.75L. TI 4.25L <= 5L.
        # Absorbing the rebate-INELIGIBLE 112A taxable (50k) with the unused
        # 50k basic exemption leaves 10,000 of 111A tax, wiped by the 12,500
        # rebate -> 0. (111A-first would leave 6,250 of 112A tax standing.)
        r = compute({"regime": "old", "income": {
            "other_sources": {"fd_interest": 200_000},
            "capital_gains": {"stcg_111a": 50_000, "ltcg_112a": 175_000}},
            "filing_date": "2026-07-20"})
        self.assertEqual(old_liab(r), 0)

    def test_basic_exemption_prefers_111a_when_rebate_capacity_short(self):
        # Old regime: 111A 3L + 112A 2L, nothing else. TI 5L. Absorbing 111A
        # first (2.5L) leaves 111A tax 10,000 (rebate-covered) + 112A taxable
        # 75k -> 9,375 tax -> 9,750 with cess. 112A-first would cost 12,500 +
        # cess. The engine must pick the cheaper order per composition.
        r = compute({"regime": "old", "income": {
            "capital_gains": {"stcg_111a": 300_000, "ltcg_112a": 200_000}},
            "filing_date": "2026-07-20"})
        self.assertEqual(old_liab(r), 9_750)

    def test_hp_loss_sets_off_against_gross_112a_gain(self):
        # s.71 works at the income stage: HP loss 1L sets off against the FULL
        # 2L 112A gain (not the post-exemption 75k), so TI = 1,00,000, the
        # 1.25L exemption then covers the net gain, tax 0, and NO carry-forward
        # remains.
        r = compute({"regime": "old", "income": {
            "house_property": [{"type": "let_out", "rent_received": 0,
                                "interest_paid": 100_000}],
            "capital_gains": {"ltcg_112a": 200_000}}, "filing_date": "2026-07-20"})
        c = r["old"]
        self.assertEqual(c["total_income"], 100_000)
        self.assertEqual(old_liab(r), 0)
        self.assertFalse(any("could not be set off" in w for w in c["warnings"]))


class TestCoverageAdditions(unittest.TestCase):
    def test_retirement_exemption_survives_new_regime(self):
        # Gross 20L incl. 5L exempt leave encashment (s.10(10AA)): slab
        # 20L - 5L - 75k = 14.25L -> tax 93,750 -> 97,500 with cess.
        r = compute({"regime": "new", "income": {
            "salary": {"gross": 2_000_000, "exempt_retirement": 500_000}},
            "filing_date": "2026-07-20"})
        self.assertEqual(new_liab(r), 97_500)

    def test_winnings_count_toward_rebate_income_threshold(self):
        # Total income 13L. Slab tax 60k + winnings tax 30k is less than
        # the 1L excess: no marginal relief; 90,000 * 1.04 = 93,600.
        r = compute({"regime": "new", "income": {
            "salary": {"gross": 1_275_000},
            "other_sources": {"winnings": 100_000}}, "filing_date": "2026-07-20"})
        t = r["new"]["tax"]
        self.assertEqual(t["rebate_87a"], 0)
        self.assertEqual(new_liab(r), 93_600)

    def test_family_pension_57iia_deduction(self):
        # 90k family pension: 1/3 = 30k, capped 25k new / 15k old ->
        # TI 65,000 / 75,000 (both under the exemption, tax 0).
        r = compute({"income": {"other_sources": {"family_pension": 90_000}},
                     "filing_date": "2026-07-20"})
        self.assertEqual(r["new"]["total_income"], 65_000)
        self.assertEqual(r["old"]["total_income"], 75_000)

    def test_relief_89_nets_after_cess(self):
        # Liability 1,92,400 (salary 20L new regime) minus 30k s.89 relief.
        r = compute({"regime": "new", "income": {"salary": {"gross": 2_000_000}},
                     "relief_89": 30_000, "filing_date": "2026-07-20"})
        self.assertEqual(new_liab(r), 162_400)

    def test_relief_89_cannot_go_negative(self):
        r = compute({"regime": "new", "income": {"salary": {"gross": 2_000_000}},
                     "relief_89": 10_000_000, "filing_date": "2026-07-20"})
        self.assertEqual(new_liab(r), 0)

    def test_24b_and_112_warnings_present(self):
        r = compute({"regime": "old", "income": {
            "salary": {"gross": 2_000_000},
            "house_property": [{"type": "self_occupied", "interest_paid": 150_000}],
            "capital_gains": {"ltcg_other": 500_000}}, "filing_date": "2026-07-20"})
        w = r["old"]["warnings"]
        self.assertTrue(any("s.24(b)" in x and "30,000" in x for x in w))
        self.assertTrue(any("indexed gain" in x.lower() for x in w))


class TestIncomeYearsAndAdvanceTax(unittest.TestCase):
    def estimate(self, fy="2026-27", as_of="2026-12-10", **fields):
        inp = {"financial_year": fy, "purpose": "advance_tax", "as_of_date": as_of,
               "regime": "new", "income": {"other_sources": {"other": 2_000_000}},
               "expected_tax_credits": {"tds": 8_000}}
        inp.update(fields)
        return compute(inp)

    def test_december_target_nets_expected_credits_and_paid_challans(self):
        # 20L income: tax 2L + 4% = 208,000. Annual TDS 8,000 leaves
        # 200,000; December 75% = 150,000, less 90,000 paid = 60,000.
        r = self.estimate(taxes_paid={"tds": 4_000, "advance_tax": [
            {"date": "2026-06-15", "amount": 30_000},
            {"date": "2026-09-15", "amount": 60_000}]})
        p = r["new"]["advance_tax"]
        self.assertEqual(p["annual_tax_liability"], 208_000)
        self.assertEqual(p["net_advance_tax_liability"], 200_000)
        self.assertEqual([s["cumulative_required"] for s in p["schedule"]],
                         [30_000, 90_000, 150_000, 200_000])
        self.assertEqual(p["next_payment"], {"due_date": "2026-12-15", "amount": 60_000,
                                              "kind": "instalment"})
        self.assertEqual(p["annual_remaining"], 110_000)
        self.assertNotIn("interest_and_fees", r["new"])

    def test_same_rates_for_both_years_without_global_state_leak(self):
        for fy, as_of in (("2025-26", "2025-12-10"), ("2026-27", "2026-12-10"),
                          ("2025-26", "2025-12-10")):
            r = self.estimate(fy, as_of)
            self.assertEqual(r["fy"], fy)
            self.assertEqual(new_liab(r), 208_000)
            self.assertEqual(r["new"]["advance_tax"]["next_payment"]["due_date"],
                             as_of[:4] + "-12-15")

    def test_shared_rate_goldens_in_each_year(self):
        # Independent expected values also used by the original golden suite.
        # Income descriptions retain raw values; no engine result is the oracle.
        cases = [
            ({"income": {"salary": {"gross": 1_275_000}}}, "new", 0),
            ({"income": {"salary": {"gross": 2_500_000}}}, "new", 319_800),
            ({"income": {"other_sources": {"other": 1_210_000}}}, "new", 10_400),
            ({"income": {"salary": {"gross": 6_000_000}}}, "new", 1_552_980),
            ({"income": {"capital_gains": {"ltcg_112a": 5_000_010}}}, "new", 581_760),
            ({"income": {"capital_gains": {"vda": 300_000}}}, "new", 93_600),
            ({"income": {"salary": {"gross": 1_000_000}}, "deductions": {"80c": 150_000}}, "old", 75_400),
            ({"age_category": "senior", "income": {"other_sources": {"fd_interest": 600_000}}}, "old", 20_800),
            ({"income": {"salary": {"gross": 2_000_000}}, "relief_89": 30_000}, "new", 162_400),
            ({"income": {"salary": {"gross": 2_000_000},
                         "house_property": [{"type": "self_occupied", "interest_paid": 250_000}]}}, "old", 351_000),
        ]
        for fy, day in (("2025-26", "2026-07-20"), ("2026-27", "2027-07-20")):
            for fields, regime, expected in cases:
                with self.subTest(fy=fy, fields=fields, regime=regime):
                    r = compute(dict(fields, financial_year=fy, filing_date=day, regime=regime))
                    self.assertEqual(r[regime]["tax"]["total_tax_liability"], expected)

    def test_march_final_instalment(self):
        p = self.estimate(as_of="2027-03-15")["new"]["advance_tax"]
        self.assertEqual(p["next_payment"], {"due_date": "2027-03-15", "amount": 200_000,
                                              "kind": "instalment"})

    def test_after_march_instalment_is_year_end_top_up(self):
        p = self.estimate(as_of="2027-03-16")["new"]["advance_tax"]
        self.assertEqual(p["next_payment"], {"due_date": "2027-03-31", "amount": 200_000,
                                              "kind": "year_end_top_up"})

    def test_paid_on_deadline_counts(self):
        p = self.estimate(as_of="2026-12-15", taxes_paid={"advance_tax": [
            {"date": "2026-12-15", "amount": 150_000}]})["new"]["advance_tax"]
        self.assertEqual(p["schedule"][2]["shortfall_at_deadline"], 0)
        self.assertEqual(p["next_payment"]["amount"], 50_000)
        self.assertEqual(p["next_payment"]["due_date"], "2027-03-15")

    def test_late_paid_amount_counts_for_next_payment_but_not_past_deadline(self):
        p = self.estimate(taxes_paid={"advance_tax": [
            {"date": "2026-10-01", "amount": 100_000}]})["new"]["advance_tax"]
        self.assertEqual(p["schedule"][1]["paid_by_deadline"], 0)
        self.assertEqual(p["schedule"][1]["shortfall_at_deadline"], 90_000)
        self.assertEqual(p["schedule"][1]["outstanding_now"], 0)
        self.assertEqual(p["next_payment"]["amount"], 50_000)

    def test_presumptive_with_interest_uses_single_march_instalment(self):
        for fy, as_of, march in (("2025-26", "2025-12-10", "2026-03-15"),
                                ("2026-27", "2026-12-10", "2027-03-15")):
            r = self.estimate(fy, as_of, expected_tax_credits={}, income={
                "business_presumptive_income": 2_000_000, "presumptive_section": "44ADA",
                "other_sources": {"fd_interest": 100_000}})
            p = r["new"]["advance_tax"]
            # 21L: tax 225,000 * 1.04 = 234,000, entirely due in March.
            self.assertEqual(p["annual_tax_liability"], 234_000)
            self.assertEqual(len(p["schedule"]), 1)
            self.assertEqual(p["next_payment"]["due_date"], march)
            self.assertEqual(p["next_payment"]["amount"], 234_000)

    def test_senior_without_business_exempt(self):
        for age in ("senior", "super_senior"):
            p = self.estimate(age_category=age)["new"]["advance_tax"]
            self.assertTrue(p["senior_exempt"])
            self.assertEqual(p["schedule"], [])
            self.assertIsNone(p["next_payment"])

    def test_senior_with_presumptive_business_not_exempt(self):
        p = self.estimate(age_category="senior", income={
            "business_presumptive_income": 2_000_000, "presumptive_section": "44AD"})["new"]["advance_tax"]
        self.assertFalse(p["senior_exempt"])
        self.assertEqual(len(p["schedule"]), 1)

    def test_ten_thousand_threshold(self):
        for credit, required in ((198_010, False), (198_000, True)):
            p = self.estimate(expected_tax_credits={"tds": credit})["new"]["advance_tax"]
            self.assertEqual(p["advance_tax_required"], required)

    def test_full_withholding_and_overpayments_never_suggest_negative_payment(self):
        p = self.estimate(expected_tax_credits={"tds": 300_000})["new"]["advance_tax"]
        self.assertFalse(p["advance_tax_required"])
        p = self.estimate(taxes_paid={"advance_tax": [
            {"date": "2026-10-01", "amount": 300_000}]})["new"]["advance_tax"]
        self.assertIsNone(p["next_payment"])
        self.assertEqual(p["annual_remaining"], 0)

    def test_new_act_labels_and_legacy_output_keys(self):
        r = self.estimate(income={"capital_gains": {"stcg_111a": 500_000,
                              "ltcg_112a": 500_000, "vda": 10_000},
                              "other_sources": {"winnings": 10_000}})
        self.assertIsNone(r["ay"])
        self.assertEqual(r["tax_year"], "2026-27")
        self.assertEqual(r["sections"]["round_tax"], "516")
        sections = [s["section"] for s in r["new"]["tax"]["special"]]
        self.assertEqual(sections, ["s.196 STCG (equity)", "s.198 LTCG (equity)",
                                   "s.194(1), Table 4 VDA/crypto", "s.194(1), Tables 1/5 winnings"])
        self.assertIn("rebate_87a", r["new"]["tax"])

    def test_new_act_warning_translation_preserves_rupee_amounts(self):
        r = self.estimate(relief_89=89, income={"capital_gains": {"ltcg_other": 500_000}})
        warnings = r["new"]["warnings"]
        self.assertTrue(any("s.157 of 89 applied" in w for w in warnings), warnings)
        self.assertTrue(any("s.197" in w for w in warnings), warnings)
        self.assertEqual(r["new"]["tax"]["special"][0]["section"], "s.197 LTCG (other)")

    def test_special_income_marginal_relief_is_limited_to_slab_tax(self):
        # TI 12.5L: 6L slab tax 10k + 6.5L STCG tax 130k. Excess 50k;
        # nominal relief 90k is capped at slab tax 10k: 130k * 1.04 = 135,200.
        for fy, day in (("2025-26", "2026-07-20"), ("2026-27", "2027-07-20")):
            r = compute({"financial_year": fy, "regime": "new", "filing_date": day,
                         "income": {"other_sources": {"other": 600_000},
                                    "capital_gains": {"stcg_111a": 650_000}}})
            self.assertEqual(r["new"]["tax"]["marginal_relief_87a"], 10_000)
            self.assertEqual(new_liab(r), 135_200)

    def test_exempt_equity_gain_still_counts_for_rebate_threshold(self):
        # 12L slab + 1.25L exempt CG: TI 13.25L exceeds 12L; slab tax
        # 60k has no marginal relief against 1.25L excess: 62,400 with cess.
        r = self.estimate(income={"other_sources": {"other": 1_200_000},
                                 "capital_gains": {"ltcg_112a": 125_000}})
        self.assertEqual(new_liab(r), 62_400)

    def test_professional_tax_is_actual_paid_not_an_invented_cap(self):
        # 10L salary - 50k standard - 6k paid = 944k. Tax 12,500 +
        # (944k - 500k)*20% = 101,300, with cess = 105,350 rounded.
        for fy, day in (("2025-26", "2026-07-20"), ("2026-27", "2027-07-20")):
            r = compute({"financial_year": fy, "regime": "old", "filing_date": day,
                         "income": {"salary": {"gross": 1_000_000, "professional_tax": 6_000}}})
            self.assertEqual(old_liab(r), 105_350)

    def test_new_year_return_dates_and_interest(self):
        # 208k tax, no prepayments: late filing Aug5 gives 423=2080,
        # 424=5*2080=10400, 425=208000*(.15*3+.45*3+.75*3+1)*1%
        # =10504 and fee=5000.
        r = compute({"financial_year": "2026-27", "regime": "new",
                     "income": {"other_sources": {"other": 2_000_000}},
                     "filing_date": "2027-08-05"})
        i = r["new"]["interest_and_fees"]
        self.assertEqual([i[k] for k in ("234A", "234B", "234C", "234F")],
                         [2_080, 10_400, 10_504, 5_000])

    def test_mixed_presumptive_return_interest_uses_march_only(self):
        r = compute({"financial_year": "2026-27", "regime": "new",
                     "income": {"business_presumptive_income": 2_000_000, "presumptive_section": "44ADA",
                                "other_sources": {"fd_interest": 100_000}},
                     "filing_date": "2027-08-20"})
        i = r["new"]["interest_and_fees"]
        self.assertEqual(i["234A"], 0)
        self.assertEqual(i["234F"], 0)
        self.assertEqual(i["234C"], 2_340)

    def test_legacy_omission_keeps_year_and_warns(self):
        r = compute({"income": {}, "filing_date": "2026-07-20"})
        self.assertEqual(r["fy"], "2025-26")
        self.assertEqual(r["ay"], "2026-27")
        self.assertTrue(any("financial_year omitted" in w for w in r["new"]["warnings"]))

    def test_unsupported_year_and_invalid_context_fail_closed(self):
        cases = [{"financial_year": "2024-25"}, {"financial_year": []},
                 {"purpose": "estimate"}, {"purpose": "advance_tax", "as_of_date": "2025-12-10"},
                 {"financial_year": "2026-27", "filing_date": "2026-12-10"}]
        for inp in cases:
            with self.subTest(inp=inp), self.assertRaises(ValueError):
                compute(inp)

    def test_planning_refuses_future_challans_and_self_assessment(self):
        for field, payment in (("advance_tax", {"date": "2027-03-15", "amount": 50_000}),
                               ("self_assessment", {"date": "2026-12-01", "amount": 50_000})):
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.estimate(taxes_paid={field: [payment]})


class TestReviewRegressions(unittest.TestCase):
    def test_lost_rebate_also_increases_surcharge(self):
        # Slab tax 60,000 + VDA tax 18,000,000; 25% surcharge and 4% cess.
        for fy, filing in (("2025-26", "2026-07-20"), ("2026-27", "2027-07-20")):
            r = compute({"financial_year": fy, "filing_date": filing, "regime": "new",
                         "income": {"salary": {"gross": 1_275_000},
                                    "capital_gains": {"vda": 60_000_000}}})
            self.assertEqual(new_liab(r), 23_478_000)
            self.assertEqual(r["new"]["tax"]["rebate_87a"], 0)

    def test_year_end_top_up_rounds_remaining_balance_once(self):
        r = compute({"financial_year": "2026-27", "purpose": "advance_tax", "regime": "old",
                     "as_of_date": "2027-03-31", "expected_tax_credits": {"tds": 759_336},
                     "income": {"other_sources": {"other": 3_648_831}},
                     "taxes_paid": {"advance_tax": [{"date": "2027-03-16", "amount": 52_206}]}})
        # 943,440 annual tax - 759,336 TDS - 52,206 paid = 131,898, rounded once.
        plan = r["old"]["advance_tax"]
        self.assertEqual(plan["annual_remaining"], 131_900)
        self.assertEqual(plan["next_payment"]["amount"], 131_900)

    def test_partial_special_rate_relief_and_old_rebate(self):
        for fy, filing in (("2025-26", "2026-07-20"), ("2026-27", "2027-07-20")):
            r = compute({"financial_year": fy, "filing_date": filing,
                         "income": {"other_sources": {"other": 1_100_000},
                                    "capital_gains": {"stcg_111a": 100_010}}})
            self.assertEqual(new_liab(r), 20_800)
            self.assertEqual(r["new"]["tax"]["marginal_relief_87a"], 50_000)
            r = compute({"financial_year": fy, "filing_date": filing,
                         "income": {"other_sources": {"other": 300_000},
                                    "capital_gains": {"stcg_111a": 150_000}}})
            self.assertEqual(old_liab(r), 20_800)
            self.assertEqual(r["old"]["tax"]["rebate_87a"], 12_500)

    def test_super_senior_new_year_old_regime(self):
        r = compute({"financial_year": "2026-27", "filing_date": "2027-07-20",
                     "age_category": "super_senior", "income": {"other_sources": {"fd_interest": 1_000_000}}})
        self.assertEqual(old_liab(r), 93_600)
        self.assertTrue(any("s.403(3)" in s for s in r["old"]["interest_and_fees"]["assumptions"]))

    def test_business_august_due_date_both_years(self):
        for fy, year in (("2025-26", 2026), ("2026-27", 2027)):
            inp = {"financial_year": fy, "income": {"business_presumptive_income": 2_000_000,
                                                     "presumptive_section": "44AD"}}
            for day, late in (("08-15", False), ("09-05", True)):
                r = compute(dict(inp, filing_date=f"{year}-{day}"))["new"]["interest_and_fees"]
                self.assertEqual(r["234F"], 5_000 if late else 0)
                self.assertEqual(r["234A"], 2_080 if late else 0)

    def test_missing_filing_date_agrees_with_validator(self):
        from validate_income import check
        inp = {"financial_year": "2026-27"}
        for today, allowed in ((date(2026, 10, 4), False), (date(2027, 3, 31), False),
                               (date(2027, 4, 1), True), (date(2027, 12, 31), True),
                               (date(2028, 1, 1), False)):
            errors, _ = check(inp, today=today)
            self.assertEqual(not errors, allowed)
            if allowed:
                compute(inp, today=today)
            else:
                with self.assertRaisesRegex(ValueError, "filing_date"):
                    compute(inp, today=today)

    def test_belated_cutoff_both_years(self):
        for fy, year in (("2025-26", 2026), ("2026-27", 2027)):
            compute({"financial_year": fy, "filing_date": f"{year}-12-31"})
            with self.assertRaisesRegex(ValueError, "window has closed"):
                compute({"financial_year": fy, "filing_date": f"{year + 1}-01-01"})

    def test_explicit_presumptive_gate(self):
        inp = {"financial_year": "2026-27", "purpose": "advance_tax", "as_of_date": "2026-12-10",
               "income": {"business_presumptive_income": 2_000_000}}
        self.assertEqual(len(compute(inp)["new"]["advance_tax"]["schedule"]), 4)
        for section in ("44AD", "44ADA"):
            inp["income"]["presumptive_section"] = section
            self.assertEqual(len(compute(inp)["new"]["advance_tax"]["schedule"]), 1)
        inp["income"]["presumptive_section"] = "44AE"
        with self.assertRaisesRegex(ValueError, "44AE is unsupported"):
            compute(inp)

    def test_new_year_warning_labels_are_explicit(self):
        import re
        inp = {"financial_year": "2026-27", "filing_date": "2027-09-01",
               "income": {"salary": {"gross": 2_000_000, "professional_tax": 6_000, "basic_plus_da": 100_000},
                          "house_property": [{"type": "self_occupied", "interest_paid": 300_000}],
                          "capital_gains": {"ltcg_other": 100_000}, "other_sources": {"family_pension": 90_000}},
               "deductions": {"80c": 200_000, "80ccd_2": 90_000, "80tta_ttb": 10_000, "80g": 5_000},
               "relief_89": 89}
        r = compute(inp)
        warnings = " ".join(w for rk in ("old", "new") for w in r[rk]["warnings"])
        self.assertIn("s.197(3)", warnings)
        self.assertIn("s.22(2)", warnings)
        self.assertIn("s.157 of 89", warnings)
        self.assertIn("deposit interest, donations", warnings)
        self.assertIsNone(re.search(r"87A|80TTA|80G|153_TTB|115BAC|s\.112|s\.24|s\.57", warnings))

    def test_gain_warning_and_legacy_fixture(self):
        import json
        from pathlib import Path
        for fy, filing, section in (("2025-26", "2026-07-20", "s.87A"), ("2026-27", "2027-07-20", "s.156")):
            r = compute({"financial_year": fy, "filing_date": filing, "income": {
                "salary": {"gross": 1_275_000}, "capital_gains": {"ltcg_112a": 100_000}}})
            self.assertEqual(new_liab(r), 62_400)
            self.assertTrue(any(section in w and "special-rate income" in w for w in r["new"]["warnings"]))
        inp = json.loads((Path(__file__).parent.parent / "assets/example-income.json").read_text())
        inp.pop("financial_year")
        self.assertEqual(compute(inp)["new"]["interest_and_fees"]["final_payable_or_refund"], 720)

    def test_fuzz_oracle_detects_coherent_wrong_plan(self):
        import copy
        from fuzz_engine import advance_plan_errors
        inp = {"financial_year": "2026-27", "purpose": "advance_tax", "as_of_date": "2026-12-10",
               "income": {"other_sources": {"other": 2_000_000}}, "expected_tax_credits": {"tds": 8_000},
               "taxes_paid": {"advance_tax": [{"date": "2026-10-01", "amount": 100_000}]}}
        plan = compute(inp)["new"]["advance_tax"]
        self.assertEqual(advance_plan_errors(inp, 208_000, plan), [])
        for key in ("expected_tds_tcs", "net_advance_tax_liability", "advance_tax_paid",
                    "annual_remaining", "schedule", "next_payment", "senior_exempt"):
            wrong = copy.deepcopy(plan)
            wrong[key] = None
            self.assertIn(key, advance_plan_errors(inp, 208_000, wrong))


if __name__ == "__main__":
    unittest.main()
