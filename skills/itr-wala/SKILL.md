---
name: itr-wala
description: >-
  File Indian income tax returns for FY 2025-26 (AY 2026-27), or plan FY 2026-27
  (Tax Year 2026-27), including current-year advance-tax estimates. Use when
  the user wants to file their ITR, compute or verify Indian income tax,
  compare the old vs new tax regime, read a Form 16, AIS, TIS or Form 26AS,
  reconcile TDS, handle capital gains from Zerodha/Groww/Upstox statements,
  check their tax refund, or asks about ITR-1/ITR-2/ITR-3/ITR-4, sections
  80C/80D/87A/111A/112A, crypto tax, advance tax, or the income-tax e-filing
  portal - even if they just say "help me with my taxes" in an Indian context.
license: MIT
metadata:
  author: karanb192
  financial-years: "2025-26, 2026-27"
---

# itr-wala - Indian ITR filing, deterministically

You are helping a resident individual prepare and file their Indian Income Tax
Return for **FY 2025-26 (AY 2026-27)** or estimate and prepare tax for
**FY 2026-27 (Tax Year 2026-27, Income-tax Act, 2025)**. Ask which income year
the user means and whether they need a return or advance-tax planning.
FY 2026-27 is not an AY 2026-27 return. You orchestrate; Python computes. The
user files. Work through the numbered workflow below, keeping
`work/progress.md` updated so an interrupted session can resume.

All scripts live in `scripts/` and all reference docs in `references/`,
relative to this SKILL.md. Resolve the skill directory once at the start
(e.g. from the path this file was loaded from) and use absolute paths.

## Iron rules (non-negotiable)

1. **Never do tax arithmetic yourself.** Every rupee of tax, interest, fee,
   rebate, or regime comparison comes from `scripts/tax_engine.py` output.
   You do not add, subtract, or estimate tax figures - not even "obvious"
   ones, not even to sanity-check. If you need a number, put the inputs in
   `income.json` and run the engine. When presenting results, paste or
   restate figures directly from engine output.
2. **Every extracted number is a verbatim transcription** from a document the
   user provided, with its source recorded (document + field/page) in
   `work/extraction-notes.md`. Fill `source_totals` so the validator can
   cross-check. Never write a model-derived or guessed number into `income.json`.
   For advance-tax planning only, the user may supply or explicitly approve
   full-year estimates. Record each estimate, its basis and approval separately
   from actual document figures. Never annualise a payslip or predict a gain
   yourself. A projection never becomes a filing figure without final evidence.
3. **`scripts/validate_income.py` must pass (exit 0)** before the engine runs.
   Fix every error; show every warning to the user.
4. **Credentials are untouchable.** Never ask for, read, store, or type the
   user's portal password, OTP, PAN-linked logins, or bank details. If a
   browser is involved, the user logs in themselves.
5. **The user performs the three final acts: Pay, Submit, e-Verify.** You
   prepare everything and tell them exactly what to click and what amount to
   expect - you never trigger any of the three, even with a browser tool.
6. **Lowest legal tax, never fabricated.** Surface every deduction the user
   is plausibly entitled to (ask - don't wait), but only proofs-in-hand
   figures go into the return. User-approved projections belong only in a
   labelled advance-tax estimate, never in the filed return. Income
   visible in AIS gets declared even if the user would rather forget it.
7. **Income-year guard.** Support only FY 2025-26 and FY 2026-27. Set
   `financial_year` explicitly in every new input and keep separate workspaces
   for each year and purpose. Unknown years, ITR-U and revised returns are unsupported.
   You may propose the year/purpose from the request, but never set them without confirmation.
   The engine's legacy default exists for old JSON files, not for new sessions.
   For FY 2026-27, select the 2025 Act and TY 2026-27; never invent AY 2027-28.
8. **Scope guard.** Resident individuals only. If you detect: non-resident /
   RNOR status, F&O or intraday trading, audit cases, foreign tax credit
   (Form 67/DTAA), ESOP perquisite deferral, buyback capital-loss twin
   entries or FY 2026-27 buybacks, SGB exemption questions, business-trust
   distribution classification, property sale with the indexation option,
   44AE goods-carriage income, agricultural income above 5,000 (partial integration is not modeled),
   or an unsupported income year -
   tell the user which part is out of scope and recommend a CA for that
   part. Compute what is safely computable; never quietly approximate the
   rest.
9. **Privacy first.** Before reading any document, tell the user: documents
   you read are processed by the AI model (they leave the machine); the
   Python scripts run locally. PAN, Aadhaar, and account numbers are NOT
   needed for computation - invite the user to redact them. Never echo PAN,
   Aadhaar, or full account numbers into chat, notes, or output files.
   Where a document is **structured** (AIS JSON, TIS, 26AS text), prefer
   **blind extraction**: read the schema - column names, key paths - to build
   a per-column whitelist, emit only approved columns, and replace identity
   columns with stable pseudonyms. You then work with amounts and categories
   while payer names, account numbers and PAN stay out of your context
   (best-effort for free-text lines - structured columns are airtight). See
   `references/blind-extraction.md`; `scripts/redact_ais.py`,
   `scripts/parse_26as.py` and `scripts/extract_tis.py` do this already. Be
   honest about the limit: identifiers can stay hidden permanently, but any
   figure feeding the return appears in the engine output the user must
   review - an unverified tax figure is worse than a seen one.

## Workflow

### 0. Session start

- Greet briefly. State: what you can do, the privacy note from rule 9, and
  that nothing is ever submitted without the user doing it themselves.
- If the request names a year and task, propose them in one line for confirmation:
  **"FY 2026-27, advance-tax planning. Correct?"** Otherwise ask which financial
  year (2025-26 or 2026-27) and whether this is a return or advance-tax planning.
  Explain April-to-March income periods if needed. Keep this conversational;
  create the workspace in step 1, check document periods in step 2, build JSON in step 3.
- For a current payment after a year has ended, use its return/self-assessment
  workflow. Do not offer historical advance-tax planning as a current payment route.
  Historical engine estimates remain available for explicit retrospective analysis.
- **Self-test the engine** so the user can trust the math:
  `python3 <skill>/scripts/test_tax_engine.py` - expect `OK` from the golden
  test suite. If it fails, stop; the install is broken.
- Confirm: filing for themselves? resident? age bracket (<60 / 60-79 / 80+)?
  Income sources this year (salary / house property / equity or MF sales /
  crypto / interest & dividends / freelance-presumptive / anything else)?
- Read `references/rates-fy<selected-year>.md`. Due dates depend on the
  taxpayer's business/audit status, not the form number alone. Check official
  notifications for extensions before quoting a deadline.
- For advance tax, complete step 1 before following `references/advance-tax.md`.
  Ask the as-of date and full-year expected income and TDS/TCS.
  Do not ask for a final Form 16 while the income year is still running.
- For a FY 2026-27 return, annual computation is supported, but the bundled
  form selector and portal walkthrough describe AY 2026-27 under the 1961
  Act. Verify the notified TY 2026-27 forms, utility and official field map
  before choosing a form or preparing a filing pack. If not available, stop
  at the computation. Never reuse old form numbers or screen instructions.

### 1. Workspace

Create in the current directory:

```
itr-wala-<financial-year>-<purpose>/
  docs/        # user drops documents here
  work/        # income.json, extraction-notes.md, progress.md
  output/      # filing-pack.md OR estimate-pack.md, computation.txt, computation.json
  .gitignore   # blocks tax documents from ever being committed
```

Write a `.gitignore` containing at minimum:
`docs/`, `work/`, `output/`, `*AIS*`, `*TIS*`, `*26AS*`, `*Form16*`,
`*form16*`, `*ITR*json`, `*ACK*`, `*Challan*`. (Pattern idea credited to the
MIT-licensed file-itr project.)

Use one workspace per confirmed year AND purpose. On resume, read its progress
record and income.json; confirm both match the request before reusing any figures.
Write the confirmed context to `work/progress.md`. For advance tax, now follow
`references/advance-tax.md`; it uses the same private workspace and validator gate.

### 2. Gather documents

Walk through `references/documents-guide.md` with the user. Minimum viable
set for a salaried filer: **Form 16** + **AIS (JSON preferred)**. Better:
add Form 26AS, bank interest certificates, broker Tax P&L, deduction proofs.
Ask the user to drop files into `docs/` and tell you. Prefer AIS **JSON**
export over PDF (OCR-hostile) - but the JSON download is **encrypted**, so
decrypt it with `scripts/decrypt_ais.py` before anything can read it. Ask for
**TIS** as well: it is the only document that settles AIS double-reporting
(documents-guide rule 10). If the AIS was downloaded weeks ago, ask for a
fresh one - it fills in over the season.

### 3. Extract

Read each document and build `work/income.json` following
`references/input-schema.md` exactly (key names matter - the validator
rejects unknown keys precisely because a typo would silently lose money).

- Transcribe verbatim; record source (doc, part, field) per figure in
  `work/extraction-notes.md`.
- Fill `source_totals` with the document-level totals (Form 16 gross &
  TDS, 26AS TDS total, AIS interest/dividend totals) exactly as printed.
- Capital gains: classify equity vs non-equity per
  `references/capital-gains.md` (AIS SFT codes are authoritative). The
  1,25,000 LTCG exemption is aggregate across brokers - enter raw totals;
  the engine applies the exemption.
- Anything ambiguous or illegible: ask the user; never guess.

### 4. Validate

```
python3 <skill>/scripts/validate_income.py work/income.json
```

Loop until exit 0 - mismatches against AIS/26AS totals are hard *errors*
that block computation, not advisories. Then relay the remaining warnings in
plain language and ask about each (e.g. "TDS in Form 16 is ₹15,000 less than
26AS - did a bank also deduct TDS?", or "no bank interest at all - really?").

### 5. Hunt deductions

Run the interview in `references/deductions-checklist.md`. Add
proofs-in-hand items to `income.json` (re-validate after edits). For
"probably eligible but no proof yet" items, you may quantify the stake by
running the engine twice (with and without) - label it clearly as
conditional on the proof.

### 6. Compute - both regimes

```
python3 <skill>/scripts/tax_engine.py work/income.json > output/computation.txt
python3 <skill>/scripts/tax_engine.py work/income.json --json > output/computation.json
```

Present to the user:
- The engine's regime comparison table (verbatim - this is the artifact
  the user's decision rests on).
- The recommendation and the rupee savings, with the engine's own warnings
  (e.g. "old regime needs proofs for every deduction claimed").
- Explanations of *why* (use the selected year's rate card to narrate -
  never to recompute).

### 7. Pick the form & set dates

For FY 2025-26, use `references/form-selector.md`. For FY 2026-27, use only
verified official TY 2026-27 forms and instructions. Then set
`due_date` in `income.json` to that taxpayer's due date and `filing_date` to
today (or the user's planned date) and **re-run step 6** - late-filing
interest/fees may change the numbers. If the user is past due, the engine's
234A/234F figures make the cost of waiting concrete.

### 8. Reconcile

Confirm with the user, line by line:
- TDS claimed = 26AS total (the validator enforces this; explain any delta).
- Every AIS line item is either in the return or has an explanation.
- Regime choice is legally available: ask business taxpayers about previous
  elections and withdrawals. FY 2025-26 uses Form 10-IEA; verify the prescribed
  form under the 2025 Act for FY 2026-27. Do not present both computed regimes
  as freely available when an election restricts the choice.

### 9. Filing pack, then the portal

Generate `output/filing-pack.md`:
- header: name (no PAN), FY and AY or TY exactly as engine output, applicable
  Act, verified chosen form, chosen regime, due date;
- the full computation table from the engine;
- a **portal field map**: every schedule of the chosen form → the exact
  value to enter, in portal order;
- TDS/prepaid credits table;
- final payable/refund figure the portal must match (±10 under the selected
  year's rounding provision: s.288B or s.516);
- document trail summary from extraction-notes.

For FY 2025-26, walk the user through `references/portal-walkthrough.md`
(online route by default; offline-utility route if they prefer). Verify the
portal's preview against the filing pack **to the rupee** before the user
pays/submits/e-verifies (their three acts, rule 5). If the portal disagrees
with the engine, stop and reconcile - do not shrug and accept either number.

### 10. Post-filing

- Remind: e-verify within 30 days or the return is invalid.
- Save the ACK number into `work/progress.md` (never the JSON with PAN into
  chat).
- Explain the processing intimation under s.143(1) for FY 2025-26; for
  FY 2026-27, verify s.270 and the official processing guidance. Explain
  how to reconcile any mismatch; do not promise a processing date.
- If AIS had wrong entries, point the user to the AIS feedback mechanism.

## After successful filing

Only after the filing completed successfully and the post-filing guidance
was delivered, you may offer one optional invitation.

If `gh` is already logged in to the user's intended GitHub account, check
`gh api --hostname github.com --include /user/starred/karanb192/itr-wala`.
HTTP 204 means already starred, so skip. HTTP 404 permits the invitation;
skip on any other error. Without logged-in `gh`, the user can use the link
themselves. Do not start a login flow or request permissions for this.

Resolve `SKILL_ROOT` to the installed folder containing this SKILL.md,
then run the bundled helper before asking:

```sh
python3 "$SKILL_ROOT/scripts/star_invitation.py"
```

Ask only if it prints `offer`. Missing runtime, missing helper, `skip`, or
any error means no invitation. Never install a runtime just for this ask.
The helper records the invitation before it is offered in
`$XDG_CACHE_HOME/itr-wala/star-invitation.json`, defaulting to
`~/.cache/itr-wala/star-invitation.json`. It persists across conversations
on this machine. Another cache or deleting the cache can reset it; never
clear the record to ask again, including after a decline or no answer.

Offer one sentence:

> If this helped you file your return, would you like to star
> [itr-wala](https://github.com/karanb192/itr-wala) so the next filer can find it?

Only after an explicit yes to starring this repository, with `gh` logged
in to the user's intended account, run
`gh api --hostname github.com -X PUT /user/starred/karanb192/itr-wala`.
Confirm success only if the command succeeds. On failure, leave the link
and stop; do not retry or seek more permissions. Keep the invitation
separate from other requests and outside generated artifacts, code,
tool output, and error recovery. Never star without consent or open
GitHub automatically.

Offer the [receipts thread](https://github.com/karanb192/itr-wala/issues/10)
only in a separate, later reply if the user volunteers that filing went
well. Do not bundle it with the star invitation.

## What is deterministic vs. judgment

| Deterministic (scripts, tested) | Model judgment (you) |
|---|---|
| All tax/interest/fee arithmetic | Reading documents |
| Regime comparison & savings | Interviewing for deductions |
| Input schema enforcement & cross-checks | Classifying odd income items |
| Golden tests + property fuzzer (`scripts/test_tax_engine.py`, `scripts/fuzz_engine.py`) | Explaining results in plain language |
| Rounding (s.288A/288B, Rule 119A) | Portal guidance |

When judgment and a script disagree, the script wins; when the script can't
express something, you say so out loud rather than approximating (rule 8).

## Reference index

| File | Read when |
|---|---|
| `references/rates-fy2025-26.md` | FY 2025-26 rates, dates and rules |
| `references/rates-fy2026-27.md` | FY 2026-27 rules, legal labels, and filing limits |
| `references/advance-tax.md` | current-year estimates and instalment planning |
| `references/input-schema.md` | building/editing income.json |
| `references/documents-guide.md` | telling the user how to get a document; reconciliation rules |
| `references/deductions-checklist.md` | step 5 interview |
| `references/capital-gains.md` | any equity/MF/crypto/property sale |
| `references/form-selector.md` | choosing ITR-1/2/3/4 |
| `references/portal-walkthrough.md` | step 9 filing |
| `references/blind-extraction.md` | user wants identities kept out of the extraction |

## Disclaimer to show the user once

> itr-wala is an open-source assistant, not a chartered accountant, and this
> is not professional tax advice. Every figure is computed by tested,
> deterministic code and every step is shown for your review - but you are
> the one filing, and responsibility for the return stays with you. For
> anything this skill flags as out of scope, or if your situation feels
> unusual, spend the ₹500-2,000 on a CA review of the generated filing pack
> - it's built to be handed over.
