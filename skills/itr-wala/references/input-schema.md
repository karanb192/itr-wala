# income.json - input schema for tax_engine.py

When to read this: before writing or editing the `income.json` that you feed to `scripts/tax_engine.py` - it defines every valid key, what document each figure comes from, and what you must never put in it.

## Iron rules

1. **Transcribed figures only.** Every number must be readable off a document (Form 16, 26AS, AIS, broker P&L, interest certificate, challan). NEVER enter a derived number: no salary net of standard deduction, no LTCG minus the 1,25,000 exemption, no house-property income after the 30% deduction, no tax you computed. The engine does all arithmetic.
2. Amounts are whole rupees, non-negative. Losses are never entered as negative income - the only loss the engine models is house property (via `interest_paid`).
3. `validate_income.py` rejects unknown/misspelled keys (e.g. `80ccd2` instead of `80ccd_2`) - a typo would otherwise silently cost the user a deduction. Always run `python3 scripts/validate_income.py income.json` and fix to 0 errors before `python3 scripts/tax_engine.py income.json`.
4. Old-regime-only fields (`exempt_allowances`, `professional_tax`, most `deductions`) still go in the file - the engine ignores them per regime and warns, which is how the both-regime comparison works.

## Annotated example (fictional; `//` comments are illustrative - the real file must be pure JSON)

```jsonc
{
  "regime": "both",                    // "new" | "old" | "both" - leave "both" to compare regimes
  "age_category": "regular",           // "regular" | "senior" (60-79) | "super_senior" (80+)
  "residential_status": "resident",    // engine is resident-only; NRI/RNOR → stop, out of scope
  "name": "Asha Verma",
  "due_date": "2026-07-31",            // AY 2026-27: ITR-1/2 → 2026-07-31; non-audit ITR-3/4 → 2026-08-31
  "filing_date": "2026-07-28",         // defaults to today if omitted
  "income": {
    "salary": {
      "gross": 2400000,                // Form 16 Part B: 17(1)+17(2)+17(3), BEFORE any deduction
      "form16_17_1": 2260000,          // salary u/s 17(1)
      "form16_17_2": 140000,           // perquisites u/s 17(2)
      "form16_17_3": 0,                // profits in lieu u/s 17(3); validator checks sum == gross
      "exempt_allowances": 320000,     // HRA/LTA exempt u/s 10 (Form 16 Part B) - old regime only
      "professional_tax": 2400,        // s.16(iii) from Form 16/payslips - old regime only, engine caps at 5,000
      "basic_plus_da": 960000          // annual basic+DA from payslips; optional, enables 80CCD(2) cap check
    },
    "house_property": [
      { "type": "self_occupied", "interest_paid": 185000 }  // lender's interest certificate, full amount
    ],
    "capital_gains": {
      "stcg_111a": 45000,              // broker tax P&L: STT-paid equity/equity-MF held ≤12m
      "ltcg_112a": 180000              // FULL gain - engine subtracts the 1,25,000 exemption itself
    },
    "other_sources": {
      "savings_interest": 12400,       // bank statements/AIS - keep separate from FD (80TTA needs the split)
      "fd_interest": 38600,
      "dividends": 15200               // AIS; keep in "dividends" (drives the 15% surcharge cap logic)
    }
  },
  "deductions": {
    "80c": 150000,                     // sum of proofs (EPF+ELSS+LIC...); engine caps at 1,50,000
    "80d": 28000                       // ELIGIBLE amount within s.80D caps - engine does NOT cap 80D
  },
  "taxes_paid": {
    "tds": 355000,                     // 26AS grand total, ALL deductors (here employer 3,42,000 + bank 13,000)
    "advance_tax": [ { "date": "2025-12-10", "amount": 25000 } ]  // challan; the date drives 234C
  },
  "source_totals": {                   // verbatim document totals - copied, never adjusted
    "form16_gross_salary": 2400000,
    "form16_total_tds": 342000,
    "form26as_total_tds": 355000,
    "ais_total_tds": 355000,
    "ais_savings_interest": 12400,
    "ais_dividends": 15200
  }
}
```

This example triggers one expected validator warning (TDS claimed 3,55,000 differs from Form 16's 3,42,000) - that gap is the banks' FD-interest TDS, visible in 26AS. Explain such gaps to the user; never silence them by changing a number.

## Field reference

| Field | Meaning | Source document | Gotchas |
|---|---|---|---|
| `regime` | "new"/"old"/"both" (default "both") | user choice | keep "both" until the comparison is shown |
| `age_category` | slab/80TTB/advance-tax age band | DOB | wrong band changes old slabs, 80TTB, 234B/C waiver |
| `residential_status` | informational gate | user | anything non-resident → stop; engine can't file it |
| `due_date` | statutory due date, ISO | form choice | engine default 2026-07-31; set 2026-08-31 for non-audit ITR-3/4 |
| `salary.gross` | 17(1)+17(2)+17(3) total | Form 16 Part B | gross, not "taxable salary"; standard deduction (75,000 new / 50,000 old) is engine-applied |
| `salary.form16_17_1/2/3` | the three components | Form 16 Part B | optional but recommended; validator enforces sum == `gross` |
| `salary.exempt_allowances` | s.10 exempt HRA/LTA etc. | Form 16 Part B annexure | old regime only; engine ignores + warns in new. Do NOT put gratuity/leave encashment here - those go in `exempt_retirement` |
| `salary.exempt_retirement` | gratuity 10(10), commuted pension 10(10A), leave encashment 10(10AA), retrenchment 10(10B), VRS 10(10C) | Form 16 Part B s.10 annexure | exempt in BOTH regimes - these survive s.115BAC; engine deducts before the standard deduction |
| `salary.professional_tax` | s.16(iii) | Form 16 / payslips | old only; engine caps 5,000 |
| `salary.basic_plus_da` | annual basic + DA | payslips | optional; unlocks the 80CCD(2) cap check (14% new / 10% old private) |
| `house_property[]` | `{type, rent_received, municipal_taxes, interest_paid}` | rent record, tax receipts, interest certificate | `type`: "self_occupied" or "let_out". Enter raw figures; engine does the 30% NAV deduction, the 2,00,000 s.24(b)/s.71(3A) caps (old) and zeroes it in new regime. Municipal taxes above rent are capped at the rent (s.24(a) - NAV never negative); if the engine warns, the figures likely have a transcription error |
| `capital_gains.stcg_111a` | STT equity/eq-MF ≤12m gains | broker tax P&L | taxed 20% (s.111A) |
| `capital_gains.ltcg_112a` | STT equity/eq-MF >12m gains | broker tax P&L | enter FULL gain; engine applies 1,25,000 exemption and 12.5%. Aggregate across all brokers |
| `capital_gains.ltcg_other` | s.112 LTCG (property, gold, unlisted) | sale deed / statements | engine uses flat 12.5% no-indexation; the 20%-with-indexation option for land/building acquired on/before 22-Jul-2024 is NOT modeled - flag to user if relevant |
| `capital_gains.stcg_slab` | slab-rate gains | broker/AMC statements | debt MFs (s.50AA, units bought on/after 1-Apr-2023 are always slab-rate STCG), short-held gold, etc. |
| `capital_gains.vda` | crypto/VDA gains, s.115BBH | exchange statement | sale minus cost of acquisition only; NEVER net losses against gains (no set-off); 30% flat, forces ITR-2/3 |
| `other_sources.savings_interest` / `fd_interest` | bank interest | AIS + bank statements | the split matters: 80TTA (regular) counts savings only; 80TTB (seniors) counts both |
| `other_sources.dividends` | dividend income | AIS / broker | must sit here, not in `other` - engine's 15% surcharge cap keys on this field |
| `other_sources.family_pension` | family pension at slab | bank credits | engine applies the s.57(iia) deduction automatically (1/3 capped at 25,000 new / 15,000 old) |
| `other_sources.winnings` | lottery/game-show/online-game winnings u/s 115BB/115BBJ | AIS ("Winnings from online games"), 194B/194BA TDS entries | flat 30%, no basic exemption, no deductions, no 87A - never put winnings in `other` (slab) |
| `other_sources.other` | residual slab-rate income | varies | NOT for buyback (see capital-gains.md) and NOT for winnings (use `winnings`) |
| `relief_89` (top level) | s.89(1) relief for salary arrears | Form 10E computation / Form 16 "relief u/s 89" | engine nets it after cess; Form 10E must be e-filed before the return |
| `business_presumptive_income` | declared presumptive income (44AD/44ADA) | user's election | the one declared (not document) figure: e.g. 50% of 44ADA gross receipts as elected |
| `deductions.80c/80ccd_1b/80d/80g/other` | Chapter VI-A claims | proof receipts | old regime only (engine warns in new). 80C capped 1,50,000; 80CCD(1B) 50,000; 80D and 80G NOT engine-capped - enter only the eligible amount |
| `deductions.80ccd_2` | employer NPS | Form 16 | valid in BOTH regimes; capped at 14%/10% of `basic_plus_da` when that field is present |
| `deductions.80tta_ttb` | savings-interest deduction | - | best OMITTED: engine auto-derives from the interest fields and applies 10,000/50,000 caps |
| `taxes_paid.tds` / `tcs` | total TDS/TCS, all deductors | 26AS | claim from 26AS, not Form 16 alone; validator errors if claim exceeds the 26AS total |
| `taxes_paid.advance_tax[]` / `self_assessment[]` | `{date: "YYYY-MM-DD", amount}` per challan | challan receipts (CIN) | dates are load-bearing: they decide 234A/234C |

## Tricky placements

- **Share buyback (1-Oct-2024 to 31-Mar-2026):** the FULL buyback consideration is deemed dividend u/s 2(22)(f), taxed at slab with no cost deduction. Put it in `other_sources.dividends` (it is dividend income, entitled to the 15% surcharge cap the engine keys on that field) and tell the user why - note it will make reported dividends exceed `ais_dividends`, which is expected here. The acquisition cost separately becomes a capital loss (consideration deemed nil u/s 46A) - the engine does not track losses/carry-forward, so record that loss for the ITR's Schedule CG/CFL manually.
- **Debt mutual fund gains** (units acquired on/after 1-Apr-2023): always `capital_gains.stcg_slab`, whatever the holding period. Units bought before 1-Apr-2023 held >24m → `ltcg_other` at 12.5%.
- **HRA:** never compute the exemption yourself if Form 16 already shows it - transcribe the employer's s.10 figure into `exempt_allowances`. If the employer missed HRA, the exemption is a genuine computation: do it outside the engine, show the working to the user, and note it is old-regime-only.
- **Interest on let-out property:** goes in that property's `interest_paid` uncapped - the engine handles the loss-set-off cap.

## Why source_totals exists

`source_totals` holds the headline totals exactly as printed on each document - Form 16 gross salary and total TDS, 26AS total TDS, AIS total TDS / savings interest / dividends. The engine never taxes these; the validator uses them to cross-check your extraction: Form 16 component sum vs `salary.gross`, TDS claimed vs 26AS (hard error if you claim more), AIS interest/dividends vs what `income` reports (hard error if you report less - omitting AIS-visible income invites a notice). Always fill it; leaving it empty downgrades the whole run to "unchecked extraction" and the validator says so.
