# Portal walkthrough - submitting the return on incometax.gov.in

When to read this: at the FINAL step, after the engine has computed tax, the regime is chosen, and `output/filing-pack.md` exists. This file covers both filing routes, the portal's known traps, and the hard stop before submission.

**Year/purpose guard:** these routes are for FY 2025-26 / AY 2026-27 under the
1961 Act only. Advance-tax estimates use [advance-tax.md](advance-tax.md).
For FY 2026-27 / TY 2026-27 under the 2025 Act, verify the notified form,
utility and official field mapping before filing. These screen notes do not
establish that the future-year portal works. If unavailable, stop at annual
computation. See [rates-fy2026-27.md](rates-fy2026-27.md).

## Ground rules

- The user logs in at https://eportal.incometax.gov.in themselves. NEVER see, ask for, type, or relay a password or OTP. Ask the user to reach the dashboard, then continue.
- Narrate steps for the user to perform. Only drive a browser yourself if the user explicitly asks AND a browser tool is available - and even then the login, payment, submit, and e-verify screens belong to the user alone.
- Compute first, then fill. Every number entered comes from `output/filing-pack.md` (which comes from `scripts/tax_engine.py`). The portal never gets to be the calculator.
- Before starting, confirm: AIS/26AS were re-downloaded recently (prefill and AIS are dynamic; early downloads miss late TDS/SFT entries), and the refund bank account is pre-validated (Profile -> My Bank Account). An unvalidated account is a common cause of refund failure.

## Route A - Online portal (recommended for ITR-1/4; works for ITR-1 to 4)

1. **Navigate**: e-File -> Income Tax Returns -> File Income Tax Return -> AY 2026-27 -> mode "Online" -> Individual -> select the ITR form already decided in the filing pack (do not let the portal's "Help me decide" override it) -> reason for filing (normally s.139(1), on/before due date).
2. **Prefill check**: the portal pre-fills from AIS/26AS/employer filings. Verify EVERY prefilled figure against the filing pack. Our reconciled numbers win - prefill can be stale or wrong - but never override silently: if prefill differs, first investigate why (missed income source? stale prefill? duplicate AIS entry?). If the difference is real income we missed, go back and re-run the engine; do not absorb it at the portal.
3. **Fill schedule by schedule**: open Return Summary / "Select Schedule", walk each schedule in the filing pack's portal-mapping table, enter values, and click **Confirm** on each. Typical order: personal info -> gross income schedules (Salary, HP, CG, OS, presumptive) -> deductions (VI-A) -> taxes paid (TDS/TCS/Schedule IT) -> Part B-TI -> Part B-TTI.
4. **Validate**: "Proceed to Verification" runs Upload Level Validation. Fix every listed defect (catalogue below) and re-run until it reports **0 errors**. Category-A defects block upload; do not proceed with any error outstanding.
5. **Preview cross-check**: download/open the PDF preview (and the return JSON if offered - the JSON is the authoritative artifact). Reconcile to the rupee against the engine output: total income per head and `total_income`; `slab_tax` + each special-rate line (s.111A, s.112A, s.112, s.115BBH); `rebate_87a`; surcharge; 4% cess; `total_tax_liability`; interest 234A/234B/234C and fee 234F; TDS + advance tax + self-assessment challans; `final_payable_or_refund`. A gap of a few rupees on rounded lines is acceptable only if explained by s.288A/288B nearest-10 rounding (the engine rounds the same way). Any other gap: stop and find it before the user submits.
6. **STOP - handoff**. The user alone performs the three final acts:
   - **Pay**: if tax is payable, "Pay Now" (e-Pay Tax). After payment, verify the challan (BSR code, date, serial no., amount) landed in Schedule IT, re-confirm Taxes Paid, and check Part B-TTI "Amount payable" is Rs 0 (few-rupee 288B gap is fine).
   - **Submit**: the user clicks the final submit/verification button.
   - **e-Verify**: within **30 days** to preserve the upload date. Verification after 30 days becomes the filing date and attracts applicable late-filing consequences. A return never verified is invalid. Aadhaar OTP (mobile linked to Aadhaar) is usually the fastest option; net-banking/bank-EVC also work. Tell the user the deadline explicitly.

## Route B - Offline utility + JSON upload

Use when the online SPA is unusable (deadline-week slowness, complex ITR-2/3) or the user prefers it.

1. Download the official utility for the chosen form from incometax.gov.in -> Downloads -> Income Tax Returns (Windows/Mac utility or Excel utility; the JSON schema and validation rules are published on the same page).
2. On the portal, download the prefilled-data JSON (offered in the File ITR flow) and import it into the utility.
3. Enter the filing-pack values schedule by schedule, run the utility's own validation to zero errors, then "Generate JSON".
4. Upload: e-File -> Income Tax Returns -> File ITR -> AY 2026-27 -> Offline mode -> upload the JSON.
5. Same preview cross-check (step A5) and the same hard stop (step A6) apply. Uploading the JSON is not filing - the user still verifies, submits, and e-verifies.

## Portal quirks (Angular SPA field notes)

The filing UI is a single-page Angular app with repeatable traps. If driving a browser, obey all of these; if narrating, warn the user about the starred ones.

- **Prefer DOM/JS clicks over coordinates.** Scroll drift between screenshot and click makes coordinate clicks hit the wrong schedule row. Locate the target `li.list-group-item` by matching its text, then click its confirm/label element via `querySelector` - never click by pixel position.
- ***Trailing-zero input bug.** Amount fields arrive pre-filled with `0`; typing `22930` can produce `229300`. Always clear the field first (triple-click or Ctrl+A, Delete), then type.
- **mat-select dropdowns ignore mouse clicks.** For Angular Material dropdowns (nature of employer, business code, etc.): focus the control, then ArrowDown to the option and Return.
- ***Schedules silently un-confirm.** Editing any upstream schedule (Salary, Part A-BS, ...) flips Part B-TI / Part B-TTI back to "Provide your confirmation" without warning. After ANY edit, walk down and re-confirm every downstream schedule (including AMT/AMTC if prompted) before validating.
- **Logout popup on direct URL navigation.** Navigating by URL triggers "Are you sure you want to Logout?" - answer No; prefer breadcrumb links, which navigate cleanly.
- **Auto-added schedules with mandatory blanks.** The questionnaire may add schedules (e.g. ESOP) with mandatory fields that don't apply. Remove them via "Select Schedule"; use "Skip Questions" so the wizard doesn't re-add them or reset earlier answers.
- ***Session timeout.** Long sessions log out mid-fill. The user logs in again and clicks **Resume Filing**; verify the in-progress data survived before continuing.

## Validation-defect catalogue

Common Upload Level Validation errors and their fixes:

- **"Nature of employer" blank**: mandatory dropdown in Schedule Salary - set "Others" for private-sector employment (pick the matching government category otherwise).
- **Blank Rs 0 perquisite / profit-in-lieu rows**: auto-created s.17(2)/17(3) rows with empty mandatory dropdowns fail validation - delete the empty rows rather than filling them.
- **Presumptive income > 0 but Part A-BS Sl.No 6 empty** (ITR-3/4 with 44AD/44ADA): fill the no-books balance sheet at item 6 with a positive cash balance (net presumptive profit is a defensible figure; debtors/creditors/stock may be 0). Disclosure only - tax is unchanged.
- **Refund but bank account not pre-validated**: pre-validate under Profile -> My Bank Account and nominate it for refund; PAN-Aadhaar-bank name mismatches also block refund credit.

Fix, re-validate, repeat until 0 errors. Never suppress a defect by inventing a value - every fix must be a true fact about the user.

## Post-filing

- **Acknowledgement**: after submission, have the user download the ITR-V / acknowledgement (ACK number) from e-File -> Income Tax Returns -> View Filed Returns. Save it with the filing pack.
- **e-verification confirmation**: confirm status shows "Successfully e-Verified". If pending, remind the user of the 30-day window. Late verification changes the filing date; a return never verified is invalid. For a belated return, recommend submitting and verifying by 31 December 2026. [Official verification FAQ](https://www.incometax.gov.in/iec/foportal/help/all-topics/e-filing-services/itr-v-faqs30-days-timeline-e-verification-returns-faq).
- **s.143(1) intimation**: CPC will process the return and email an intimation comparing the filed figures with its computation. If our numbers were verified to the rupee at preview, expect "no demand, no refund" or the computed refund. A mismatch there usually means a TDS-credit mismatch (26AS vs claimed) or a CPC adjustment - reconcile the intimation line-by-line against the engine output before the user pays any demand or accepts a reduced refund; a wrong demand can be contested (rectification u/s 154 or revised return).
- **Missed or wrong filing - deadlines (AY 2026-27)**. Re-check [the rate card](rates-fy2025-26.md) and [official updates](https://www.incometax.gov.in/iec/foportal/latest-news):
  - Original non-audit due dates: 31 July 2026 without business/profession; 31 August 2026 with business/profession. Verify taxpayer status rather than choosing a date from the form number.
  - Belated return s.139(4): up to **31 December 2026**, with 234F fee (Rs 5,000; Rs 1,000 if total income <= 5,00,000), 234A interest, and loss of carry-forward for most losses (house-property loss and unabsorbed depreciation survive). Regime-choice restrictions for belated filers exist - (verify on the portal before relying on this).
  - Revised return s.139(5): up to **31 March 2027**, or assessment completion if earlier. From 1 January, s.234I fee is ₹1,000 up to ₹5L total income and ₹5,000 above it. Revised-return workflow/fees are not modelled. Source: [ITR-2 FAQ](https://www.incometax.gov.in/iec/foportal/help/all-topics/e-filing-services/itr-2/itr-2-faqs).
