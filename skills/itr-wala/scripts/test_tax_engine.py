"""Golden tests for tax_engine.py - every expected value hand-derived from
FY 2025-26 (AY 2026-27) rules. Run: python3 -m unittest test_tax_engine -v
"""

import unittest

from tax_engine import compute


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

    def test_rebate_survives_ltcg_but_ltcg_still_taxed(self):
        # Salary 12.75L (slab 12L) + LTCG 112A 2L. FY 2025-26 rule: the 12L
        # 87A threshold tests SLAB income only, so the rebate survives
        # (slab tax 60000 -> 0), but LTCG gets no rebate:
        # 12.5%*(200000-125000) = 9375 -> *1.04 = 9750
        r = compute({"income": {"salary": {"gross": 1_275_000},
                                "capital_gains": {"ltcg_112a": 200_000}}})
        self.assertEqual(new_liab(r), 9_750)

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
                     "income": {"business_presumptive_income": 2_000_000},
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

    def test_winnings_flat_30_no_rebate_interaction(self):
        # Salary 12.75L -> slab 12L, rebate 60k holds; winnings 1L taxed flat
        # 30% (s.115BBJ) outside the slabs -> 30,000 + cess = 31,200.
        r = compute({"regime": "new", "income": {
            "salary": {"gross": 1_275_000},
            "other_sources": {"winnings": 100_000}}, "filing_date": "2026-07-20"})
        t = r["new"]["tax"]
        self.assertEqual(t["rebate_87a"], 60_000)
        self.assertEqual(new_liab(r), 31_200)

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


if __name__ == "__main__":
    unittest.main()
