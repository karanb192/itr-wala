# ITR Form Selector - AY 2026-27 (FY 2025-26)

When to read this: before telling the user which ITR form to file, and before setting the `due_date` input for `tax_engine.py`. Ask the questions below in order; do not assume.

**Year guard:** this form selector covers FY 2025-26 / AY 2026-27 only.
For FY 2026-27 / TY 2026-27, use the [selected-year rate card](rates-fy2026-27.md)
and verify the notified return forms and utility. Do not copy the form numbers,
eligibility or screen flow below. Advance-tax estimates need no ITR form.

## Decision procedure (ask in this order, stop at the first hit)

1. **Non-resident or RNOR?** → Out of this skill's scope (engine is resident-only). At minimum ITR-2; refer out.
2. **Any business or professional income?** This includes freelancing, creator/platform income, consulting, **F&O trading (non-speculative business)** and **intraday equity trading (speculative business)** - both force a business head even for a "salaried" user.
   - Eligible presumptive u/s 44AD/44ADA, total income ≤ 50,00,000, and no ITR-4 disqualifier (below) → **ITR-4 (Sugam)**. Set `income.presumptive_section`. 44AE is outside this tool's scope.
   - Anything else with a business/profession head (actual books, presumptive + STCG, F&O, intraday, directorship, unlisted shares, foreign assets, income > 50,00,000) → **ITR-3**.
3. **No business income.** Any of the ITR-1 disqualifiers below present → **ITR-2**.
4. **None of the above** → **ITR-1 (Sahaj)**.

## ITR-1 (Sahaj) - allowed only if ALL of these hold

- Resident individual (not RNOR, not non-resident); total income ≤ 50,00,000.
- Income only from: salary/pension, ONE house property, other sources (interest, dividend); agricultural income ≤ 5,000.
- **LTCG u/s 112A up to 1,25,000 is now allowed in ITR-1** (form change effective AY 2025-26, continues for AY 2026-27) - but only if there is **no capital loss to set off or carry forward**.

**Hard disqualifiers** (any one → ITR-2 minimum):
- ANY STCG u/s 111A (even 1 rupee), any capital gains other than the 112A carve-out, any capital loss.
- Any VDA (crypto/NFT) income - Schedule VDA does not exist in ITR-1/4.
- Lottery/game-show/online-game winnings (income taxable at special rates u/s 115BB/115BBJ).
- More than one house property; brought-forward or carry-forward losses of any head.
- Foreign assets or foreign income (Schedule FA), including **foreign RSU/ESOP merely held** (see below).
- Director in any company; unlisted equity shares held at any time in the FY; ESOP tax deferral (eligible start-up).
- TDS deducted u/s 194N (cash withdrawals).

## ITR-2 - individuals/HUF with NO business/profession income

Forced into ITR-2 by any of: STCG of any kind; LTCG > 1,25,000 or with losses; more than one house property; total income > 50,00,000; foreign assets/foreign income; NR/RNOR status; directorship; unlisted shares; VDA reported as capital gains; buyback loss reporting (the 1-Oct-2024 to 31-Mar-2026 buyback regime creates a deemed-dividend entry in Other Sources PLUS a capital-loss entry - that loss alone rules out ITR-1).

**RSU/foreign-stock rule**: foreign employer RSUs/ESPP/ESOPs or any foreign brokerage holding require **Schedule FA disclosure even if nothing was sold during the year** → minimum ITR-2. Never let a "salaried, no sales" user with vested US RSUs file ITR-1.

## ITR-3 - any business or professional income

Everything ITR-2 covers, plus business/profession. Specifically forces ITR-3:
- F&O trading (non-speculative business income), intraday trading (speculative business income).
- Presumptive income combined with anything ITR-4 disallows (e.g. 44ADA creator + STCG on shares - the very common "salaried + creator + sold some stock" case is ITR-3).
- Actual books of account; partner in a firm.

## ITR-4 (Sugam) - presumptive only

- Resident individual/HUF/firm (non-LLP); total income ≤ 50,00,000.
- Business/profession taxed presumptively u/s 44AD or 44ADA. Although the form can cover 44AE, this tool cannot.
- Same LTCG allowance as ITR-1: 112A gains ≤ 1,25,000, no losses. Any 111A STCG, other capital gains, VDA, foreign assets, directorship, or unlisted shares → ITR-3 instead.

## Due dates (AY 2026-27) and the engine's `due_date` input

Finance Act 2026 split the non-audit deadline (s.139(1)); business/professional
income and audit status determine it, not the form number alone. Check
[the rate card](rates-fy2025-26.md) and official notifications for extensions.

| Taxpayer status | Due date | Pass to engine as `"due_date"` |
|---|---|---|
| No business/profession, no audit | 31 July 2026 | `"2026-07-31"` |
| Business/profession, no audit | 31 August 2026 | `"2026-08-31"` |
| Audit cases u/s 44AB, outside scope | 21 November 2026 (extended) | do not compute audit cases |

The engine defaults to 2026-07-31 without business income and 2026-08-31 with
presumptive income. **Always set a verified `due_date` explicitly**. A no-business
ITR-3 filer is not automatically entitled to the August date. Belated return:
31 December 2026; revised: 31 March 2027, subject to earlier assessment completion.
Revised-return workflow/fees remain unsupported. Source:
[Finance Act 2026 s.5](https://egazette.gov.in/WriteReadData/2026/271439.pdf).

## Form 10-IEA (old-regime opt-in for business filers)

- A filer **with business/profession income** (ITR-3/ITR-4) who wants the OLD regime must e-file **Form 10-IEA before the s.139(1) due date**. Without a 10-IEA on record by then, they are locked into the new regime for the year - say so plainly before running the old-regime comparison as if it were available.
- Filers **without** business income (ITR-1/ITR-2) just tick the regime choice inside the return each year; no 10-IEA needed.
- Once a business filer opts out to the old regime, switching back to new is allowed once, after which re-entry to old is restricted - flag this before they opt out for a marginal saving.

## Wrong-form consequences and common mistakes

Filing the wrong form triggers a **defective-return notice u/s 139(9)**; an uncured defect means the return is treated as not filed. The classic errors:

- ITR-1 filed with STCG, with foreign RSUs held (no Schedule FA), or with 194N TDS present in 26AS.
- ITR-4 filed by an F&O/intraday trader (that is business income needing ITR-3, not presumptive-eligible-by-default).
- ITR-1/4 filed with any crypto/VDA transaction - no Schedule VDA in those forms.
- Assuming capital gains always disqualify ITR-1/4 - the small 112A ≤ 1,25,000 no-loss carve-out is allowed this AY; do not needlessly push those users to ITR-2.
- Choosing the form before checking AIS/26AS - 194N TDS, SFT equity-sale entries, or dividend from unlisted shares in AIS can silently disqualify ITR-1.

**When in doubt between two forms, pick the higher-numbered one - it is always legal to file more detail.**
