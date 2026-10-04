# FY 2025-26 rebate calculation correction

Engine 1.2.0 checked the new-regime ₹12 lakh rebate limit against slab-rate
income alone. It should have included special-rate income in total income.
The correction can increase annual tax by up to ₹62,400, before any resulting
interest. It does not mean every user or every filed return was affected.

## Check whether this affects your computation

Recheck if you used engine 1.2.0 for FY 2025-26 under the new regime and had
special-rate income, such as equity gains, other long-term gains, VDA or winnings.
The affected pattern is slab-rate income at or below ₹12 lakh but total income
above ₹12 lakh. Gains within the equity LTCG exemption still count towards
that total-income test. Marginal relief can reduce the difference near the limit.

These fictional examples were run against main at `3c1c49a` and the corrected
engine. Each has gross salary ₹12,75,000, no other deductions and the additional
income shown. Amounts are annual tax including cess, excluding interest and fees.

| Additional income | Engine 1.2.0 | Corrected | Difference |
|---|---:|---:|---:|
| Equity LTCG ₹2,00,000 | ₹9,750 | ₹72,150 | ₹62,400 |
| Equity LTCG ₹1,00,000 | ₹0 | ₹62,400 | ₹62,400 |
| Equity STCG ₹20,000 | ₹4,160 | ₹20,800 | ₹16,640 |
| VDA gain ₹1,00,000 | ₹31,200 | ₹93,600 | ₹62,400 |
| Winnings ₹50,000 | ₹15,600 | ₹52,000 | ₹36,400 |

The ₹62,400 example is the lost ₹60,000 rebate plus 4% cess. The statutory
total-income test and restriction to slab-rate tax are in
[Finance Act 2025 s.20](https://egazette.gov.in/WriteReadData/2025/262125.pdf).
The [regression tests](../skills/itr-wala/scripts/test_tax_engine.py) cover the
threshold, partially available marginal relief and both supported income years.

## If you used an affected computation

1. Recompute with the corrected version and compare the result with the actual
   filed return and any processing intimation. The portal may already have
   corrected the rebate; an old tool estimate alone does not prove underpayment.
2. If the filed return is wrong, review the correction promptly using the official
   utility or a CA. Do not wait until a filing deadline to review unpaid tax or
   accruing interest. Do not dispute a correct demand using the old engine output.
3. For AY 2026-27, revision is generally available until 31 March 2027 or assessment
   completion, whichever is earlier. Revision after 31 December 2026 attracts the
   new s.234I fee: ₹1,000 up to ₹5 lakh total income, ₹5,000 above it. That fee
   window is not a deadline for paying tax without interest. Revised-return
   preparation remains outside itr-wala's supported workflow.

Sources: [Finance Act 2026 ss.5 and 16](https://egazette.gov.in/WriteReadData/2026/271439.pdf),
[official ITR-2 FAQ](https://www.incometax.gov.in/iec/foportal/help/all-topics/e-filing-services/itr-2/itr-2-faqs).

Verify a submitted return within the prescribed 30 days. Timely verification
preserves the upload date; late verification can change the filing date and its
consequences. The user completes submission and verification.
[Official verification FAQ](https://www.incometax.gov.in/iec/foportal/help/all-topics/e-filing-services/itr-v-faqs30-days-timeline-e-verification-returns).
