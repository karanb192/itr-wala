# Deductions checklist for both supported income years

When to read this: before building `income.json`, whenever the old regime is in play, or when the user asks "what can I claim?". Walk the checklist item by item - people overpay because nobody asked.

The interview retains legacy 1961 Act section labels and stable JSON keys.
For FY 2026-27, read [rates-fy2026-27.md](rates-fy2026-27.md) for legal
counterparts. Verify any additional deduction/form under the selected Act
before using it. Unsupported government NPS/Agniveer cases remain unsupported.
For advance tax, user-approved eligible forecasts may be used with their basis
recorded; a return still requires final proof.

## Ground rules

1. **Never invent, inflate, or assume a deduction.** Goal is the lowest LEGAL tax. A claim needs a proof document the user actually has (or an entry already printed in Form 16 Part B - the employer verified proofs for those).
2. **You do zero arithmetic.** Classify amounts; Python applies caps and computes. Where the engine accepts an already eligible amount (80D, 80G, `other`), get the documented computation or use a deterministic script and show its output for user approval. Never calculate it mentally or invent a total.
3. **Two lists, two runs.** Items with proofs in hand go into `income.json` and drive the regime comparison. Items the user *probably* has but can't produce yet ("I think I paid LIC premium…") go into a separate "possible but unproven" list - run the engine a second time with them added and show the delta: "finding that proof would save another ₹X under the old regime." File only on the proven set.
4. Chapter VI-A deductions do NOT reduce special-rate income (s.111A/112A/112 gains, VDA) - the engine enforces this. Don't promise 80C savings to someone whose income is mostly capital gains.

## New regime first - set expectations

The new regime (s.115BAC, the default) kills almost every deduction. What survives:

| Item | Limit (new regime) | Engine field |
|---|---|---|
| Standard deduction (salary/pension) | 75,000 - automatic | applied by engine |
| s.80CCD(2) employer NPS | 14% of Basic+DA, govt AND private | `deductions.80ccd_2` (+ `income.salary.basic_plus_da` for the cap check) |
| Employer EPF contribution | not taxed within statutory limits | nothing to enter - it is simply not part of gross salary |
| s.80CCH(2) Agniveer Corpus Fund | Agniveers only; engine does not model it - flag manually if it applies | - |

**Dead in the new regime** (engine warns and ignores them): 80C, 80CCD(1B), 80D, 80TTA/80TTB, 80G, HRA, LTA, s.24(b) self-occupied interest, professional tax, house-property loss set-off. Tell the user this upfront so expectations are set - but still run the interview below, because the old regime can only win if the proven deductions are collected and compared.

## Old regime - walk this table item by item

Ask about every row. For each "yes": get the amount, the proof, and map to the engine field. Employer-declared items appear in Form 16 Part B (Chapter VI-A breakup, and the s.10 exempt-allowance list for HRA/LTA) - extract from there first.

| Legacy section | Limit in supported years | What qualifies | Proof / where in Form 16 | Engine field |
|---|---|---|---|---|
| Standard deduction | 50,000 | salary/pension, automatic | none needed | applied by engine |
| s.16(iii) professional tax | actual paid amount | tax on employment deducted by employer | year-specific salary certificate / payslips | `income.salary.professional_tax` |
| 80C (aggregate with 80CCC + 80CCD(1)) | 1,50,000 | EPF **employee** share (Form 16 Part B VI-A / EPF passbook), PPF, ELSS, life-insurance premium, home-loan **principal**, children's tuition fees (tuition component only), NSC, 5-yr tax-saver FD, Sukanya Samriddhi | passbooks, premium receipts, lender principal certificate, fee receipts; usually pre-totalled in Form 16 Part B | `deductions.80c` (engine caps) |
| 80CCD(1B) | 50,000 extra, over the 80C cap | own NPS contribution | NPS transaction statement; Form 16 Part B if routed via employer | `deductions.80ccd_1b` (engine caps) |
| 80CCD(2) | **10%** of Basic+DA private / 14% govt - note the asymmetry: the 14%-for-everyone rate is NEW regime only | employer NPS contribution | Form 16 Part B VI-A | `deductions.80ccd_2` - engine applies the 10% old-regime cap; a govt employee entitled to 14% under old regime will be over-capped - flag and verify on the portal |
| 80D | 25,000 self/family (50,000 if a senior is insured) **plus** 25,000 parents (50,000 if senior); preventive check-up 5,000 sub-limit *within* these caps | health-insurance premium, preventive health check-up. Also s.80D(2): where a senior (60+, self/spouse or parent) has NO health-insurance cover, actual medical expenditure qualifies within the same 50,000 senior cap - payment by any mode other than cash | insurer premium statement/receipts; Form 16 Part B VI-A; for senior medical expenditure: itemised bills + non-cash payment proof | `deductions.80d` - engine does NOT cap this; you compute the eligible amount from the rules here and feed only that |
| 80TTA / 80TTB | 10,000 savings interest (<60y) / 80TTB 50,000 savings+FD interest (60+, replaces 80TTA) | bank interest already reported in `other_sources` | bank statements / interest certificates | omit `deductions.80tta_ttb` - engine auto-computes the right cap from age + reported interest |
| s.24(b) home-loan interest | self-occupied: 2,00,000. Let-out: full interest, but total house-property **loss** set-off against other heads is capped at 2,00,000 (s.71(3A)); balance carries forward (engine warns, does not track) | interest on housing loan | lender's interest certificate | `income.house_property` list (`type`, `interest_paid`, `rent_received`, `municipal_taxes`) - NOT a `deductions` key |
| HRA s.10(13A) | exempt = least of: actual HRA received; rent − 10% of Basic+DA; 50% Basic+DA metro / 40% non-metro (verify this computation on the portal before relying on it) | rent actually paid while receiving HRA | rent receipts; landlord PAN if rent > 1,00,000/yr; HRA figure from Form 16 / payslips. If employer already allowed it, it's in the Form 16 s.10 exempt list - use that number | fold into `income.salary.exempt_allowances` |
| LTA s.10(5) | domestic travel fare, twice per 4-year block, employer-routed | travel bills submitted to employer | Form 16 s.10 exempt list - only add manually if employer missed it AND bills exist | fold into `income.salary.exempt_allowances` |
| 80E | **no cap** on education-loan interest | interest (not principal) on a higher-education loan | lender interest certificate | add into `deductions.other` |
| 80G | 50% or 100% depending on donee, some capped at 10% of adjusted GTI; **cash donations above 2,000 don't qualify** | donations to approved institutions | donation receipt with donee PAN + 80G registration reference | `deductions.80g` - engine does NOT cap; compute the eligible amount first and show your working |
| 80EEB | EV-loan interest, up to 1,50,000 (verify on the portal before relying on this) | interest on a loan for an electric vehicle | lender interest certificate | add into `deductions.other` |
| 80EEA | additional 1,50,000 over the s.24(b) 2,00,000 cap | interest on an affordable-housing loan sanctioned 1-Apr-2019 to 31-Mar-2022; stamp-duty value of the house up to 45,00,000; user owned no other residential house on the sanction date; ONLY interest beyond what s.24(b) already absorbed - never the same rupee under both sections | lender interest certificate + sanction letter (shows sanction date; stamp-duty value from the sale deed) | add into `deductions.other` - show the working: total interest, minus the portion claimed under s.24(b), balance capped at 1,50,000 |
| 80U / 80DD / 80DDB | flat/capped amounts vary by disability severity and age - confirm current limits on the portal before claiming | self disability / disabled dependant / specified-disease treatment | disability certificate (Form 10-IA) / medical prescription | add into `deductions.other` |
| 80GG | rent paid when NO HRA is received (limits apply - verify on the portal before relying on this) | rent without an HRA component | rent receipts + declaration | add into `deductions.other` |

Also ask: **brought-forward capital losses** from earlier ITRs (prior acknowledgements / Schedule CFL) - not a deduction, but they cut gains and change the regime math.

Also ask: **clubbing of income** - not a deduction, but missed clubbing is under-reporting. (a) Minor children's bank/FD interest: clubbed into the higher-earning parent's income u/s 64(1A), minus the s.10(32) exemption of 1,500 per child; transcribe the net amount into the matching `other_sources` field (savings_interest / fd_interest) and show the working. (b) Income from assets transferred to a spouse without adequate consideration (e.g. money gifted into an FD in the spouse's name): clubbed in the transferor's hands u/s 64(1)(iv) - report it under the transferor's matching income head.

## Feeding the engine

- Valid `deductions` keys are ONLY: `80c`, `80ccd_1b`, `80ccd_2`, `80d`, `80tta_ttb`, `80g`, `other`. `validate_income.py` rejects anything else (e.g. `80e`) - sum 80E/80EEB/80EEA/80U/80DD/80DDB/80GG eligible amounts into `other` and list the breakup for the user in chat.
- HRA/LTA are exemptions, not Chapter VI-A: they belong in `income.salary.exempt_allowances`. s.24(b) belongs in `income.house_property`. Putting them under `deductions` double-counts nothing but computes the wrong regime picture.
- Run the engine with `"regime": "both"` in income.json (the default) and the **proven** set → recommendation. Then rerun with the unproven items added → quote the extra saving as the incentive to dig out proofs. Never let unproven items decide the filed return.
- Present the final claim list with proof named per line. If the user asks you to add anything they cannot substantiate, refuse and explain: an unproven claim risks a notice and penalty; lowest *legal* tax only.
