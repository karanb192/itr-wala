# FY 2025-26 rebate calculation correction

Installs before 1.3.0 checked the new-regime ₹12 lakh rebate limit against slab-rate
income alone. It should have included special-rate income in total income.
The correction increases annual tax by ₹62,400 in the no-surcharge example below;
the difference can be larger when surcharge applies, before any resulting
interest. It does not mean every user or every filed return was affected.

## Check whether this affects your computation

Recheck any itr-wala install before 1.3.0: plugin 1.2.0 or 1.2.1, an unversioned
install, or a clone or skills.sh install from before the correction was merged.
Old `output/computation.json` files identify this code as `engine_version: "1.2.0"`,
even when the installed plugin says 1.2.1.

The affected computation used FY 2025-26 and the new regime, had special-rate
income (equity STCG/LTCG, other LTCG, VDA or winnings), total income above
₹12 lakh, and showed a rebate or marginal relief in the old output. Gains within
the equity LTCG exemption still count. This includes slab income above ₹12 lakh
in the marginal-relief band, roughly up to ₹12.7 lakh. Slab-only income, old-regime
computations and outputs with neither rebate nor marginal relief are outside
this correction's affected profile.

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
| Equity LTCG ₹50,00,000 | ₹6,97,130 | ₹7,65,770 | ₹68,640 |
| VDA gain ₹6,00,00,000 | ₹2,34,00,000 | ₹2,34,78,000 | ₹78,000 |

An additional marginal-relief example has gross salary ₹12,85,000 plus equity
LTCG ₹2,00,000. Old annual tax was ₹20,150; corrected annual tax is ₹73,710,
a ₹53,560 difference. Its slab income is ₹12,10,000, already above ₹12 lakh.

The ₹62,400 example is the lost ₹60,000 rebate plus 4% cess. Surcharge makes
that difference ₹68,640 at 10% or ₹78,000 at 25% in the examples above. These
are reproduced examples, not a ceiling on the total bill including interest.
The statutory
total-income test and restriction to slab-rate tax are in
[Finance Act 2025 s.20](https://egazette.gov.in/WriteReadData/2025/262125.pdf),
as corrected by [Finance Act 2026 s.161](https://egazette.gov.in/WriteReadData/2026/271439.pdf).
The [regression tests](../skills/itr-wala/scripts/test_tax_engine.py) cover the
threshold, partially available marginal relief and both supported income years.

## If you used an affected computation

1. Update to **1.3.0 or later**, restart the agent, then recompute and compare the result with the actual
   filed return and any processing intimation. The portal may already have
   corrected the rebate; an old tool estimate alone does not prove underpayment.
2. If the filed return understates tax and no processing intimation has already
   demanded the difference, reconcile the amount with the official utility or a CA,
   pay the difference plus applicable interest as self-assessment tax, then file
   a revised return under s.139(5). If an intimation already demands it, reconcile
   that demand first to avoid paying twice. Do not dispute a correct demand using
   the old output. itr-wala does not prepare revised returns; use the official
   utility or a CA.
3. For AY 2026-27, revision is available until 31 March 2027 or assessment
   completion, whichever is earlier. File by 31 December 2026 to avoid the
   s.234-I revision fee. Later revision attracts ₹1,000 up to ₹5 lakh total
   income, ₹5,000 above it. Tax-payment interest can continue before that date.
4. Verify the submitted return within 30 days to preserve the upload date.
   Verification after 30 days becomes the filing date, with applicable late-filing
   consequences. A return never verified is invalid. Submit and verify promptly,
   especially near the revision cutoff. [Official verification FAQ](https://www.incometax.gov.in/iec/foportal/help/all-topics/e-filing-services/itr-v-faqs30-days-timeline-e-verification-returns-faq).

Sources: [Finance Act 2026 ss.5 and 16](https://egazette.gov.in/WriteReadData/2026/271439.pdf),
[official ITR-2 FAQ](https://www.incometax.gov.in/iec/foportal/help/all-topics/e-filing-services/itr-2/itr-2-faqs).

## Update your existing install

Use the route you originally installed with. These commands fetch the published
default branch; before release they cannot install the fix. After updating, run
the self-test and confirm new computation JSON reports `engine_version: "1.3.0"`
or later. Stop if it still reports 1.2.0.

| Install route | Update |
|---|---|
| Clone / install.sh | In the checkout, run `git pull --ff-only`, review the diff, then rerun `./install.sh` with the same agent and scope flags used originally. For a project install use `./install.sh --project /path/to/tax-project`. |
| Claude Code plugin | `claude plugin marketplace update itr-wala`, then `claude plugin update itr-wala@itr-wala`; restart Claude Code. |
| Codex plugin | `codex plugin marketplace upgrade itr-wala`, then `codex plugin add itr-wala@itr-wala`; restart Codex. |
| skills.sh | `npx skills update itr-wala`; choose the original installation scope. |

Install flags and scoped installations are documented in the [README](../README.md#install-options).
