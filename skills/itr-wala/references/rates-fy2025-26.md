# Rate card - FY 2025-26 (AY 2026-27), resident individuals

When to read this: while explaining a `tax_engine.py` result to the user, or answering "why is my tax X". **Never compute from this file** - `scripts/tax_engine.py` implements every rule below; this doc exists only so you can narrate its output accurately.

## Due dates (AY 2026-27), checked 3 October 2026

Finance Act 2026 split the non-audit deadline under s.139(1). The determinant
is the taxpayer's business/professional income and audit status, not the ITR
form number. See [Finance Act 2026 s.5](https://egazette.gov.in/WriteReadData/2026/271439.pdf).

| Filing | Deadline |
|---|---|
| No business/professional income, no audit | **31 Jul 2026** |
| Business/professional income, not liable to audit | **31 Aug 2026** |
| Audit cases (s.44AB), outside scope | 21 Nov 2026 (extended from 31 Oct) |
| Transfer pricing (s.92E) | 30 Nov 2026 |
| Belated return, s.139(4) | 31 Dec 2026; submit and e-verify by this date to avoid late verification crossing the cutoff |
| Revised return, s.139(5) | 31 Mar 2027 (extended by Finance Act 2026) |

- Audit extension: [CBDT Circular 07/2026 dated 28 September 2026](https://www.incometax.gov.in/iec/foportal/sites/default/files/2026-09/Circular-7-2026.pdf), audit report 21 October and return 21 November. Re-check official notifications before quoting any deadline; never carry an extension across years.
- Belated/revised limits are also subject to earlier assessment completion. Revisions from 1 January to 31 March 2027 attract s.234I fee ₹1,000 up to ₹5L total income, ₹5,000 above it. Revised-return workflow/fees are unsupported. Sources: [Finance Act s.5/16](https://egazette.gov.in/WriteReadData/2026/271439.pdf), [ITR-2 FAQ](https://www.incometax.gov.in/iec/foportal/help/all-topics/e-filing-services/itr-2/itr-2-faqs).
- **Belated return regime lock (s.115BAC(6)):** once the s.139(1) due date passes, a no-business taxpayer can no longer opt for the old regime - the utility enforces new-regime-only for belated returns. The engine detects `filing_date > due_date`, warns, and forces its recommendation to the new regime even when the old computes cheaper.
- Pass an explicitly verified `due_date`. The engine defaults to 2026-07-31 without business income, 2026-08-31 with supported presumptive income.

## NEW regime (s.115BAC - the default)

| Slab (total income at slab rates) | Rate |
|---|---|
| 0 - 4,00,000 | 0% |
| 4,00,001 - 8,00,000 | 5% |
| 8,00,001 - 12,00,000 | 10% |
| 12,00,001 - 16,00,000 | 15% |
| 16,00,001 - 20,00,000 | 20% |
| 20,00,001 - 24,00,000 | 25% |
| > 24,00,000 | 30% |

- Standard deduction (salary/pension): **75,000**.
- **s.87A rebate: max 60,000.** The ₹12,00,000 eligibility threshold uses TOTAL income, including special-rate gains. The rebate offsets slab-rate tax only. Salary up to ₹12,75,000 yields zero tax only with no other income affecting eligibility. Source: [Finance Act 2025 s.20](https://egazette.gov.in/WriteReadData/2025/262125.pdf), as corrected by [Finance Act 2026 s.161](https://egazette.gov.in/WriteReadData/2026/271439.pdf).
- **87A marginal relief:** above ₹12L total income, the deduction is total income-tax minus income exceeding ₹12L, capped at slab-rate tax. For slab-only income ₹12,10,000, tax before relief is ₹61,500, relief ₹51,500, then cess gives ₹10,400. With special income, tax need not fall to the excess because that deduction cannot absorb special-rate tax. Source: [s.87A amended by Finance Act 2025 s.20](https://egazette.gov.in/WriteReadData/2025/262125.pdf), as corrected by [Finance Act 2026 s.161](https://egazette.gov.in/WriteReadData/2026/271439.pdf).
- Deductions surviving in new regime: employer NPS **s.80CCD(2) at 14% of Basic+DA** (govt AND private, FY 2025-26). No 80C/80D/80TTA/HRA/LTA/s.24(b) self-occupied interest; house-property loss cannot be set off against other heads. The engine warns when it drops these.
- **Retirement exemptions survive the new regime**: gratuity s.10(10), commuted pension s.10(10A), leave encashment s.10(10AA), retrenchment s.10(10B), VRS s.10(10C) - s.115BAC withdraws only 10(5)/10(13A)/most 10(14)/10(17)/10(32). Schema field `salary.exempt_retirement`, deducted in BOTH regimes; `salary.exempt_allowances` (HRA/LTA) stays old-regime-only.

## OLD regime (opt-in; business income needs Form 10-IEA)

| Slab | <60y | Senior 60-79 | Super-senior 80+ |
|---|---|---|---|
| Nil up to | 2,50,000 | 3,00,000 | 5,00,000 |
| 5% band | 2.5L - 5L | 3L - 5L | - (no 5% band) |
| 20% band | 5L - 10L | 5L - 10L | 5L - 10L |
| 30% | > 10L | > 10L | > 10L |

- Standard deduction **50,000**; actual professional tax paid is deductible, without an invented ₹5,000 engine cap. Source: [s.16(iii), employment-tax deduction](https://www.incometaxindia.gov.in/w/employees-benefits-allowable). Amounts above ₹2,500 trigger a validator warning to check arrears or multiple-State payments, not a deduction cap: [Constitution Article 276(2)](https://www.indiacode.nic.in/bitstream/123456789/19151/1/constitution_of_india.pdf).
- **s.87A: 12,500 if total income ≤ 5,00,000** - a hard cliff, NO marginal relief (income 5,00,010 loses the entire rebate; the ≤ test is on the s.288A-rounded figure, so 5,00,004 still qualifies). Threshold tested on total income including special-rate income. Engine applies the rebate against all tax except: (a) 112A LTCG - statutory bar, s.112A(6); (b) VDA (115BBH) and winnings (115BB/BBJ) tax - no statutory bar, but no ruling supports the claim and the utility denies it, so the engine takes the safe posture and excludes them (with a warning). 87A **against 111A/112 tax is allowed in the old regime**: the Finance Act 2025 denial amended only the new-regime proviso, and Bombay HC (Chamber of Tax Consultants) plus ITAT rulings back the claim - but CPC has disputed it in processing and **CBDT Circular 13/2025 takes the department's side**, so the engine warns to verify the portal accepts the figure before filing.
- **Basic-exemption absorption order vs 87A:** when unused basic exemption can absorb special-rate gains AND the rebate is in play, no fixed order is always cheapest (111A/112 tax is rebate-eligible, 112A tax is not) - the engine tries every order and keeps the lowest lawful tax.
- Chapter VI-A caps the engine enforces: 80C 1,50,000; 80CCD(1B) 50,000; 80TTA 10,000 (<60y) / 80TTB 50,000 (seniors, savings+FD); 80CCD(2) at **10%** of Basic+DA for private employers under old regime (14% govt); s.24(b) self-occupied interest 2,00,000; house-property loss set-off vs other heads capped at 2,00,000 (s.71(3A)).
- **s.24(b) caveat:** the 2,00,000 self-occupied cap requires a loan taken on/after 1-Apr-1999 for purchase/construction completed within 5 years; for repair/renovation or pre-1999 loans the cap is **30,000**. The engine applies 2,00,000 and warns - confirm the loan purpose.
- **s.71 set-off order** (engine-implemented): house-property loss first absorbs the other slab heads; any remainder sets off against capital gains - highest-rate bucket first, against the **full 112A gain before its 1.25L exemption** (the exemption is a tax-stage threshold), and never against VDA or winnings (s.115BBH(2), s.58(4)); the unabsorbed balance carries forward (Schedule CFL - not tracked here, warned).

## Applied automatically in both regimes

- **Family pension, s.57(iia):** deduction of one-third of the pension, capped at **25,000** (new regime) / **15,000** (old regime) - the engine applies it to `other_sources.family_pension` and warns with the figure.
- **Relief u/s 89(1)** (salary arrears/advance): a transcribed figure from the Form 10E computation goes in top-level `relief_89`; the engine nets it after cess, which also shrinks the 234A/B/C base. **Form 10E must be e-filed before the return** or CPC disallows the relief.

## Surcharge and cess (both regimes)

The 10%/15% tiers are tested on TOTAL income; the 25%/37% tiers are tested on total income **excluding dividends and s.111A/112/112A income** (First Schedule clauses (c)/(d)):

| Test | Surcharge on income-tax |
|---|---|
| Total income > 50,00,000 | 10% |
| Total income > 1,00,00,000 | 15% |
| Income excluding dividend/CG > 2,00,00,000 | 25% |
| Income excluding dividend/CG > 5,00,00,000 | 37% old regime only - **new regime caps at 25%** |

- **Clause (e):** when total income crosses 2 crore only because of dividend/111A/112/112A income (the exclusive figure stays at or under 2cr), the surcharge is a **flat 15% on the entire tax** - never 25% on the salary side. The engine implements this.
- **15% surcharge ceiling** on tax attributable to dividends and capital gains u/s 111A/112/112A, regardless of total income. (Engine attributes top-slab-rate tax to dividends for this ceiling - an approximation it flags above 2 crore.)
- **Marginal relief on surcharge** at each threshold: the extra (tax+surcharge) over the tax at the threshold cannot exceed the income above the threshold. For the 25%/37% tiers the threshold is measured on the exclusive figure. Engine computes this.
- **Health & Education Cess: 4%** on (tax + surcharge), always, after rebate.

## Special rates

| Section | Income | Rate | Notes |
|---|---|---|---|
| s.111A | STCG, STT-paid equity/equity-MF (≤12m) | **20%** | post-23-Jul-2024 rate applies all FY |
| s.112A | LTCG, same assets >12m | **12.5% above 1,25,000** | exemption aggregates across all 112A gains for the FY; 31-Jan-2018 grandfathering still applies |
| s.112 | Other LTCG (property etc.) | **12.5%** no indexation | land/building bought on/before 22-Jul-2024: tax on that asset is CAPPED at 20% of the indexed gain (2nd proviso to s.112(1)(a)) - a tax-level cap, not a different gain figure. **Always feed the UNINDEXED gain** (that is what enters total income). The engine cannot apply the cap and warns; if 20% x indexed gain is lower, that asset needs the offline utility or a CA |
| s.115BBH | VDA/crypto | **30% flat** | cost of acquisition only; no loss set-off or carry-forward; no basic-exemption set-off; no 87A |
| s.115BB / s.115BBJ | Lottery, game shows, online-game winnings | **30% flat** | schema field `other_sources.winnings`; TDS arrives u/s 194B/194BA; no basic-exemption set-off, no deductions, no 87A; NOT excluded from the 25%-tier surcharge test and NOT under the 15% surcharge ceiling |

- Qualifying specified MF units bought on/after 1 Apr 2023 (s.50AA): always short-term, slab rate → engine's `stcg_slab` bucket.
- Residents may absorb unused basic exemption against 111A/112A/112 gains (never VDA). New regime absorbs highest-rate first; old regime evaluates the lawful orders because the rebate can change which is cheapest.
- Chapter VI-A deductions cannot be set against special-rate CG/VDA income (engine enforces).

## Interest and fees

- **s.234A** (late filing): 1% simple per month or part on the unpaid balance from the day after the due date, **stopping on amounts discharged by self-assessment payments at their payment date** and running on any remainder to the filing date. Nil if a refund is due or self-assessment tax was fully paid by the due date. The engine implements the payment-date stop for both 234A and 234B.
- **s.234B** (advance-tax default): applies only if assessed tax (liability − TDS/TCS) ≥ 10,000 AND advance tax paid < 90% of it. 1% per month or part on the shortfall from 1 Apr 2026 to payment/filing.
- **s.234C** (deferment): cumulative installments 15% / 45% / 75% / 100% by 15 Jun / 15 Sep / 15 Dec / 15 Mar. Shortfall charged 1% × 3 months (first three) or 1% × 1 month (March). Safe harbour: no Q1/Q2 interest if ≥12%/36% paid. Eligible timing exceptions are NOT modelled; quarterly data cannot be entered in the schema, so verify that part externally. Eligible presumptive 44AD/44ADA taxpayers use a single 100% March instalment even with other income. For estimates rather than return interest, use [advance-tax.md](advance-tax.md).
- **s.207(2) senior carve-out**: resident 60+ with no business/professional income owes no advance tax → no 234B/234C. Engine applies this automatically from `age_category`.
- **Rule 119A**: the base amount for 234A/B/C is rounded DOWN to a multiple of 100 before applying 1%.
- **s.234F late fee**: 5,000 if filed after the due date; **1,000 if total income ≤ 5,00,000**; nil if total income is below the basic exemption (mandatory-filing edge cases exist - verify on the portal before relying on this).

## Rounding

- **s.288A**: total income rounded to the nearest 10. **s.288B**: tax payable/refund rounded to the nearest 10. Engine rounds half-up (`_r10`); allow ±10 vs the portal at intermediate lines.

## Sources

- https://cleartax.in/last-date-to-file-itr · https://taxguru.in/income-tax/ay-2026-27-itr-due-dates-finance-act-2026.html
- https://cleartax.in/s/income-tax-slabs · https://1finance.co.in/blog/old-tax-regime-slabs-fy-2025-26/
- https://tax2win.in/guide/section-87a · https://taxguru.in/income-tax/tax-planning-fy-2025-26-understanding-rebate-rules-ltcg-section-112a-new-regime.html · https://taxguru.in/income-tax/section-87a-rebate-stcg-111a-tax-planning-fy-2025-26.html
- https://cleartax.in/s/marginal-relief-surcharge · https://www.incometaxindia.gov.in/w/tax-rates%E2%80%8B
- https://cleartax.in/s/long-term-capital-gains-ltcg-tax · https://tax2win.in/guide/calculate-capital-gains-tax-on-shares · https://cleartax.in/s/cryptocurrency-taxation-guide
- https://cleartax.in/s/interest-imposed-by-income-tax-department-under-section-234c · https://www.taxbuddy.com/blog/section-234b-234c-interest-calculation · https://cleartax.in/s/late-tax-return
- https://www.taxbuddy.com/blog/80ccd-2-in-new-tax-regime

**Reminder: every rupee figure shown to the user must come from `tax_engine.py` output. If this doc and the engine ever disagree, the engine wins - and file a bug.**
