# Documents Guide - Sourcing and Reconciliation

When to read this: at the start of every filing session, before extracting a single number - it tells you which documents to ask for, where the user downloads each one, and the reconciliation rules that gate `income.json`.

## Core principle

One number per income head, each tied to a source document. Never accept a figure the user "remembers". You extract; `validate_income.py` cross-checks; `tax_engine.py` computes. Fill `source_totals` (form16_gross_salary, form16_total_tds, form26as_total_tds, ais_total_tds, ais_savings_interest, ais_dividends) verbatim from documents - leaving it empty downgrades every guarantee the validator gives (it will warn).

## The documents

### 1. AIS - Annual Information Statement (with TIS summary)
- WHAT: the department's wide feed of everything reported against the PAN - interest, dividends, securities/MF transactions (SFT), salary, TDS/TCS. TIS is the aggregated summary the portal uses for prefill.
- WHERE: e-filing portal login (incometax.gov.in) → **AIS tab** → redirects to the AIS portal → download. Formats: **JSON and PDF - both are encrypted** (see DECRYPTING, below). A CSV export also exists (verify on the portal before relying on this). There is also an AIS mobile app and an offline **AIS Utility** - a viewer: it imports the encrypted JSON and supports feedback, but does not export usable data, so it is not a substitute for decrypting the file.
- **DECRYPTING THE DOWNLOAD.** The `.json` file is not JSON - it is base64-wrapped AES ciphertext, and nothing reads it as-is. Run `scripts/decrypt_ais.py`, which prompts for PAN and DOB without echoing them and writes plaintext JSON. The scheme:
  - `file     = IV(32 hex chars) || salt(32 hex chars) || base64(ciphertext)`
  - `password = PAN || "GQ39%*g" || DDMMYYYY`
  - `key      = PBKDF2-HMAC-SHA256(password, salt, 1000 iterations, 32 bytes)`
  - `cipher   = AES-256-CBC, PKCS7 padding`

  The literal `GQ39%*g` wedged between PAN and DOB is why a plain PAN+DOB password always fails. Sources disagree on PAN case; the script tries both. The **PDF** uses a *different* password - **PAN lowercase + ddmmyyyy**, no separator - and opens with `qpdf --password=... --decrypt`.
- **Never paste an AIS file into a web decryption tool.** Several exist. They are third-party pages that would receive the taxpayer's entire financial year in one upload. Decrypt locally.
- WHY: it is the department's view of the user's income - anything here that the return omits is notice bait. Feeds `source_totals.ais_*` and helps discover income the user forgot. **Strongly prefer the JSON download over the PDF** - AIS PDFs are often image/OCR-only and digit-level OCR errors are the top extraction hazard.
- SFT codes in AIS are authoritative evidence for equity vs non-equity fund classification: **SFT-18-EMF / SFT-17-LES → equity-oriented (s.111A/s.112A rates)**; **SFT-18-OTU → non-equity (slab / s.112)**. Traps: arbitrage funds ARE equity-oriented; balanced-advantage and liquid funds are NOT; switch-outs count as redemptions.

### 2. Form 26AS - Tax Credit Statement
- WHAT: every TDS/TCS entry against the PAN, with deductor TAN and section (192 salary, 194A interest, 194C contract, 194J professional, 194S VDA…), plus advance/self-assessment tax challans.
- WHERE: e-filing portal → **e-File → Income Tax Returns → View Form 26AS** → redirects to TRACES → download (PDF/text).
- WHY: the ONLY document against which TDS credit may be claimed. Feeds `taxes_paid.tds` and `source_totals.form26as_total_tds`. The validator hard-errors if TDS claimed exceeds the 26AS total.

### 3. Form 16 (one per employer)
- WHAT: employer's TDS certificate. **Part A**: TDS deposited quarter-by-quarter. **Part B**: salary breakup - s.17(1) salary, 17(2) perquisites, 17(3) profits in lieu - exempt allowances, and the regime the employer used.
- WHERE: from each employer (HR/payroll portal or email). Users who switched jobs need one from EVERY employer of FY 2025-26.
- WHY: feeds `salary.form16_17_1/2/3`, `salary.gross`, `exempt_allowances`, `professional_tax`, `basic_plus_da` (enables the 80CCD(2) cap check), and `source_totals.form16_gross_salary/form16_total_tds`. The validator hard-errors if 17(1)+17(2)+17(3) ≠ gross.

### 4. Broker tax P&L (capital gains)
- WHAT: realised STCG/LTCG per scrip with buy/sell dates, cost, sale value, STT flag; usually splits equity vs debt vs intraday vs F&O.
- WHERE: **Zerodha: Console → Reports → Tax P&L** (select FY 2025-26). Groww and Upstox have equivalent tax P&L reports under their reports section. Collect one per broker the user traded on.
- WHY: feeds `capital_gains.stcg_111a / ltcg_112a / ltcg_other / stcg_slab`. The 1,25,000 s.112A exemption aggregates across ALL brokers, so every broker's report is needed. Cross-classify fund gains against AIS SFT codes (above).

### 5. Mutual fund statements (CAMS / KFintech)
- WHAT/WHY: capital-gains statements for MF redemptions outside a broker. Watch for the same redemption appearing in both a broker P&L and a CAMS/KFintech statement - count it once.

### 6. Bank interest certificates / statements
- WHAT: per-bank interest certificate (net banking → deposits/statements section) or, failing that, the statement with interest credit lines totalled.
- WHY: ground truth for `other_sources.savings_interest` and `fd_interest`, and for tracing that platform/freelance payouts actually landed. Needed from EVERY bank - AIS can miss small banks. The validator warns when a salaried filer reports zero bank interest.

### 7. Deduction proofs (old regime only, plus 80CCD(2))
- WHAT: 80C (LIC/PPF/ELSS/tuition receipts, max 1,50,000), 80CCD(1B) NPS (50,000), 80D health insurance receipts, home-loan interest certificate for s.24(b) (2,00,000 self-occupied cap), rent receipts for HRA, 80G donation receipts, 80TTA/80TTB. Employer NPS 80CCD(2) works in the NEW regime too (14% of Basic+DA) - check Form 16/payslips even for new-regime filers.
- WHY: feeds `deductions.*`. Never enter a deduction without a proof document or the user's explicit confirmation that proof exists.

### 8. Tax payment challans
- WHAT: counterfoils for any advance tax / self-assessment tax paid (CIN, **date**, amount). Also visible in 26AS/AIS.
- WHY: feeds `taxes_paid.advance_tax` / `self_assessment` - the engine needs the DATE of each payment to compute s.234B/234C interest correctly.

## Timing: AIS is dynamic

AIS/26AS keep filling in after year-end - Q4 TDS filings land after May 31, and SFT entries trickle in later. **Re-download AIS, 26AS, and the portal prefill JSON shortly before filing.** A prefill or AIS pulled in April/May will miss late TDS and SFT entries; filing from stale prefill is a known notice-generator.

## Reconciliation rules (hard rules - do not proceed past a failure)

1. **One number per head, one source per number.** Build a small table: every rupee in `income.json` traces to a named document. If a number cannot be sourced, stop and find the source.
2. **TDS claimed must reconcile to 26AS.** Claiming more than the 26AS total is a validator ERROR and a guaranteed CPC mismatch. Small gaps vs Form 16/AIS (multiple deductors, timing) must be explained before filing.
3. **AIS-visible income must be declared** - even if the user "forgot" it or disputes remembering it. Omitting income the department can already see is under-reporting territory (s.270A penalty exposure). The validator hard-errors when AIS interest/dividends exceed what the return reports.
4. **Income missing from AIS must STILL be declared.** A small bank below the reporting threshold, a foreign platform payout - absence from AIS is not permission to omit. Tax is on actual income, not on what got reported.
5. **A 26AS TDS entry implies income exists somewhere.** Find the corresponding receipt and put it in the right head; never claim the TDS credit while dropping the income.
6. **AIS entry the user says is genuinely wrong** (duplicate, joint-account attribution, not theirs): do not silently drop it - the user should submit a response through the **AIS feedback mechanism** on the AIS portal (per-entry "feedback" option), then declare the correct figure. Record the discrepancy and the feedback submitted.
7. **De-duplicate before totalling**: the same payout seen by two reporters, the same FD interest reported twice after a bank merger, the same MF redemption in broker + CAMS. And check gross vs net: AIS interest entries are sometimes net of TDS while the taxable figure is gross.
8. **Foreign-platform money received in INR in India** is ordinarily Indian-source business/professional income for a resident - not "foreign income" merely because the payer is abroad. Cross-tie payout totals to bank credits. Any genuine foreign asset (RSUs, foreign brokerage) forces Schedule FA → at least ITR-2, and is a stop-and-escalate.
9. **Exclude AIS rows flagged `Inactive`.** AIS keeps superseded entries alongside the corrections that replaced them. Sum **only** rows with `Status = Active`. Including inactive rows inflates income and - far worse - **inflates the TDS claim**, and an overstated TDS claim is a guaranteed CPC mismatch rather than a rounding quibble. Always cross-check a computed total against AIS's own derived amount for that category; a gap usually means inactive rows crept in.

## Watch for these - the top 10 filer mistakes

1. AIS/26AS vs return mismatch → CPC notice, refund hold. Reconcile Form 16 + 26AS + AIS + bank/broker before filing.
2. Wrong regime chosen without computing both - always run the engine on both; old regime with business income needs Form 10-IEA.
3. Omitted savings/FD/RD interest and dividends not in Form 16 - the single most common miss.
4. RSU/ESOP confusion: vest = salary perquisite (employer TDS), sale = capital gains from vest-date FMV; foreign tax credit needs Form 67 BEFORE the ITR; Schedule FA required even with no sale.
5. Missed 80CCD(2) - valid in the new regime but often absent from prefill if the employer misreported.
6. Wrong ITR form (e.g. ITR-1 with STCG or foreign assets) → defective-return notice u/s 139(9).
7. Bank account not pre-validated / PAN-Aadhaar-bank name mismatch → refund failure.
8. Filing from stale prefill/AIS downloaded early in the season (see Timing above).
9. Forgetting e-verification - 30-day window after submission, else the return is invalid.
10. Capital-gains rate-period errors: mixing pre/post 23-Jul-2024 rate logic, missing the 1,25,000 s.112A exemption aggregation across brokers, or missing the buyback deemed-dividend + capital-loss twin entries.
