# Advance tax for FY 2026-27

Read after confirming `financial_year` and `purpose: "advance_tax"` and completing
SKILL step 1, including the year/purpose workspace and .gitignore. This estimates
a payment; it does not file a return or certify historical interest. The user pays.

This can apply to salary with a withholding shortfall or additional rent, interest
or gains; investors and landlords; and eligible presumptive business/professional
income. Salary with sufficient employer TDS usually needs no extra payment.
Business support is limited to 44AD/44ADA, not ordinary business books, F&O or 44AE.
Source: [department tax-payment FAQ](https://www.incometax.gov.in/iec/foportal/help/all-topics/e-filing-services/tax-payments-faq).

## Interview and evidence

1. Confirm FY, residency, age and the as-of date. For a current payment after the
   FY ended, use return/self-assessment preparation instead. Historical engine
   estimates are for explicit retrospective analysis.
2. Collect current payslips/payroll projections, bank interest forecasts, realised
   broker gains, rent records, deduction proofs and paid challans. Final year-end
   certificates may not exist. Use the selected year's evidence and normal privacy
   and blind-extraction rules.
3. Ask for full-year expected income, eligible deductions and TDS/TCS. Transcribe
   forecasts from documents or numbers the user explicitly approves. Record each
   source, period, actual/estimated status and approval in `work/extraction-notes.md`.
   Never extrapolate or compute tax with the model. Derive any needed total with
   a deterministic script and show it for approval. Do not predict future sales.
4. Keep actual credits in `taxes_paid.tds/tcs` and actual document totals in
   `source_totals`; expected annual credits belong in `expected_tax_credits`.
   Keep YTD salary and payslip components in the source trail with their periods.
   The validator warns about differing salary periods during planning; annual
   Form 16 equality checks remain mandatory for return inputs. Never reduce an
   annual forecast to match YTD or prior-year salary. Expected withholding must
   be supportable: verify credit for income already paid without required
   withholding under old s.209 / new s.405.
5. Confirm presumptive eligibility: old 44AD/44ADA or new s.58(2), Table 1/3.
   Set `income.presumptive_section` to `44AD` or `44ADA` (stable identifiers for
   both years) and enter positive declared income, not turnover. A label with zero
   or absent presumptive income is rejected. Without the identifier, the engine
   uses quarterly targets and warns, except legacy FY 2025-26 presumptive-only
   files, which retain their single March instalment. 44AE is unsupported. Ask about
   business regime elections and withdrawals before comparing payment plans.

## Input and computation

Save `work/income.json` with `financial_year`, `purpose`, `as_of_date`, income,
deductions, expected credits and actual payments. Omit return dates and
self-assessment payments. Only advance-tax challans paid inside the FY on or
before the as-of date count. Do not record a planned payment as already paid.

Run the validator to exit 0, show warnings, then run the engine in text and JSON
modes. Save `output/computation.txt` and `output/computation.json`. Restate engine
figures verbatim. Review annual tax, credits, payments, dates and both regimes.
Confirm which regime the user can legally use and identify ONE payment plan;
the other is a comparison. A cheaper calculation does not establish eligibility
to change regimes. When both are legally available, present the recommended
regime's plan unless the user chooses the other one. Before a planned sale, warn
that special-rate gains can reduce the new-regime rebate or marginal relief when
total income exceeds ₹12 lakh. Recompute a user-approved scenario before the sale;
do not predict gains. See [the rebate correction](../../../docs/rebate-correction.md).

Standard cumulative targets are 15%, 45%, 75%, 100% by 15 June, 15 September,
15 December and 15 March. Eligible presumptive taxpayers use one 100% March
instalment even with other income (old s.211(1)(b)/234C(1)(b), new s.408(2)).
Resident seniors without business/professional income are exempt under s.403(3)
of the 2025 Act, not s.404. Section 404 sets the ₹10,000 threshold, s.405 governs
credits and s.408 the schedule.
Sources: [old advance-tax guidance](https://incometaxindia.gov.in/Tutorials/31.%20Provisions%20on%20pymt%20of%20adv.%20tax.pdf),
[amended 2025 Act](https://www.incometaxindia.gov.in/documents/d/guest/income_tax_act_2025_as_amended_by_fa_act_2026-pdf),
[2025 Act Gazette, ss.403/408](https://egazette.gov.in/WriteReadData/2025/265620.pdf),
[1961 Act ss.211/234C explained by CBDT, paragraph 72](https://www.incometaxindia.gov.in/documents/20117/6507196/Circular2_2018.pdf/61ce9ca1-09f6-df86-d049-0ded12a4ee08?t=1762868291859).
Portal/CPC instalment-interest calculations for presumptive plus other income
have not been checked.

The plan includes surcharge and cess but excludes future filing fees, historical
interest assessment and refunds. `shortfall_at_deadline` compares a target with
payments by its deadline; `paid_to_date` and `outstanding_now` include later payments
through the as-of date. The next payment skips covered targets and is absent when
fully paid. After 15 March, an unpaid balance is labelled a 31 March top-up.
This does not cure missed-instalment interest. The engine does not model the
s.234C / s.425 exception for capital gains or dividends received during the year,
so instalment interest can be overstated. Use dated evidence and the official
computation or a CA.

## Handoff and revisit

Save `output/estimate-pack.md`: FY/TY, Act, as-of date, approved inputs, source
trail, chosen regime, comparison, next amount/date and assumptions. Update
`work/progress.md`. Verify the government payment screen's year, Act and
advance-tax category before the user pays. Never invent an AY for FY 2026-27:
the [official estimator instructions](https://www.incometax.gov.in/iec/foportal/help/all-topics/e-filing-services/income-and-tax-estimator-um)
distinguish AY 2026-27 under the 1961 Act from TY 2026-27 under the 2025 Act.
Only record a payment after the user supplies its receipt.

Revisit actuals and approved forecasts before each instalment. At year end,
create the separate return workspace, replace projections with final evidence,
verify notified forms and revalidate. Never carry estimates into a filing pack.
The star invitation remains post-filing only; do not offer it after an estimate.
