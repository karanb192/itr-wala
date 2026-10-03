# Advance tax for either supported financial year

Read after confirming `financial_year` and `purpose: "advance_tax"`. This
workflow estimates a payment. It does not file a return or certify historical
interest. The user alone pays.

## Interview and evidence

1. Confirm FY 2025-26 or FY 2026-27, residency, age and the as-of date.
2. Collect current payslips/payroll projections, bank interest forecasts,
   realised broker gains, rent records, deduction proofs and paid challans.
   A final year-end certificate may not exist yet. Use only the selected
   year's documents and the normal privacy/blind-extraction rules.
3. Ask the user for full-year expected income, eligible deductions and
   expected TDS/TCS. Transcribe forecasts from documents or numbers the user
   explicitly approves. Record the source, period, actual/estimated status
   and approval for each figure. Never extrapolate, sum or compute tax with
   the model. If a total needs deriving, use a deterministic script and show
   its output for approval. Do not predict future sales or investment returns.
4. Keep actual credits in `taxes_paid.tds/tcs` and actual document totals in
   `source_totals`. Put full-year expected credits in `expected_tax_credits`.
   Do not cross-check an annual forecast against a year-to-date certificate
   as though they describe the same period. Record why the periods differ.
   Do not put year-to-date salary in `source_totals.form16_gross_salary`
   while `salary.gross` is an annual forecast: that check requires equal
   periods. Keep YTD salary and payslip components in the source trail;
   those legacy Form 16 fields are for a matching final annual certificate.
   Expected credits must be supportable: do not assume credit for income
   already paid without required withholding. Verify such cases separately
   under s.209/405 rather than reducing the payment by hypothetical TDS.
5. Ask whether presumptive income is an eligible election under 44AD/44ADA
   (FY 2025-26) or s.58(2), Table 1/3 (FY 2026-27). Enter the declared income,
   not turnover. Ask about old-regime business elections and withdrawals;
   a cheaper computed regime is conditional on its legal availability.

## Input and computation

Set `financial_year`, `purpose`, `as_of_date`, `income`, `deductions`,
`expected_tax_credits` and `taxes_paid`. Omit `due_date`, `filing_date` and
self-assessment payments. Only paid advance-tax challans on or before the
as-of date count. No planned payment may be entered as already paid.

Run `validate_income.py` to exit 0, show its warnings, then run `tax_engine.py`
in text and JSON modes. Use the engine's figures verbatim. Review both regimes,
annual tax, expected credits, recorded payments and the next payment date and
amount. The annual tax includes surcharge and cess. It excludes future filing
fees and default interest; a negative payment is never shown as a refund.

Standard cumulative targets are 15%, 45%, 75%, 100% by 15 June, 15 September,
15 December and 15 March of the selected income year. Eligible presumptive
taxpayers use one 100% March instalment even with other income. Resident seniors
without business/professional income owe no advance tax. Net annual liability
below ₹10,000 does not require advance tax. These rules come from
[the department's advance-tax guidance](https://incometaxindia.gov.in/Tutorials/31.%20Provisions%20on%20pymt%20of%20adv.%20tax.pdf) and
[s.404/408 of the 2025 Act](https://www.incometaxindia.gov.in/documents/d/guest/income_tax_act_2025_as_amended_by_fa_act_2026-pdf).

Past schedule shortfalls are payment comparisons, not an interest assessment.
Capital-gain/dividend timing and other statutory exceptions can change deferment
interest. Get the dated evidence and use the official computation or a CA for
that part. After 15 March, the plan labels any remaining payment by 31 March as
a year-end top-up; it does not claim this cures a missed March instalment.

## Handoff and revisit

Save a labelled estimate pack: FY/TY, Act, as-of date, approved annual inputs,
source trail, engine comparison, next amount/date and assumptions. Before the
user pays, verify the government payment screen uses the selected income year,
applicable Act and advance-tax category. Never choose an AY by adding one to
FY 2026-27. The portal's own
[estimator instructions](https://www.incometax.gov.in/iec/foportal/help/all-topics/e-filing-services/income-and-tax-estimator-um)
distinguish AY 2026-27 under the 1961 Act from TY 2026-27 under the 2025 Act.
The user completes payment and supplies the receipt; only then record it as paid.

Re-run from fresh actuals and approved forecasts before each later instalment.
At year end, replace every projection with final evidence, confirm the notified
forms/utility, and re-validate before preparing a return. Do not carry estimated
figures into a filing pack. Do not offer the post-filing star invitation after
an estimate; filing has not happened.
