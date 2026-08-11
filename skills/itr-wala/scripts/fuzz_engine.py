#!/usr/bin/env python3
"""Property-based fuzzer for tax_engine.py - FY 2025-26 (AY 2026-27).

Generates random schema-valid income.json inputs biased toward statutory
boundaries (slab edges, 87A thresholds, the 1,25,000 s.112A exemption,
surcharge tiers) and asserts invariants that must hold for every
resident-individual computation:

  1  compute() never raises on schema-valid input.
  2  Determinism: identical input -> byte-identical json.dumps output.
  3  Rounding: total_income and total_tax_liability are non-negative
     multiples of 10 (s.288A/288B); final_payable_or_refund is a multiple
     of 10.
  4  Bounds: 87A rebate <= 60,000 (new) / 12,500 (old); 234A/B/C/F >= 0;
     234F in {0, 1000, 5000}; surcharge marginal relief <= surcharge;
     87A rebate and 87A marginal relief never both positive.
  5  Cess equals 4% of (tax_after_rebate + surcharge - relief) within 1 rupee.
  6  total_tax_liability reconciles with its components within 10 rupees.
  7  Regime comparison: savings == |new - old| and the recommendation is
     the cheaper regime.
  8  New-regime monotonicity: adding 1,000..1,00,000 of income to one field
     never lowers the new-regime total_tax_liability by more than 10 rupees,
     one s.288B rounding quantum - surcharge-tier tests run on the s.288A-
     rounded total income, so a bump can lawfully flip a tier boundary and
     land the rounded payable one quantum lower (old regime exempt: its
     5,00,000 87A rebate cliff is statutory).

Zero dependencies (Python 3.9+ stdlib). Fully deterministic for a given
--seed: every random draw flows from one random.Random(seed).

Usage:
    python3 fuzz_engine.py                        # 2000 cases, seed 42
    python3 fuzz_engine.py --cases 20000 --seed 7 --verbose

Exit 0: every invariant held. Exit 1: a shrunk repro JSON is printed for
each violated invariant (at most 5) with a per-invariant tally - save the
repro to a file and replay with `python3 tax_engine.py repro.json --json`.
Exit 2: the generator itself emitted schema-invalid input (fuzzer bug).
"""

import argparse
import copy
import json
import math
import random
import sys
from datetime import date, timedelta

if sys.version_info < (3, 9):
    sys.exit("itr-wala needs Python 3.9 or newer (found %d.%d)." % sys.version_info[:2])

import tax_engine
from validate_income import check as validate_check

# ---------------------------------------------------------------------------
# Boundary-biased generators
# ---------------------------------------------------------------------------

# Rupee points where FY 2025-26 rules bend: slab edges, 87A thresholds,
# the 112A exemption, basic exemptions, surcharge tiers.
MAGIC_AMOUNTS = [
    0, 1,
    125_000, 250_000, 300_000, 400_000, 500_000,
    800_000, 1_000_000, 1_200_000, 1_275_000, 1_600_000,
    2_000_000, 2_400_000,
    5_000_000, 10_000_000, 20_000_000, 50_000_000,
]
DELTAS = [-1_000, -100, -10, -5, -1, 0, 1, 5, 10, 100, 1_000]
AMOUNT_CAP = 1_000_000_000            # 100 crore; the validator warns beyond
DEDUCTION_MAGIC = [0, 1, 10_000, 25_000, 50_000, 100_000, 150_000, 200_000, 500_000]

# Advance-tax challans cluster around the 234C installment dates.
INSTALLMENT_DATES = [date(2025, 6, 15), date(2025, 9, 15),
                     date(2025, 12, 15), date(2026, 3, 15)]
SELF_ASSESSMENT_DATES = [date(2026, 7, 25), date(2026, 7, 31), date(2026, 8, 31)]
DUE_DATES = ["2026-07-31", "2026-08-31", "2026-10-31"]

BUMP_FIELDS = ("salary.gross", "other_sources.other", "stcg_111a", "ltcg_112a", "vda")

MAX_SHOWN = 5          # repros printed per run
SHRINK_BUDGET = 500    # predicate evaluations per repro shrink


def rand_amount(rng):
    """Boundary-biased rupee amount: magic points +/- small deltas, else
    log-uniform across 1 .. 100 crore, else zero. Occasionally fractional
    (paise creep in real broker exports)."""
    roll = rng.random()
    if roll < 0.55:
        v = rng.choice(MAGIC_AMOUNTS) + rng.choice(DELTAS)
    elif roll < 0.90:
        v = int(math.exp(rng.uniform(0.0, math.log(AMOUNT_CAP))))
    else:
        v = 0
    if rng.random() < 0.05:
        v += 0.5
    return min(max(v, 0), AMOUNT_CAP)


def rand_deduction(rng):
    """Deduction-sized amount biased toward the Chapter VI-A caps."""
    if rng.random() < 0.6:
        v = rng.choice(DEDUCTION_MAGIC) + rng.choice(DELTAS)
    else:
        v = int(math.exp(rng.uniform(0.0, math.log(3_000_000))))
    return max(v, 0)


def rand_payment_date(rng, magic_dates, start, span_days):
    if rng.random() < 0.6:
        d = rng.choice(magic_dates) + timedelta(days=rng.randint(-3, 3))
    else:
        d = start + timedelta(days=rng.randint(0, span_days))
    return d.isoformat()


def rand_payments(rng, proxy, magic_dates, start, span_days):
    out = []
    for _ in range(rng.randint(1, 3)):
        if proxy > 0 and rng.random() < 0.6:
            amount = int(proxy * rng.uniform(0.0, 0.6))
        else:
            amount = rand_amount(rng)
        out.append({"date": rand_payment_date(rng, magic_dates, start, span_days),
                    "amount": amount})
    return out


def _sum_amounts(node):
    """Recursive sum of every number in a subtree - rough income proxy so
    generated TDS/advance-tax amounts land near realistic magnitudes."""
    if isinstance(node, dict):
        return sum(_sum_amounts(v) for v in node.values())
    if isinstance(node, list):
        return sum(_sum_amounts(v) for v in node)
    if isinstance(node, (int, float)) and not isinstance(node, bool):
        return node
    return 0


def gen_case(rng):
    """One random schema-valid input. Sections go missing or empty at random
    so defaults get fuzzed too."""
    inp = {}
    if rng.random() < 0.9:
        inp["regime"] = "both"      # omitted -> engine defaults to both anyway
    if rng.random() < 0.9:
        inp["age_category"] = rng.choice(
            ("regular", "regular", "regular", "senior", "super_senior"))

    income = {}
    if rng.random() < 0.75:
        sal = {"gross": rand_amount(rng)}
        if rng.random() < 0.35:
            # Sometimes a plausible fraction of gross, sometimes unrelated
            # (exempt > gross is a boundary the engine must clamp).
            sal["exempt_allowances"] = (rand_amount(rng) if rng.random() < 0.3
                                        else int(sal["gross"] * rng.uniform(0.0, 0.5)))
        if rng.random() < 0.25:
            sal["professional_tax"] = rng.choice((0, 200, 2_400, 2_500, 4_999, 5_000, 6_000))
        if rng.random() < 0.25:
            sal["basic_plus_da"] = int(sal["gross"] * rng.uniform(0.3, 0.6))
        income["salary"] = sal

    props = []
    sop_used = 0
    for _ in range(rng.choice((0, 0, 0, 0, 1, 1, 2, 3))):
        # s.23(4): at most two self-occupied properties (validator enforces).
        if rng.random() < 0.5 and sop_used < 2:
            sop_used += 1
            p = {"type": "self_occupied",
                 "interest_paid": rng.choice((0, 100_000, 199_990, 200_000,
                                              200_010, 350_000, rand_amount(rng)))}
        else:
            p = {"type": "let_out", "rent_received": rand_amount(rng)}
            if rng.random() < 0.5:
                # Fraction of rent, or unrelated (municipal > rent: the engine
                # clamps NAV to 0 - s.24(a) caps the deduction at the annual
                # value, so no loss may come from the tax excess).
                p["municipal_taxes"] = (int(p["rent_received"] * rng.uniform(0.0, 0.3))
                                        if rng.random() < 0.7 else rand_amount(rng))
            if rng.random() < 0.7:
                p["interest_paid"] = rand_amount(rng)
        props.append(p)
    if props or rng.random() < 0.05:
        income["house_property"] = props

    cg = {}
    for key in ("stcg_111a", "ltcg_112a", "ltcg_other", "stcg_slab", "vda"):
        if rng.random() < 0.35:
            cg[key] = rand_amount(rng)
    if cg or rng.random() < 0.05:
        income["capital_gains"] = cg

    os_ = {}
    for key in ("savings_interest", "fd_interest", "dividends", "family_pension", "other"):
        if rng.random() < 0.3:
            os_[key] = rand_amount(rng)
    if os_ or rng.random() < 0.05:
        income["other_sources"] = os_

    if rng.random() < 0.2:
        income["business_presumptive_income"] = rand_amount(rng)
    if income or rng.random() < 0.5:
        inp["income"] = income

    ded = {}
    for key in ("80c", "80ccd_1b", "80ccd_2", "80d", "80tta_ttb", "80g", "other"):
        if rng.random() < 0.25:
            ded[key] = rand_deduction(rng)
    if ded:
        inp["deductions"] = ded

    proxy = _sum_amounts(income)
    tp = {}
    if rng.random() < 0.5:
        tp["tds"] = (int(proxy * rng.uniform(0.0, 0.35))
                     if proxy > 0 and rng.random() < 0.7 else rand_amount(rng))
    if rng.random() < 0.15:
        tp["tcs"] = rand_deduction(rng)
    if rng.random() < 0.45:
        tp["advance_tax"] = rand_payments(rng, proxy * 0.3, INSTALLMENT_DATES,
                                          date(2025, 4, 1), 364)
    if rng.random() < 0.3:
        tp["self_assessment"] = rand_payments(rng, proxy * 0.3, SELF_ASSESSMENT_DATES,
                                              date(2026, 4, 1), 270)
    if tp:
        inp["taxes_paid"] = tp

    if rng.random() < 0.8:
        inp["due_date"] = rng.choice(DUE_DATES)
    if rng.random() < 0.95:
        if rng.random() < 0.5:
            f = (date.fromisoformat(rng.choice(DUE_DATES))
                 + timedelta(days=rng.randint(-5, 5)))
        else:
            f = date(2026, 6, 1) + timedelta(days=rng.randint(0, 300))
        inp["filing_date"] = f.isoformat()
    if rng.random() < 0.1:
        inp["residential_status"] = "resident"
    return inp


def apply_bump(inp, field, delta):
    """Return a deep copy of inp with `delta` rupees added to one income
    field (creating the path if the section was absent)."""
    out = copy.deepcopy(inp)
    income = out.setdefault("income", {})
    if field == "salary.gross":
        sal = income.setdefault("salary", {})
        sal["gross"] = sal.get("gross", 0) + delta
    elif field == "other_sources.other":
        os_ = income.setdefault("other_sources", {})
        os_["other"] = os_.get("other", 0) + delta
    else:
        cg = income.setdefault("capital_gains", {})
        cg[field] = cg.get(field, 0) + delta
    return out


# ---------------------------------------------------------------------------
# Invariants
# ---------------------------------------------------------------------------

def run_case(inp, bump_field, bump_delta):
    """Run every invariant against one input. Returns a list of violations:
    {"invariant", "message", "input", "bump"} - "input" is the exact dict
    that exhibits the failure (the bumped one for a bumped-input crash)."""
    fails = []

    def fail(inv, msg, case=inp, bump=None):
        fails.append({"invariant": inv, "message": msg, "input": case, "bump": bump})

    try:
        r1 = tax_engine.compute(inp)
    except Exception as e:                                     # invariant 1
        fail("1-no-raise", f"compute() raised {type(e).__name__}: {e}")
        return fails
    r2 = tax_engine.compute(inp)
    if json.dumps(r1) != json.dumps(r2):                       # invariant 2
        fail("2-determinism", "two identical compute() calls returned different JSON")

    for rk in ("new", "old"):
        if rk not in r1:
            continue
        c = r1[rk]
        t, fees = c["tax"], c["interest_and_fees"]
        pre = f"[{rk}] "
        if c["total_income"] % 10 or c["total_income"] < 0:    # invariant 3
            fail("3-rounding", pre + f"total_income={c['total_income']}")
        if t["total_tax_liability"] % 10 or t["total_tax_liability"] < 0:
            fail("3-rounding", pre + f"total_tax_liability={t['total_tax_liability']}")
        if fees["final_payable_or_refund"] % 10:
            fail("3-rounding",
                 pre + f"final_payable_or_refund={fees['final_payable_or_refund']}")

        cap = 60_000 if rk == "new" else 12_500                # invariant 4
        if t["rebate_87a"] > cap:
            fail("4-bounds", pre + f"rebate_87a={t['rebate_87a']} > {cap}")
        for k in ("234A", "234B", "234C", "234F"):
            if fees[k] < 0:
                fail("4-bounds", pre + f"{k}={fees[k]} is negative")
        if fees["234F"] not in (0, 1_000, 5_000):
            fail("4-bounds", pre + f"234F={fees['234F']} not in {{0, 1000, 5000}}")
        if t["surcharge_marginal_relief"] > t["surcharge"]:
            fail("4-bounds", pre + f"surcharge_marginal_relief="
                 f"{t['surcharge_marginal_relief']} > surcharge={t['surcharge']}")
        if t["rebate_87a"] > 0 and t["marginal_relief_87a"] > 0:
            fail("4-bounds", pre + "rebate_87a and marginal_relief_87a both positive")

        base = t["tax_after_rebate"] + t["surcharge"] - t["surcharge_marginal_relief"]
        if abs(t["cess"] - 0.04 * base) > 1:                   # invariant 5
            fail("5-cess", pre + f"cess={t['cess']} but 4% of {base} = {0.04 * base:.2f}")
        if abs(t["total_tax_liability"] - (base + t["cess"])) > 10:   # invariant 6
            fail("6-liability", pre + f"total_tax_liability={t['total_tax_liability']} "
                 f"vs components {base + t['cess']}")

    comp = r1.get("comparison")                                # invariant 7
    if comp:
        n, o = comp["new_total"], comp["old_total"]
        if comp["savings"] != abs(n - o):
            fail("7-comparison", f"savings={comp['savings']} != |{n} - {o}|")
        rec = comp["recommended_regime"]
        # Belated returns lock the choice to the new regime (s.115BAC(6)) -
        # the engine then forces rec="new" even when old is cheaper.
        belated_lock = "belated" in comp.get("note", "").lower()
        if (n < o and rec != "new") or (o < n and rec != "old" and not belated_lock):
            fail("7-comparison", f"recommended={rec} but new={n} old={o}")
        if o < n and rec == "new" and not belated_lock:
            fail("7-comparison", f"recommended=new with old cheaper and no belated note")

    bumped = apply_bump(inp, bump_field, bump_delta)           # invariant 8
    try:
        rb = tax_engine.compute(bumped)
    except Exception as e:
        fail("1-no-raise", f"compute() raised {type(e).__name__}: {e} (bumped input)",
             case=bumped)
        return fails
    if "new" in r1 and "new" in rb:
        before = r1["new"]["tax"]["total_tax_liability"]
        after = rb["new"]["tax"]["total_tax_liability"]
        # Tolerance = one s.288B quantum: tier thresholds are tested on the
        # s.288A-rounded total income, so a bump across a surcharge boundary
        # (with marginal relief pinning tax to the threshold benchmark) can
        # lawfully round the payable 10 rupees lower.
        if after < before - 10:
            fail("8-monotonic", f"+{bump_delta} to {bump_field}: new-regime "
                 f"total_tax_liability fell {before} -> {after}",
                 bump={"field": bump_field, "delta": bump_delta})
    return fails


# ---------------------------------------------------------------------------
# Repro shrinking - greedy delete + numeric bisection, budget-capped
# ---------------------------------------------------------------------------

def _paths(node, prefix=()):
    if isinstance(node, dict):
        for k in list(node):
            yield prefix + (k,)
            yield from _paths(node[k], prefix + (k,))
    elif isinstance(node, list):
        for i in range(len(node)):
            yield prefix + (i,)
            yield from _paths(node[i], prefix + (i,))


def _parent_of(root, path):
    node = root
    for step in path[:-1]:
        node = node[step]
    return node


def _still_fails(candidate, inv, bump_field, bump_delta):
    """Shrink predicate: candidate must stay schema-valid AND still violate
    the same invariant."""
    errors, _ = validate_check(candidate)
    if errors:
        return False
    return any(v["invariant"] == inv for v in run_case(candidate, bump_field, bump_delta))


def shrink(violation, bump_field, bump_delta, budget=SHRINK_BUDGET):
    """Minimize a failing input: drop whole sections/keys first, then
    bisect each remaining number toward 0. Best-effort and budget-capped -
    the result always still violates the invariant."""
    inv = violation["invariant"]
    best = copy.deepcopy(violation["input"])

    def deletion_pass():
        nonlocal best, budget
        progress = True
        while progress and budget > 0:
            progress = False
            for path in sorted(_paths(best), key=len):
                cand = copy.deepcopy(best)
                try:
                    parent = _parent_of(cand, path)
                    del parent[path[-1]]
                except (KeyError, IndexError, TypeError):
                    continue
                budget -= 1
                if _still_fails(cand, inv, bump_field, bump_delta):
                    best = cand
                    progress = True
                    break              # structure changed; re-enumerate paths
                if budget <= 0:
                    break

    def numeric_pass():
        nonlocal budget
        progress = True
        while progress and budget > 0:
            progress = False
            for path in list(_paths(best)):
                try:
                    parent = _parent_of(best, path)
                    val = parent[path[-1]]
                except (KeyError, IndexError, TypeError):
                    continue
                if (not isinstance(val, (int, float)) or isinstance(val, bool)
                        or not val or budget <= 0):
                    continue

                def try_value(v):
                    nonlocal budget
                    old = parent[path[-1]]
                    parent[path[-1]] = v
                    budget -= 1
                    if _still_fails(best, inv, bump_field, bump_delta):
                        return True
                    parent[path[-1]] = old
                    return False

                if try_value(0):
                    progress = True
                    continue
                lo, hi = 0, val        # lo passes, hi still fails
                while hi - lo > 1 and budget > 0:
                    mid = int((lo + hi) // 2)
                    if try_value(mid):
                        hi = mid
                    else:
                        lo = mid
                if hi < val:
                    progress = True

    deletion_pass()
    numeric_pass()
    deletion_pass()                    # zeroed numbers may free whole sections
    return best


# ---------------------------------------------------------------------------
# Entry
# ---------------------------------------------------------------------------

def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Property-based fuzzer for tax_engine.compute().")
    ap.add_argument("--cases", type=int, default=2000,
                    help="number of random cases (default 2000)")
    ap.add_argument("--seed", type=int, default=42,
                    help="RNG seed; same seed -> same cases (default 42)")
    ap.add_argument("--verbose", action="store_true",
                    help="progress every 500 cases + each violation as found")
    args = ap.parse_args(argv)

    rng = random.Random(args.seed)
    tally = {}                 # invariant id -> violation count
    kept = []                  # first (violation, bump) per invariant id
    seen = set()
    verbose_shown = 0

    for case_no in range(1, args.cases + 1):
        inp = gen_case(rng)
        bump_field = rng.choice(BUMP_FIELDS)
        bump_delta = rng.randint(1_000, 100_000)

        errors, _ = validate_check(inp)
        if errors:
            print(f"FUZZER BUG (case {case_no}): generator emitted schema-invalid input:",
                  file=sys.stderr)
            for e in errors[:5]:
                print(f"  {e}", file=sys.stderr)
            print(json.dumps(inp, sort_keys=True), file=sys.stderr)
            return 2

        for v in run_case(inp, bump_field, bump_delta):
            tally[v["invariant"]] = tally.get(v["invariant"], 0) + 1
            if v["invariant"] not in seen and len(kept) < MAX_SHOWN:
                seen.add(v["invariant"])
                kept.append((v, bump_field, bump_delta))
            if args.verbose and verbose_shown < 20:
                verbose_shown += 1
                print(f"case {case_no}: {v['invariant']} - {v['message']}")
        if args.verbose and case_no % 500 == 0:
            print(f"... {case_no}/{args.cases} cases, "
                  f"{sum(tally.values())} violation(s) so far")

    if not tally:
        print(f"OK - {args.cases} cases (seed {args.seed}), all invariants held.")
        return 0

    print(f"FAIL - {sum(tally.values())} violation(s) across {args.cases} cases "
          f"(seed {args.seed}). Violations per invariant:")
    for inv in sorted(tally):
        print(f"  {inv}: {tally[inv]}")
    for idx, (v, bf, bd) in enumerate(kept, 1):
        small = shrink(v, bf, bd)
        fresh = [w for w in run_case(small, bf, bd) if w["invariant"] == v["invariant"]]
        msg = fresh[0]["message"] if fresh else v["message"]
        print(f"\n--- violation {idx}/{len(kept)}: {v['invariant']} ---")
        print(f"  {msg}")
        if v["invariant"] == "8-monotonic":
            print(f"  bump: {bf} += {bd}")
        print(f"  repro: {json.dumps(small, sort_keys=True)}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
