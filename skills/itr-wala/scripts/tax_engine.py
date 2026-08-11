#!/usr/bin/env python3
"""Deterministic Indian income-tax engine for FY 2025-26 (AY 2026-27).

Resident individuals only. Computes tax under both the new (default) and old
regimes: slab tax, special-rate capital gains, VDA and lottery/online-game
winnings, 87A rebate with marginal relief, surcharge with marginal relief and
the 15% cap on capital-gains/dividend income, health & education cess, s.89
relief, interest under 234A/234B/234C and the 234F late-filing fee.

Zero dependencies (Python 3.9+ stdlib). All amounts are rupees (int/float).

Usage:
    python3 tax_engine.py input.json            # computation table, both regimes
    python3 tax_engine.py input.json --json     # machine-readable JSON
    echo '{...}' | python3 tax_engine.py -

The LLM driving this skill must NEVER do tax arithmetic itself. It prepares
the input JSON and reads the output. Every rupee figure comes from here.
"""

import itertools
import json
import sys
from datetime import date, timedelta

if sys.version_info < (3, 9):
    sys.exit("itr-wala needs Python 3.9 or newer (found %d.%d)." % sys.version_info[:2])

FY = "2025-26"
AY = "2026-27"

# ---------------------------------------------------------------------------
# FY 2025-26 (AY 2026-27) rule constants. One block per year; update annually.
# ---------------------------------------------------------------------------

NEW_REGIME = {
    "slabs": [  # (upper_bound, rate) - upper_bound None = no limit
        (400_000, 0.00),
        (800_000, 0.05),
        (1_200_000, 0.10),
        (1_600_000, 0.15),
        (2_000_000, 0.20),
        (2_400_000, 0.25),
        (None, 0.30),
    ],
    "standard_deduction": 75_000,
    "rebate_87a_limit": 1_200_000,   # taxable (slab-rate) income threshold
    "rebate_87a_max": 60_000,
    "basic_exemption": 400_000,
    "surcharge_cap": 0.25,           # 37% tier does not apply in new regime
    "nps_80ccd2_pct": 0.14,          # of basic + DA
}

OLD_REGIME = {
    # Basic exemption varies with age: <60 → 2.5L, 60-79 → 3L, 80+ → 5L
    "slabs_by_age": {
        "regular": [(250_000, 0.0), (500_000, 0.05), (1_000_000, 0.20), (None, 0.30)],
        "senior": [(300_000, 0.0), (500_000, 0.05), (1_000_000, 0.20), (None, 0.30)],
        "super_senior": [(500_000, 0.0), (1_000_000, 0.20), (None, 0.30)],
    },
    "standard_deduction": 50_000,
    "rebate_87a_limit": 500_000,
    "rebate_87a_max": 12_500,
    "surcharge_cap": 0.37,
    "nps_80ccd2_pct": 0.10,          # private-sector employer, old regime
}

# Special-rate incomes, FY 2025-26 (post Finance (No.2) Act 2024 rates)
RATE_STCG_111A = 0.20        # STT-paid equity/equity-MF short-term gains
RATE_LTCG_112A = 0.125       # STT-paid equity/equity-MF long-term gains
LTCG_112A_EXEMPT = 125_000   # first 1.25L of 112A gains exempt
RATE_LTCG_OTHER = 0.125      # s.112 (property etc., transfers on/after 23-Jul-2024)
RATE_VDA = 0.30              # s.115BBH crypto/VDA - no basic-exemption set-off, no 87A
RATE_WINNINGS = 0.30         # s.115BB lottery/game shows + s.115BBJ online games -
                             # same denials as VDA (TDS arrives u/s 194B/194BA)

# Surcharge (First Schedule, Part III, Paragraph A): 10% > 50L and 15% > 1cr
# are tested on TOTAL income; 25% > 2cr and 37% > 5cr are tested on total
# income EXCLUDING dividends and s.111A/112/112A income, with a flat-15%
# residual clause when only the inclusive figure crosses 2cr. Logic lives in
# compute_surcharge.
SURCHARGE_CAP_SPECIAL = 0.15  # ceiling on 111A/112A/112/dividend income surcharge
CESS_RATE = 0.04

# s.57(iia): family-pension deduction, one-third of the pension capped at
CAP_57IIA_NEW = 25_000        # new regime (Finance (No.2) Act 2024)
CAP_57IIA_OLD = 15_000        # old regime

# Chapter VI-A caps (old regime)
CAP_80C = 150_000
CAP_80CCD_1B = 50_000
CAP_80TTA = 10_000
CAP_80TTB = 50_000
CAP_HP_LOSS_SETOFF = 200_000  # s.71(3A)

# 234F late fee
FEE_234F_HIGH = 5_000
FEE_234F_LOW = 1_000          # if total income <= 5L
FEE_234F_INCOME_CUTOFF = 500_000

ADVANCE_TAX_MIN = 10_000      # below this net liability, no 234B/234C


def _r10(x):
    """Round to nearest 10 (s.288A/288B), half-up.

    Quantize to the paisa first: float residue (0.1 has no exact binary form)
    can leave a true half-point like 259025.0 at 259024.999...97, which would
    floor the wrong way and break monotonicity by 10 rupees (fuzzer-found)."""
    return int((round(x, 2) + 5) // 10 * 10)


def _floor100(x):
    """Rule 119A: interest base rounded down to a multiple of 100."""
    return int(round(x, 2) // 100) * 100


def _pos(x):
    return max(0.0, float(x or 0))


def slab_tax(income, slabs):
    tax, lower = 0.0, 0
    for upper, rate in slabs:
        if upper is None or income <= upper:
            tax += _pos(income - lower) * rate
            break
        tax += (upper - lower) * rate
        lower = upper
    return tax


# ---------------------------------------------------------------------------
# Heads of income
# ---------------------------------------------------------------------------

def compute_salary(inp, regime_key, warnings):
    sal = inp.get("income", {}).get("salary") or {}
    gross = _pos(sal.get("gross"))
    if gross == 0:
        return 0.0, {}
    # Retirement/terminal exemptions - gratuity s.10(10), commuted pension
    # s.10(10A), leave encashment s.10(10AA), retrenchment s.10(10B), VRS
    # s.10(10C) - survive the new regime (s.115BAC withdraws only 10(5)/
    # 10(13A)/most 10(14)/10(17)/10(32)), so they are exempt in BOTH regimes.
    retire = min(_pos(sal.get("exempt_retirement")), gross)
    exempt = _pos(sal.get("exempt_allowances")) if regime_key == "old" else 0.0
    if regime_key == "new" and _pos(sal.get("exempt_allowances")):
        warnings.append("New regime: HRA/LTA and other exempt allowances ignored (not "
                        "available). Retirement exemptions (gratuity, leave encashment, "
                        "commuted pension) stay exempt - those belong in "
                        "salary.exempt_retirement, applied in both regimes.")
    regime = OLD_REGIME if regime_key == "old" else NEW_REGIME
    std = min(regime["standard_deduction"], _pos(gross - retire - exempt))
    if regime_key == "new" and _pos(sal.get("professional_tax")):
        warnings.append("New regime: professional tax (s.16(iii)) not deductible - ignored.")
    ptax = min(_pos(sal.get("professional_tax")), 5_000) if regime_key == "old" else 0.0
    net = _pos(gross - retire - exempt - std - ptax)
    return net, {"gross": gross, "exempt_retirement": retire, "exempt_allowances": exempt,
                 "standard_deduction": std, "professional_tax": ptax, "net": net}


def compute_house_property(inp, regime_key, warnings):
    props = inp.get("income", {}).get("house_property") or []
    if isinstance(props, dict):
        props = [props]
    total, detail, warned_24b = 0.0, [], False
    for p in props:
        ptype = p.get("type", "self_occupied")
        interest = _pos(p.get("interest_paid"))
        if ptype == "self_occupied":
            if regime_key == "old":
                allowed = min(interest, 200_000)
                income = -allowed
                if interest > 30_000 and not warned_24b:
                    warned_24b = True
                    warnings.append("s.24(b): the 2,00,000 self-occupied cap assumes a loan "
                                    "taken on/after 1-Apr-1999 for purchase/construction "
                                    "completed within 5 years; for repair/renovation or "
                                    "pre-1999 loans the lawful cap is 30,000 - confirm the "
                                    "loan purpose before claiming.")
            else:
                income = 0.0
                if interest:
                    warnings.append("New regime: self-occupied home-loan interest (s.24b) not deductible - ignored.")
        else:  # let_out
            nav = _pos(p.get("rent_received")) - _pos(p.get("municipal_taxes"))
            # s.23(2)/s.24(a): municipal taxes are deductible only up to the
            # annual value - the NAV can never go negative. Taxes above the
            # rent (usually a transcription slip) must not manufacture a loss
            # that could then set off against other heads under s.71.
            if nav < 0:
                warnings.append("Municipal taxes exceed rent on a let-out property - "
                                "the s.24(a) deduction is limited to the annual value, "
                                "so NAV is taken as 0. Confirm the figures; municipal "
                                "taxes above rent are usually a transcription error.")
                nav = 0.0
            income = nav - 0.30 * nav - interest
        detail.append({"type": ptype, "income": round(income)})
        total += income
    if total < 0:
        if regime_key == "old":
            if total < -CAP_HP_LOSS_SETOFF:
                warnings.append("House-property loss capped at 2,00,000 for set-off (s.71(3A)); "
                                "balance carries forward (not tracked here).")
            total = max(total, -CAP_HP_LOSS_SETOFF)
        else:
            warnings.append("New regime: house-property loss cannot be set off against other heads - treated as 0; "
                            "carry-forward not tracked here.")
            total = 0.0
    return total, detail


def compute_capital_gains(inp):
    cg = inp.get("income", {}).get("capital_gains") or {}
    return {
        "stcg_111a": _pos(cg.get("stcg_111a")),
        "ltcg_112a": _pos(cg.get("ltcg_112a")),
        "ltcg_other": _pos(cg.get("ltcg_other")),
        "stcg_slab": _pos(cg.get("stcg_slab")),   # debt MFs, gold <holding period, etc.
        "vda": _pos(cg.get("vda")),
    }


def compute_other_sources(inp, regime_key, warnings):
    os_ = inp.get("income", {}).get("other_sources") or {}
    parts = {k: _pos(os_.get(k)) for k in ("savings_interest", "fd_interest", "dividends", "family_pension", "other")}
    # Winnings (lottery/game shows s.115BB, online games s.115BBJ) are
    # special-rate income, never slab income - kept out of "total".
    parts["winnings"] = _pos(os_.get("winnings"))
    fp_ded = 0.0
    if parts["family_pension"]:
        cap = CAP_57IIA_NEW if regime_key == "new" else CAP_57IIA_OLD
        fp_ded = min(parts["family_pension"] / 3.0, cap)
        warnings.append(f"Family pension: s.57(iia) deduction of {round(fp_ded):,} applied "
                        "(one-third of the pension, capped - available in both regimes).")
    parts["deduction_57iia"] = fp_ded
    parts["total"] = (parts["savings_interest"] + parts["fd_interest"] + parts["dividends"]
                      + parts["family_pension"] + parts["other"] - fp_ded)
    return parts


def allowed_deductions(inp, regime_key, heads, warnings):
    """Chapter VI-A. New regime: only employer NPS 80CCD(2) (+80JJAA, out of scope)."""
    d = inp.get("deductions") or {}
    out = {}
    ccd2 = _pos(d.get("80ccd_2"))
    basic = _pos(inp.get("income", {}).get("salary", {}).get("basic_plus_da"))
    if ccd2:
        pct = (NEW_REGIME if regime_key == "new" else OLD_REGIME)["nps_80ccd2_pct"]
        if basic and ccd2 > pct * basic:
            warnings.append(f"80CCD(2) capped at {int(pct*100)}% of basic+DA = {_r10(pct*basic):,}.")
            ccd2 = pct * basic
        out["80ccd_2"] = ccd2
    if regime_key == "new":
        skipped = [k for k in ("80c", "80ccd_1b", "80d", "80tta_ttb", "80g", "other")
                   if _pos(d.get(k)) > 0]
        if skipped:
            warnings.append("New regime: " + ", ".join(s.upper() for s in skipped)
                            + " not deductible - ignored (compare with old regime!).")
        return out

    age = inp.get("age_category", "regular")
    out["80c"] = min(_pos(d.get("80c")), CAP_80C)
    if _pos(d.get("80c")) > CAP_80C:
        warnings.append("80C capped at 1,50,000.")
    out["80ccd_1b"] = min(_pos(d.get("80ccd_1b")), CAP_80CCD_1B)
    out["80d"] = _pos(d.get("80d"))  # user supplies eligible amount; caps vary by family mix
    tta = _pos(d.get("80tta_ttb"))
    savings_int = heads["other_sources"]["savings_interest"]
    if age in ("senior", "super_senior"):
        eligible_base = savings_int + heads["other_sources"]["fd_interest"]
        out["80tta_ttb"] = min(tta if tta else eligible_base, CAP_80TTB, eligible_base)
    else:
        out["80tta_ttb"] = min(tta if tta else savings_int, CAP_80TTA, savings_int)
    out["80g"] = _pos(d.get("80g"))
    out["other"] = _pos(d.get("other"))
    return {k: v for k, v in out.items() if v}


# ---------------------------------------------------------------------------
# Core per-regime computation
# ---------------------------------------------------------------------------

def compute_regime(inp, regime_key):
    warnings = []
    age = inp.get("age_category", "regular")
    if regime_key == "new":
        slabs = NEW_REGIME["slabs"]
        basic_exemption = NEW_REGIME["basic_exemption"]
    else:
        slabs = OLD_REGIME["slabs_by_age"][age]
        basic_exemption = slabs[0][0]

    salary_net, salary_detail = compute_salary(inp, regime_key, warnings)
    hp_income, hp_detail = compute_house_property(inp, regime_key, warnings)
    cg = compute_capital_gains(inp)
    other = compute_other_sources(inp, regime_key, warnings)
    business = _pos(inp.get("income", {}).get("business_presumptive_income"))
    winnings = other["winnings"]

    if cg["ltcg_other"] > 0:
        warnings.append("s.112 LTCG taxed at 12.5% without indexation. For land/building "
                        "acquired on/before 22-Jul-2024, tax on that asset is capped at 20% "
                        "of the INDEXED gain (2nd proviso to s.112(1)(a)) - this engine "
                        "cannot apply that cap; if 20% of the indexed gain is lower, this "
                        "figure overstates the tax - use the offline utility or a CA for "
                        "that asset.")

    special_total = (cg["stcg_111a"] + cg["ltcg_112a"] + cg["ltcg_other"] + cg["vda"]
                     + winnings)
    slab_raw = salary_net + hp_income + cg["stcg_slab"] + other["total"] + business

    # s.71: house-property loss beyond the other slab heads sets off against
    # capital gains at the INCOME stage - so against the FULL 112A gain; the
    # 1.25L exemption (a tax-stage threshold, s.112A(2)) applies afterwards to
    # the net gain. Never against VDA or winnings (s.115BBH(2), s.58(4)); any
    # remainder carries forward (Schedule CFL - not tracked here).
    hp_residual = _pos(-slab_raw)
    slab_income_gross = _pos(slab_raw)

    rem = {"111a": cg["stcg_111a"], "112a": cg["ltcg_112a"], "112": cg["ltcg_other"]}
    setoff = 0.0
    if hp_residual > 0:
        for key in ("111a", "112a", "112"):  # highest-rate first
            room = hp_residual - setoff
            if room <= 0:
                break
            take = min(room, rem[key])
            rem[key] -= take
            setoff += take
        if setoff:
            warnings.append(f"House-property loss of {round(setoff):,} set off against "
                            "capital gains (s.71) - mirror this in Schedule CYLA.")
        if hp_residual - setoff > 0:
            warnings.append(f"House-property loss of {round(hp_residual - setoff):,} could "
                            "not be set off this year - carry-forward (Schedule CFL) is "
                            "not tracked here.")
    special_total_net = _pos(special_total - setoff)
    gti = slab_income_gross + special_total_net

    ded = allowed_deductions(inp, regime_key, {"other_sources": other}, warnings)
    ded_total = sum(ded.values())
    # Chapter VI-A cannot be set against special-rate CG/VDA income
    ded_total = min(ded_total, _pos(slab_income_gross))
    slab_income = _pos(slab_income_gross - ded_total)
    total_income = _r10(slab_income + special_total_net)

    unused_be0 = _pos(basic_exemption - slab_income)
    tax_slab = slab_tax(slab_income, slabs)

    def _with_absorption(order):
        """Absorb unused basic exemption into the special buckets in the given
        order (residents only; never VDA/winnings - s.115BBH, s.115BB), then
        compute special tax and the 87A rebate.

        New regime (Finance Act 2025): the 12L threshold is tested on income
        chargeable at SLAB rates (special-rate income excluded), and the rebate
        applies only against slab-rate tax. Old regime: threshold on total
        income; rebate covers all tax except 112A LTCG (s.112A(6)) and - safe
        posture - VDA/winnings. Thresholds are tested on s.288A-rounded
        figures (5,00,004 rounds to 5,00,000 and keeps the old-regime rebate).
        """
        t = {"111a": rem["111a"], "112a": _pos(rem["112a"] - LTCG_112A_EXEMPT),
             "112": rem["112"]}
        ube = unused_be0
        for key in order:
            if ube <= 0:
                break
            take = min(ube, t[key])
            t[key] -= take
            ube -= take
        specials = [
            {"section": "111A STCG (equity)", "income": cg["stcg_111a"], "in_ti": rem["111a"],
             "taxable": t["111a"], "rate": RATE_STCG_111A,
             "tax": t["111a"] * RATE_STCG_111A, "cap15": True},
            {"section": "112A LTCG (equity)", "income": cg["ltcg_112a"], "in_ti": rem["112a"],
             "taxable": t["112a"], "rate": RATE_LTCG_112A,
             "tax": t["112a"] * RATE_LTCG_112A, "cap15": True},
            {"section": "112 LTCG (other)", "income": cg["ltcg_other"], "in_ti": rem["112"],
             "taxable": t["112"], "rate": RATE_LTCG_OTHER,
             "tax": t["112"] * RATE_LTCG_OTHER, "cap15": True},
            {"section": "115BBH VDA/crypto", "income": cg["vda"], "in_ti": cg["vda"],
             "taxable": cg["vda"], "rate": RATE_VDA,
             "tax": cg["vda"] * RATE_VDA, "cap15": False},
            {"section": "115BB/BBJ winnings", "income": winnings, "in_ti": winnings,
             "taxable": winnings, "rate": RATE_WINNINGS,
             "tax": winnings * RATE_WINNINGS, "cap15": False},
        ]
        specials = [s for s in specials if s["income"] > 0]
        tax_special = sum(s["tax"] for s in specials)
        rebate, mr87a, notes = 0.0, 0.0, []
        if regime_key == "new":
            slab_r = _r10(slab_income)
            if slab_r <= NEW_REGIME["rebate_87a_limit"]:
                rebate = min(tax_slab, NEW_REGIME["rebate_87a_max"])
            else:
                excess = slab_r - NEW_REGIME["rebate_87a_limit"]
                if tax_slab > excess:  # marginal relief: pay no more than the excess
                    mr87a = tax_slab - excess
        else:
            if total_income <= OLD_REGIME["rebate_87a_limit"]:
                # The FA 2025 special-rate denial amended only the new-regime
                # proviso, so 111A/112 tax stays rebate-eligible here (Bombay
                # HC, ITAT Ahd) - though CPC and Circular 13/2025 disagree.
                tax_112a = sum(s["tax"] for s in specials
                               if s["section"].startswith("112A"))
                tax_no87a = sum(s["tax"] for s in specials
                                if s["section"].startswith(("115BBH", "115BB/")))
                rebate = min(_pos(tax_slab + tax_special - tax_112a - tax_no87a),
                             OLD_REGIME["rebate_87a_max"])
                if rebate and tax_no87a > 0:
                    notes.append("Old regime: 87A rebate NOT applied against VDA/winnings "
                                 "tax - the claim is arguable but unsupported, and the "
                                 "utility treats special-rate income as outside the rebate.")
                if rebate > tax_slab and (t["111a"] or t["112"]):
                    notes.append("Old regime: 87A rebate applied against s.111A/112 tax - "
                                 "statute and ITAT rulings support this, but CPC has disputed "
                                 "similar claims in processing (CBDT Circular 13/2025 takes "
                                 "the department's side); verify the portal accepts the "
                                 "figure before filing.")
        return {"specials": specials, "tax_special": tax_special, "rebate": rebate,
                "mr87a": mr87a, "notes": notes,
                "after": _pos(tax_slab + tax_special - rebate - mr87a)}

    # Basic-exemption absorption order: highest-rate-first is optimal in the
    # new regime, but in the old regime the 87A interaction (111A/112 tax is
    # rebate-eligible, 112A tax is not) means no fixed order is always best -
    # so try every order and keep the cheapest lawful outcome.
    chosen = _with_absorption(("111a", "112a", "112"))
    if regime_key == "old" and unused_be0 > 0:
        for order in itertools.permutations(("111a", "112a", "112")):
            cand = _with_absorption(order)
            if cand["after"] < chosen["after"] - 0.005:
                chosen = cand
    specials = chosen["specials"]
    tax_special = chosen["tax_special"]
    rebate = chosen["rebate"]
    marginal_relief_87a = chosen["mr87a"]
    warnings.extend(chosen["notes"])
    tax_after_rebate = chosen["after"]

    # --- Surcharge with 15% cap on special CG/dividend income and marginal relief ---
    surcharge, surcharge_relief, s_rate = compute_surcharge(
        regime_key, total_income, slab_income, tax_after_rebate, specials, other, slabs, warnings)

    cess = CESS_RATE * (tax_after_rebate + surcharge - surcharge_relief)
    pre_relief = tax_after_rebate + surcharge - surcharge_relief + cess
    # s.89(1) relief for salary arrears/advance - a transcribed figure from the
    # Form 10E computation, netted after cess (portal order). Also shrinks the
    # assessed tax that drives 234A/B/C (Explanation 1 to s.234B).
    relief_89 = min(_pos(inp.get("relief_89")), pre_relief)
    if relief_89:
        warnings.append(f"Relief u/s 89 of {round(relief_89):,} applied - Form 10E must be "
                        "e-filed BEFORE the return, or CPC disallows the relief and raises "
                        "a demand.")
    total_liability = _r10(_pos(pre_relief - relief_89))

    return {
        "regime": regime_key,
        "age_category": age,
        "basic_exemption": basic_exemption,
        "heads": {
            "salary": salary_detail,
            "house_property": {"income": round(hp_income), "properties": hp_detail},
            "capital_gains": cg,
            "other_sources": other,
            "business_presumptive": business,
        },
        "gross_total_income": _r10(gti),
        "deductions": {k: round(v) for k, v in ded.items()},
        "deductions_total": round(ded_total),
        "total_income": total_income,
        "tax": {
            "slab_income": round(slab_income),
            "slab_tax": round(tax_slab),
            "special": [{**{k: v for k, v in s.items() if k not in ("in_ti", "cap15")},
                         "tax": round(s["tax"])} for s in specials],
            "special_tax": round(tax_special),
            "rebate_87a": round(rebate),
            "marginal_relief_87a": round(marginal_relief_87a),
            "tax_after_rebate": round(tax_after_rebate),
            "surcharge_rate": s_rate,
            "surcharge": round(surcharge),
            "surcharge_marginal_relief": round(surcharge_relief),
            "cess": round(cess),
            "relief_89": round(relief_89),
            "total_tax_liability": total_liability,
        },
        "warnings": warnings,
    }


def compute_surcharge(regime_key, total_income, slab_income, tax_after_rebate,
                      specials, other, slabs, warnings):
    """First Schedule, Part III, Paragraph A (AY 2026-27).

    The 10% (>50L) and 15% (>1cr) tiers are tested on TOTAL income. The 25%
    (>2cr) and 37% (>5cr) tiers are tested on total income EXCLUDING dividends
    and s.111A/112/112A income (clauses (c)/(d)); when only the inclusive
    figure crosses 2cr, surcharge is a flat 15% on the whole tax (clause (e)).
    Tax on dividend/111A/112/112A income is never surcharged above 15%, and
    the new regime caps the top rate at 25% (s.115BAC(1A) proviso).
    """
    cap = (NEW_REGIME if regime_key == "new" else OLD_REGIME)["surcharge_cap"]
    dividends = other.get("dividends", 0.0)
    cg_in_ti = sum(s["in_ti"] for s in specials if s["cap15"])
    excl_income = _pos(total_income - dividends - cg_in_ti)

    T50, T1CR, T2CR, T5CR = 50_00_000, 1_00_00_000, 2_00_00_000, 5_00_00_000
    if total_income <= T50:
        return 0.0, 0.0, 0.0
    if excl_income > T5CR:
        rate, below_rate, threshold, measure = min(0.37, cap), 0.25, T5CR, "excl"
    elif excl_income > T2CR:
        rate, below_rate, threshold, measure = 0.25, 0.15, T2CR, "excl"
    elif total_income > T1CR:
        rate, below_rate, threshold, measure = 0.15, 0.10, T1CR, "total"
    else:
        rate, below_rate, threshold, measure = 0.10, 0.0, T50, "total"

    def _apply(slab_amt, cap15_amt, rest_amt, r):
        """Surcharged tax on a (slab, capped-special, other-special) split at
        main rate r, honouring the 15% ceiling on CG/dividend tax. Dividend
        sits in slab income; when r > 15% the top-slab-rate tax attributed to
        it moves into the capped bucket (approximation, warned below)."""
        d_at = (min(dividends * slabs[-1][1], slab_amt + rest_amt)
                if dividends and r > SURCHARGE_CAP_SPECIAL else 0.0)
        return ((slab_amt + rest_amt - d_at) * (1 + r)
                + (cap15_amt + d_at) * (1 + min(r, SURCHARGE_CAP_SPECIAL)))

    cg_tax = sum(s["tax"] for s in specials if s["cap15"])
    rest_tax = sum(s["tax"] for s in specials if not s["cap15"])
    slab_side_tax = _pos(tax_after_rebate - cg_tax - rest_tax)
    if dividends and rate > SURCHARGE_CAP_SPECIAL:
        warnings.append("Surcharge: dividend income attributed top-slab tax for the 15% surcharge cap "
                        "(approximation; verify for incomes above 2 crore).")
    surcharge = _apply(slab_side_tax, cg_tax, rest_tax, rate) - tax_after_rebate

    # Marginal relief: the extra (tax + surcharge) over the tax at the
    # threshold cannot exceed the income above the threshold. "Tax at the
    # threshold" is recomputed on THIS taxpayer's income mix: for the
    # total-income tiers every bucket shrinks proportionally; for the
    # exclusive-income tiers only the excluded-income side shrinks (slab
    # income net of dividends, VDA, winnings) while dividend/CG buckets -
    # which did not cause the tier - stay constant.
    if measure == "total":
        excess_income = total_income - threshold
        shrink = excess_income / total_income if total_income else 0.0
        slab_at_thr = slab_tax(slab_income * (1 - shrink), slabs)
        cap15_at_thr = sum(_pos(s["taxable"] - s["in_ti"] * shrink) * s["rate"]
                           for s in specials if s["cap15"])
        rest_at_thr = sum(_pos(s["taxable"] - s["in_ti"] * shrink) * s["rate"]
                          for s in specials if not s["cap15"])
    else:
        excess_income = excl_income - threshold
        shrink = excess_income / excl_income if excl_income else 0.0
        slab_excl = _pos(slab_income - dividends)
        slab_at_thr = slab_tax(slab_excl * (1 - shrink) + min(dividends, slab_income), slabs)
        cap15_at_thr = sum(s["taxable"] * s["rate"] for s in specials if s["cap15"])
        rest_at_thr = sum(_pos(s["taxable"] - s["in_ti"] * shrink) * s["rate"]
                          for s in specials if not s["cap15"])
    tax_at_thr = _apply(slab_at_thr, cap15_at_thr, rest_at_thr, below_rate)
    total_with_s = tax_after_rebate + surcharge
    if total_with_s > tax_at_thr + excess_income:
        relief = min(total_with_s - (tax_at_thr + excess_income), surcharge)
        if specials and slab_income > 0:
            warnings.append("Surcharge marginal relief computed on a proportional income mix "
                            "at the threshold - cross-check with the portal utility.")
        return surcharge, relief, rate
    return surcharge, 0.0, rate


# ---------------------------------------------------------------------------
# Interest (234A/B/C) and late fee (234F)
# ---------------------------------------------------------------------------

def _months_between(d1, d2):
    """Calendar months in the period starting the day AFTER d1 through d2,
    any part of a month counting as a full month (s.234A/B convention).
    E.g. due 30-Nov, filed 31-Dec -> the period 1-Dec..31-Dec is 1 month."""
    if d2 <= d1:
        return 0
    start = d1 + timedelta(days=1)
    months = (d2.year - start.year) * 12 + (d2.month - start.month)
    if d2.day >= start.day:
        months += 1
    return max(months, 1)


def compute_interest_and_fee(comp, inp):
    """234A/B/C + 234F. Simplified but deterministic; documented assumptions."""
    taxes = inp.get("taxes_paid") or {}
    tds = _pos(taxes.get("tds")) + _pos(taxes.get("tcs"))

    # AY 2026-27 due dates (Finance Act 2026 split): ITR-1/2 -> 2026-07-31,
    # non-audit ITR-3/4 -> 2026-08-31. Caller sets due_date per selected form.
    date_notes = []
    due = _parse_date(inp.get("due_date"))
    if due is None:
        state = "unparseable (use YYYY-MM-DD)" if inp.get("due_date") else "not provided"
        date_notes.append(f"due_date {state} - defaulted to 2026-07-31 (ITR-1/2); "
                          "non-audit ITR-3/4 filers must set 2026-08-31.")
        due = date(2026, 7, 31)
    filing = _parse_date(inp.get("filing_date"))
    if filing is None:
        state = "unparseable (use YYYY-MM-DD)" if inp.get("filing_date") else "not provided"
        date_notes.append(f"filing_date {state} - defaulted to today ({date.today()}).")
        filing = date.today()
    fy_start, fy_end = date(2025, 4, 1), date(2026, 3, 31)

    # Advance tax is only what was paid within the FY (s.211). Payments dated
    # outside the window (or undated) still count as tax paid, but for the
    # 234A/B/C tests they behave like self-assessment payments.
    advance_list, stray_advance = [], []
    for a in (taxes.get("advance_tax") or []):
        d = _parse_date(a.get("date"))
        (advance_list if d is not None and fy_start <= d <= fy_end
         else stray_advance).append(a)
    advance_total = sum(_pos(a.get("amount")) for a in advance_list)
    stray_total = sum(_pos(a.get("amount")) for a in stray_advance)
    if stray_total:
        date_notes.append(f"Advance-tax payments of {round(stray_total):,} dated outside "
                          "FY 2025-26 (or undated) treated as self-assessment payments "
                          "for interest purposes (s.211).")
    self_asmt_list = list(taxes.get("self_assessment") or []) + stray_advance
    self_asmt = sum(_pos(a.get("amount")) for a in self_asmt_list)
    # (date, amount) of every non-advance payment, undated ones at filing
    late_payments = sorted(
        ((_parse_date(a.get("date")) or filing, _pos(a.get("amount")))
         for a in self_asmt_list),
        key=lambda p: p[0])

    liability = comp["tax"]["total_tax_liability"]
    assessed_tax = _pos(liability - tds)  # for advance-tax purposes
    net_payable = liability - tds - advance_total - self_asmt

    out = {"234A": 0, "234B": 0, "234C": 0, "234F": 0,
           "assumptions": date_notes +
                          ["TDS treated as reducing advance-tax liability (s.209).",
                           "234C assumes no eligible capital-gains carve-outs "
                           "unless quarterly gains data provided."]}

    # Resident senior citizens with no business income owe no advance tax (s.207(2)).
    senior_exempt = (comp["age_category"] in ("senior", "super_senior")
                     and comp["heads"]["business_presumptive"] == 0)
    if senior_exempt:
        out["assumptions"].append("Senior citizen with no business income: "
                                  "no advance-tax liability, 234B/234C waived (s.207).")

    # 234F late fee (nil if total income is under the basic exemption limit)
    if filing > due and comp["total_income"] > comp["basic_exemption"]:
        out["234F"] = FEE_234F_LOW if comp["total_income"] <= FEE_234F_INCOME_CUTOFF else FEE_234F_HIGH

    # 234A: 1%/month on the unpaid balance from the day after the due date,
    # stopping on amounts discharged by later self-assessment payments.
    unpaid_at_due = _pos(liability - tds - advance_total -
                         sum(amt for pdate, amt in late_payments if pdate <= due))
    if filing > due and unpaid_at_due > 0:
        # Months are counted once, from the due date: each payment stop
        # charges the then-outstanding balance only for the months added
        # since the previous stop, so a mid-month payment cannot charge the
        # payment month twice on the continuing balance.
        outstanding, interest, cum = unpaid_at_due, 0.0, 0
        for pdate, amt in late_payments:
            if pdate <= due:
                continue  # already netted from the base
            pdate = min(pdate, filing)
            if outstanding > 0:
                m = _months_between(due, pdate)
                interest += _floor100(outstanding) * 0.01 * max(0, m - cum)
                cum = max(cum, m)
            outstanding = _pos(outstanding - amt)
        if outstanding > 0:
            m = _months_between(due, filing)
            interest += _floor100(outstanding) * 0.01 * max(0, m - cum)
        out["234A"] = int(interest)  # rule 119A: floor base to 100

    if assessed_tax >= ADVANCE_TAX_MIN and not senior_exempt:
        # 234B: advance (+TDS already netted) < 90% of assessed tax.
        # Interest runs from 1 Apr on the outstanding shortfall, stopping on
        # amounts discharged by self-assessment payments at their payment
        # date (s.234B(2)), and on the balance until filing.
        if advance_total < 0.90 * assessed_tax:
            # Same incremental month-counting as 234A, anchored at 1 Apr.
            outstanding, interest, cum = _pos(assessed_tax - advance_total), 0.0, 0
            for pdate, amt in late_payments:
                pdate = min(pdate, filing)
                if outstanding > 0:
                    m = _months_between(fy_end, pdate)
                    interest += _floor100(outstanding) * 0.01 * max(0, m - cum)
                    cum = max(cum, m)
                outstanding = _pos(outstanding - amt)
            if outstanding > 0:
                m = _months_between(fy_end, filing)
                interest += _floor100(outstanding) * 0.01 * max(0, m - cum)
            out["234B"] = int(interest)

        # 234C: cumulative 15/45/75/100% by Jun 15 / Sep 15 / Dec 15 / Mar 15.
        # Presumptive-only filers (s.234C(1)(b)): single 100% installment by 15 Mar.
        heads = comp["heads"]
        non_business = (heads["salary"].get("net", 0) + heads["house_property"]["income"]
                        + sum(heads["capital_gains"].values())
                        + heads["other_sources"]["total"]
                        + heads["other_sources"]["winnings"])
        if heads["business_presumptive"] > 0 and non_business <= 0:
            checkpoints = [(date(2026, 3, 15), 1.00, 1, None)]
            out["assumptions"].append("Presumptive-only income: single 100% advance-tax "
                                      "installment by 15 Mar (s.234C).")
        else:
            checkpoints = [
                (date(2025, 6, 15), 0.15, 3, 0.12),
                (date(2025, 9, 15), 0.45, 3, 0.36),
                (date(2025, 12, 15), 0.75, 3, None),
                (date(2026, 3, 15), 1.00, 1, None),
            ]
            if heads["business_presumptive"] > 0:
                out["assumptions"].append("Mixed presumptive + other income: 234C uses the "
                                          "standard 4-installment schedule; the presumptive "
                                          "portion may be overstated.")
        paid_by = lambda d: sum(_pos(a.get("amount")) for a in advance_list
                                if (_parse_date(a.get("date")) or filing) <= d)
        total_234c = 0.0
        for cp_date, pct, months, safe_pct in checkpoints:
            if cp_date > filing:
                continue  # installment not yet due on the computation date
            required = pct * assessed_tax
            paid = paid_by(cp_date)
            if safe_pct is not None and paid >= safe_pct * assessed_tax:
                continue  # safe harbour: 12%/36% paid by Q1/Q2
            if paid < required:
                total_234c += _floor100(required - paid) * 0.01 * months
        out["234C"] = int(total_234c)

    out["net_payable_before_interest"] = round(net_payable)
    out["total_interest_and_fee"] = out["234A"] + out["234B"] + out["234C"] + out["234F"]
    final = net_payable + out["total_interest_and_fee"]
    out["final_payable_or_refund"] = (-1 if final < 0 else 1) * _r10(abs(final))  # s.288B
    return out


def _parse_date(s):
    if not s:
        return None
    try:
        return date.fromisoformat(str(s))
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Entry
# ---------------------------------------------------------------------------

def compute(inp):
    want = inp.get("regime", "both")
    if want not in ("new", "old", "both"):
        raise ValueError(f"regime must be 'new', 'old' or 'both', got {want!r}")
    age = inp.get("age_category", "regular")
    if age not in ("regular", "senior", "super_senior"):
        raise ValueError(f"age_category must be 'regular', 'senior' or "
                         f"'super_senior', got {age!r}")

    # Belated return (s.139(4)): the old-regime option is gone - s.115BAC(6)
    # requires the opt-out in a return filed by the s.139(1) due date, and
    # the e-filing utility enforces it.
    due = _parse_date(inp.get("due_date")) or date(2026, 7, 31)
    filing = _parse_date(inp.get("filing_date")) or date.today()
    belated = filing > due

    result: dict = {"fy": FY, "ay": AY, "engine_version": "1.2.0"}
    regimes = ("new", "old") if want == "both" else (want,)
    for rk in regimes:
        comp = compute_regime(inp, rk)
        comp["interest_and_fees"] = compute_interest_and_fee(comp, inp)
        if belated and rk == "old":
            comp["warnings"].append("Belated return (s.139(4)): the old regime CANNOT be "
                                    "opted - s.115BAC(6) requires the choice in a return "
                                    "filed by the s.139(1) due date. Old-regime figures "
                                    "are informational only.")
        result[rk] = comp
    if len(regimes) == 2:
        n = result["new"]["tax"]["total_tax_liability"] + result["new"]["interest_and_fees"]["total_interest_and_fee"]
        o = result["old"]["tax"]["total_tax_liability"] + result["old"]["interest_and_fees"]["total_interest_and_fee"]
        better = "new" if (n <= o or belated) else "old"
        note = ("Recommendation is on submitted numbers only. Old regime needs "
                "proofs for every deduction claimed.")
        if belated and o < n:
            note += (" Old regime would be cheaper but is unavailable in a belated "
                     "return (s.115BAC(6)) - recommendation forced to new.")
        result["comparison"] = {
            "new_total": n, "old_total": o,
            "recommended_regime": better,
            "savings": abs(n - o),
            "note": note,
        }
    return result


def _fmt(n):
    """Indian digit grouping."""
    n = int(round(n))
    s, sign = str(abs(n)), "-" if n < 0 else ""
    if len(s) <= 3:
        return sign + s
    head, tail = s[:-3], s[-3:]
    parts = []
    while len(head) > 2:
        parts.insert(0, head[-2:])
        head = head[:-2]
    if head:
        parts.insert(0, head)
    return sign + ",".join(parts + [tail])


def render_table(result):
    lines = []
    add = lines.append
    add(f"Income-tax computation for FY {FY} (AY {AY})")
    add("=" * 64)
    for rk in ("new", "old"):
        if rk not in result:
            continue
        c = result[rk]
        t = c["tax"]
        add(f"\n[{rk.upper()} REGIME]")
        add(f"  Gross total income        {_fmt(c['gross_total_income']):>16}")
        add(f"  Deductions                {_fmt(c['deductions_total']):>16}")
        add(f"  Total income              {_fmt(c['total_income']):>16}")
        add(f"  Tax on slab income        {_fmt(t['slab_tax']):>16}")
        for s in t["special"]:
            add(f"  {s['section']:<25} {_fmt(s['tax']):>16}")
        if t["rebate_87a"]:
            add(f"  Rebate u/s 87A            {_fmt(-t['rebate_87a']):>16}")
        if t["marginal_relief_87a"]:
            add(f"  Marginal relief (87A)     {_fmt(-t['marginal_relief_87a']):>16}")
        if t["surcharge"]:
            add(f"  Surcharge                 {_fmt(t['surcharge'] - t['surcharge_marginal_relief']):>16}")
        add(f"  Cess (4%)                 {_fmt(t['cess']):>16}")
        if t.get("relief_89"):
            add(f"  Relief u/s 89             {_fmt(-t['relief_89']):>16}")
        add(f"  TOTAL TAX                 {_fmt(t['total_tax_liability']):>16}")
        i = c["interest_and_fees"]
        for k in ("234A", "234B", "234C", "234F"):
            if i[k]:
                add(f"  Interest/fee {k}        {_fmt(i[k]):>16}")
        add(f"  NET PAYABLE (-ve=refund)  {_fmt(i['final_payable_or_refund']):>16}")
    if "comparison" in result:
        cmp_ = result["comparison"]
        add("\n" + "=" * 64)
        add(f"  RECOMMENDED: {cmp_['recommended_regime'].upper()} regime "
            f"(saves Rs. {_fmt(cmp_['savings'])})")
        add(f"  New: {_fmt(cmp_['new_total'])}   Old: {_fmt(cmp_['old_total'])}")
    warn = set(result.get("new", {}).get("warnings", []) + result.get("old", {}).get("warnings", []))
    if warn:
        add("\nNotes:")
        for w in sorted(warn):
            add(f"  - {w}")
    return "\n".join(lines)


def main(argv):
    if len(argv) < 2 or argv[1] in ("-h", "--help"):
        print(__doc__)
        return 0
    try:
        raw = sys.stdin.read() if argv[1] == "-" else open(argv[1]).read()
    except OSError as e:
        print(f"ERROR: cannot read input file: {e}", file=sys.stderr)
        return 2
    try:
        inp = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"ERROR: input is not valid JSON: {e}", file=sys.stderr)
        return 2
    if not isinstance(inp, dict):
        print("ERROR: input must be a JSON object - see references/input-schema.md",
              file=sys.stderr)
        return 2
    try:
        result = compute(inp)
    except (TypeError, ValueError, KeyError, AttributeError) as e:
        print(f"ERROR: bad value in income.json ({e}) - run validate_income.py "
              "on this file first; it pinpoints the field.", file=sys.stderr)
        return 2
    if "--json" in argv:
        print(json.dumps(result, indent=2))
    else:
        print(render_table(result))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
