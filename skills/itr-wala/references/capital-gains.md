# Capital gains and crypto for both supported financial years

When to read this: the user has sold shares, mutual funds, property, or crypto, or AIS/broker statements show SFT capital-gains rows. Classify every gain into an engine bucket here; `tax_engine.py` does ALL the arithmetic.

Confirm FY before classification. Legacy schema names stay the same: for
FY 2026-27, s.111A/112A/112 correspond to s.196/198/197, and VDA/winnings
use s.194 tables. See [rates-fy2026-27.md](rates-fy2026-27.md). Form-selection
notes below cover FY 2025-26 only; future-year forms must be verified.
FY 2026-27 buybacks and SGB exemption questions are outside this workflow.

## Engine buckets (`income.capital_gains` in income.json)

| Engine key | Section | What goes in | Rate applied by engine |
|---|---|---|---|
| `stcg_111a` | s.111A | STT-paid listed equity / equity-oriented MF / business trust units held ≤12 months | 20% |
| `ltcg_112a` | s.112A | Same assets held >12 months. Enter the FULL gain - the engine subtracts the 1,25,000 exemption itself; never pre-subtract | 12.5% above 1,25,000 |
| `ltcg_other` | s.112 | Other long-term assets: property (holding period 24 months), gold, unlisted shares, pre-Apr-2023 debt-MF units held >24 months | 12.5%, no indexation |
| `stcg_slab` | slab | Non-equity short-term gains; specified mutual-fund units acquired on/after 1-Apr-2023 (s.50AA, any holding period) | slab rates |
| `vda` | s.115BBH | Crypto/NFT/VDA transfer gains (sum of per-transfer positive gains only) | 30% flat |

Surcharge on these supported CG buckets is capped at 15% and cess is 4%.
Both supported years use 20% equity STCG and 12.5% equity LTCG, not older
15%/10% columns. Source: [amended Act ss.196-198](https://www.incometaxindia.gov.in/documents/d/guest/income_tax_act_2025_as_amended_by_fa_act_2026-pdf)
and [Finance Act 2026](https://egazette.gov.in/WriteReadData/2026/271439.pdf).

All five keys must be NET POSITIVE amounts. The engine models NO loss set-off or carry-forward and the validator rejects negatives. If any bucket is a net loss, or brought-forward losses exist (Schedule CFL), the engine cannot compute this return correctly - tell the user, file via ITR-2 with the losses reported, and suggest a CA if amounts are material.

## Situations the engine does NOT model - always warn

- **Land/building acquired on or before 22-Jul-2024** sold by a resident individual/HUF: taxpayer may pay the LOWER of 12.5% without indexation or 20% WITH indexation (second proviso to s.112). The engine taxes `ltcg_other` at flat 12.5% only, which can overstate tax. Flag for manual/CA computation before filing.
- **Buyback capital-loss twin** (below).
- **s.234C carve-out for unforeseeable gains** (below).
- Per-scrip **grandfathering** (equity bought before 1-Feb-2018 uses FMV as on 31-Jan-2018 as stepped-up cost): still applies in FY 2025-26, but broker tax P&L reports already bake it in - use the broker's gain figure; never recompute cost yourself.

## Buyback: 1-Oct-2024 to 31-Mar-2026 window

For buybacks in this window, the FULL consideration is deemed dividend u/s 2(22)(f) - taxed at slab under Income from Other Sources with NO cost deduction. Put the entire proceeds in `income.other_sources.dividends` (correctly gets the 15% dividend surcharge cap; reconcile any TDS in 26AS). The cost of acquisition separately becomes a capital LOSS (sale consideration deemed nil u/s 46A), STCL/LTCL by holding period, with normal set-off/carry-forward. The engine does not model this loss twin - warn the user it exists, it needs Schedule CG entry in ITR-2 to be claimed, and suggest a CA if the cost (loss) is material. From 1-Apr-2026 buybacks revert to capital-gains treatment - do not reuse this rule next AY.

## Crypto / VDA (s.115BBH)

- 30% flat + surcharge + 4% cess. Only cost of acquisition deductible - no expenses, no exchange fees.
- NO loss set-off of any kind, not even VDA-against-VDA: `vda` = sum of positive per-transfer gains; drop loss transfers entirely (they also cannot be carried forward).
- No basic-exemption set-off or new-regime rebate against VDA tax. The engine also excludes VDA/winnings from the old rebate as its conservative posture; it does not apply a contested VDA claim.
- **Schedule VDA is mandatory**, one line per transfer (acquisition date, transfer date, cost, consideration). ITR-1/4 cannot report VDA - minimum ITR-2 (capital-gains route) or ITR-3 (trading-as-business route).
- Reconcile 1% TDS u/s 194S: exchange statements vs 26AS/AIS. Include it in `taxes_paid.tds`. If 194S entries exist in 26AS but the user reported no VDA income, that is a notice magnet - resolve before filing.

## Classify equity vs non-equity from AIS SFT codes

Never classify by fund name or gut feel. The AIS information code plus the STT column is the evidence:

| AIS code | Meaning | Treatment |
|---|---|---|
| SFT-17-LES | Sale of listed equity share | 111A / 112A |
| SFT-18-EMF | Sale of unit of equity-oriented MF (STT amount present on the row) | 111A / 112A |
| SFT-18-OTU | Sale of other unit (STT column zero) | Check the fund's tax classification, acquisition date and holding period; this code alone does not establish s.50AA treatment |

Known traps (real CA/software errors have cost users thousands):
- **Arbitrage funds ARE equity-oriented** (111A/112A) despite debt-like returns.
- **Balanced-advantage / dynamic asset allocation names do not establish tax status.** Check the AMC's tax statement and STT evidence before choosing an equity or non-equity bucket.
- **Switch-outs count as redemptions**; equity-fund switch-outs carry STT and get 111A/112A like normal sales.
- Two frequent mistakes to catch in third-party computations: equity-MF LTCG dumped into "other than 112A" (forfeits the 1,25,000 exemption), and equity STCG taxed at slab instead of 111A.

For FY 2025-26 onward, the specified-mutual-fund definition covers funds investing
more than 65% in debt/money-market instruments and funds investing at least 65%
in those funds. Do not apply deemed short-term treatment to every non-equity
fund acquired after April 2023. Use the broker/AMC's confirmed classification;
stop if it is unclear. Sources: [s.50AA](https://www.incometaxindia.gov.in/w/section-50aa-3),
[AMFI tax guidance](https://www.amfiindia.com/investor/knowledge-center-info?zoneName=TaxRegimeForMutualFunds).

## Broker Tax P&L exports

- Ask for each broker's tax P&L report (Zerodha: Console → Reports → Tax P&L; Groww/Upstox have equivalents). These give the STCG/LTCG split with grandfathered costs already applied.
- The 1,25,000 s.112A exemption is ONE aggregate per PAN per FY - never per broker. Sum LTCG across ALL brokers/MF platforms into a single `ltcg_112a`; the engine applies the exemption exactly once. Watch for broker reports that each show "exemption remaining 1,25,000".
- Cross-check broker totals against AIS SFT rows and bank credits; investigate any gap before filing (AIS may include off-broker MF redemptions via RTA data).

## Quarterly gains and s.234C

The engine computes 234C from full-year assessed tax against the standard cumulative installments (15/45/75/100% by 15-Jun/15-Sep/15-Dec/15-Mar) using `taxes_paid.advance_tax` dates. It does NOT model the s.234C carve-out: no 234C interest on shortfall attributable to unforeseeable capital gains (or dividends/lottery) if the tax on them is paid in the NEXT installment, or by 31-Mar for Q4 gains. So if a large gain landed in a specific quarter and advance tax followed in the next installment, the engine's 234C may OVERSTATE interest - say so, and treat the portal's figure (driven by the quarter-wise CG breakup in Schedule CG) as authoritative. Always fill the Schedule CG quarterly breakup with actual sale dates from broker reports; a wrong quarter mis-states interest on the portal.

## Basic exemption set-off and 87A - narrating engine output

For residents, if slab-rate income is below the basic exemption (4,00,000 new regime; 2,50,000/3,00,000/5,00,000 old regime by age), the unused exemption absorbs special-rate gains. Engine order (beneficial, highest rate first): 111A @ 20% → 112A → 112 other. VDA never participates (s.115BBH). In the output, each `tax.special` row shows `income` vs `taxable`; the difference is the exemption absorbed (the 112A row's difference also includes the 1,25,000 exemption).

New rebate: the ₹12L test uses TOTAL income, including special-rate gains;
the ₹60,000 deduction offsets slab tax only. Marginal relief is likewise
capped at slab tax. Old rebate uses ₹5L total income / ₹12,500 and excludes
equity LTCG; its special-gain processing warning remains. Sources:
[Finance Act 2025 s.20](https://egazette.gov.in/WriteReadData/2025/262125.pdf),
[2025 Act ss.156/198](https://www.incometaxindia.gov.in/documents/d/guest/income_tax_act_2025_as_amended_by_fa_act_2026-pdf).

## Which ITR form do capital gains force?

- ITR-1/ITR-4 CAN include LTCG u/s 112A up to 1,25,000, provided there are no losses to set off or carry forward.
- Any 111A STCG, 112A LTCG above 1,25,000, any other capital gain, any capital loss, buyback-loss reporting, or any VDA → ITR-1/4 are out.
- Capital gains without business income → ITR-2. Any business income - including F&O (non-speculative business) or intraday (speculative business) - → ITR-3.
- Original return due dates depend on business/audit status. Set an explicitly verified `due_date` using the selected-year rate card; do not infer it from the ITR form alone.
