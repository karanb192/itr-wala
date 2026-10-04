# Rate card: FY / Tax Year 2026-27, resident individuals

Income earned 1 April 2026 to 31 March 2027 uses the Income-tax Act, 2025.
Use `financial_year: "2026-27"`. The engine reports `tax_year: "2026-27"`
and `ay: null`; do not label this AY 2027-28. FY 2025-26 remains AY 2026-27
under the 1961 Act. The government
[estimator manual](https://www.incometax.gov.in/iec/foportal/help/all-topics/e-filing-services/income-and-tax-estimator-um)
makes the same distinction.

Read to explain engine output, never to do arithmetic. Verified against the
[2025 Act amended by Finance Act 2026](https://www.incometaxindia.gov.in/documents/d/guest/income_tax_act_2025_as_amended_by_fa_act_2026-pdf), with the [original 2025 Act Gazette](https://egazette.gov.in/WriteReadData/2025/265620.pdf) as a fetchable companion,
the enacted [Finance Act 2026](https://egazette.gov.in/WriteReadData/2026/271439.pdf),
and [Act 21 of 2026](https://egazette.gov.in/WriteReadData/2026/275521.pdf).
If the consolidated PDF is unavailable, read the [original Act gazette](https://egazette.gov.in/WriteReadData/2025/265620.pdf)
together with those two amendments; the original alone is not the current law.
The August amendment changes fund/foreign-entity and business-trust provisions,
not the resident-individual slabs used here. Business-trust distributions need
separate classification and are outside this workflow.

## Supported computation rules and statutory counterparts

The covered numerical rates match FY 2025-26. The dates and legal labels differ.
Input/output field names containing 1961 Act section numbers remain stable
schema identifiers; `sections` and the rendered output identify the applicable law.

| Covered rule | TY 2026-27 law | Engine treatment |
|---|---|---|
| New slabs | s.202(1) | Up to ₹4L nil; ₹4-8L 5%; ₹8-12L 10%; ₹12-16L 15%; ₹16-20L 20%; ₹20-24L 25%; above ₹24L 30% |
| New rebate | s.156(2)/(3) | Total income up to ₹12L; rebate up to ₹60,000 against slab tax only. Special-rate income counts towards eligibility. Marginal relief uses total tax minus income above ₹12L, capped at slab tax |
| Old slabs | Finance Act 2026 s.3(1), First Schedule Part I-B, Paragraph A; Part III for advance tax | Nil up to ₹2.5L / ₹3L / ₹5L by age; 5% up to ₹5L where applicable, 20% ₹5-10L, 30% above ₹10L |
| Old rebate | s.156(1), s.198(7) | ₹12,500 up to ₹5L total income; no rebate against equity LTCG. Existing conservative VDA/winnings exclusion and special-gain portal warning remain |
| Salary deductions | s.19(1), Table 1/2; s.202(2) | ₹75,000 standard new, ₹50,000 old; actual professional tax old only; eligible retirement exemptions both |
| Employer NPS | s.124(1)/(2) | 14% basic+DA new; 10% old for private employers. Government old-regime 14% is not modelled; flag it |
| Personal NPS, savings, health | s.124(3), s.123, s.126 | Old-only ₹50,000 personal NPS; ₹1.5L savings cap; health/other eligible amounts supplied with evidence, not automatically determined |
| Deposit-interest deduction | s.153(2) | Old-only ₹10,000 savings interest for regular individuals, ₹50,000 eligible deposits for seniors |
| House property | s.21(7), s.22(1)/(2), s.109(1)(b); s.202(2) | At most two self-occupied houses; 30% net annual value deduction; old self-occupied interest and inter-head loss cap ₹2L; new inter-head loss prohibited. Repair/pre-1999 loans require separate review |
| Family pension | s.93(1)(d) | One-third deduction, capped ₹25,000 new / ₹15,000 old |
| Salary-arrears relief | s.157 | Transcribed eligible relief after cess; verify prescribed form before claiming |
| Equity STCG | s.196 | 20%, with resident unused-basic-exemption adjustment |
| Equity LTCG | s.198 | 12.5% above aggregate ₹1.25L; exemption does not remove gains from total-income threshold tests |
| Other LTCG | s.197 | 12.5% without indexation; property tax-cap exception is unsupported |
| VDA / winnings | s.194(1), Table 4 / Tables 1,5 | 30%; no basic-exemption absorption; no new rebate against this tax |
| Surcharge / cess | Finance Act 2026 s.3(4)(b), Table Sl.10; s.3(15); First Schedule Part I-B | 10/15/25/37% old, new capped at 25%; 15% dividend/CG tax ceiling; marginal relief; 4% cess. Existing proportional-mixture approximation is warned |
| Rounding | s.516 | Nearest ₹10, half-up, for total income and payable/refundable amount |

Statutory source for the table: [amended Act](https://www.incometaxindia.gov.in/documents/d/guest/income_tax_act_2025_as_amended_by_fa_act_2026-pdf)
and [Finance Act 2026](https://egazette.gov.in/WriteReadData/2026/271439.pdf).
See the [deduction interview](deductions-checklist.md) for evidence questions.
It retains legacy section labels; verify the 2025 Act counterpart before quoting
a claim or form. No new unsupported deduction is implied by adding a year.

## Advance tax now

Use `purpose: "advance_tax"` with an explicit as-of date inside the FY.
The engine calculates annual estimated tax less full-year expected TDS/TCS,
then cumulative targets and the next payment after actual paid challans.
It does not calculate future filing interest/fees or an estimated refund.

| Standard cumulative target | Due date |
|---|---|
| 15% | 15 June 2026 |
| 45% | 15 September 2026 |
| 75% | 15 December 2026 |
| 100% | 15 March 2027 |

Eligible s.58(2), Table 1/3 presumptive taxpayers pay 100% by 15 March, including
those with other income. Seniors with no business/profession are exempt; net
liability below ₹10,000 requires no advance tax. Payments by 31 March count
as advance tax but do not erase instalment default. Source:
[s.403(3) exemption, s.404 threshold, s.405 credits and s.408 schedule](https://www.incometaxindia.gov.in/documents/d/guest/income_tax_act_2025_as_amended_by_fa_act_2026-pdf),
[2025 Act Gazette](https://egazette.gov.in/WriteReadData/2025/265620.pdf).
Follow [advance-tax.md](advance-tax.md) for forecasts, credits and handoff.

## Annual return preparation after year end

The statutory dates under s.263 are in the year after the income year ends:

| Taxpayer / return | Statutory date |
|---|---|
| No business/profession, no audit | 31 July 2027 |
| Business/profession without audit | 31 August 2027 |
| Audit | 31 October 2027, outside scope |
| Transfer pricing | 30 November 2027, outside scope |
| Belated | 31 December 2027, or assessment completion if earlier |
| Revised | 31 March 2028, or assessment completion if earlier; workflow unsupported |

Verify extensions live. The engine defaults the original due date from business
status and accepts an explicit verified `due_date`. Return computations use
s.423/424/425 interest and s.428(a) late fee, with the same numerical conventions
as the earlier year. Historical deferment interest still needs timing exceptions
checked separately. Revised-return fees under s.428(b) are not modelled.
Source: [s.263 and ss.423-428](https://www.incometaxindia.gov.in/documents/d/guest/income_tax_act_2025_as_amended_by_fa_act_2026-pdf).

Annual tax computation is supported. The bundled form selector and portal guide
cover AY 2026-27 for FY 2025-26. Do not reuse them for TY 2026-27. Before filing,
verify notified forms, the official utility and its field mapping. Until those
are available and checked, deliver a computation only, not a portal filing pack.

## Changed transactions that require a separate review

- Buybacks from 1 April 2026 return to capital-gains treatment, with additional
  promoter provisions under s.69. Do not put these proceeds in dividends or
  assume the normal CG buckets capture the promoter rules. Buybacks remain
  outside the supported workflow.
- SGB redemption exemption under s.70(1)(x) requires continuous holding from
  the date of original issue until maturity. Do not import a blanket
  exemption from the earlier year. SGB exemption classification is unsupported.
- Loss carry-forwards, foreign income, RNOR/NRI, F&O/intraday, audit, property
  indexation caps and business-trust distribution classification remain out
  of scope. Government NPS and statutory income-timing exceptions still need
  external verification where the engine cannot express the facts.

Sources: [Finance Act 2026 s.35(b)(A) removes buyback dividend treatment; s.42 changes s.69; s.43 changes SGB exemption](https://egazette.gov.in/WriteReadData/2026/271439.pdf)
and [August amendment](https://egazette.gov.in/WriteReadData/2026/275521.pdf).
