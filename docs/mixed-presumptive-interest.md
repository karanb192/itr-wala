# Mixed presumptive income: how s.234C is split

When a return combines eligible 44AD/44ADA presumptive income with salary, rent,
interest or gains, the engine now applies the quarterly instalment schedule only
to the non-presumptive tax share. The presumptive share is added to the 15 March
target. This replaces the earlier taxpayer-wide March interpretation and its
external-verification flag.

The split is pinned to the behaviour of the official AY 2026-27 calculation
components. It is still a calculation-component result, not a complete return,
portal submission or CPC processing result.

## What the engine computes

For each regime:

1. Recompute annual tax with `business_presumptive_income` set to zero.
2. Reduce that non-presumptive tax by TDS/TCS, capped at the total assessed tax.
3. Apply the 15% / 45% / 75% cumulative targets to that non-presumptive balance
   on 15 June, 15 September and 15 December.
4. Require 100% of the total assessed tax, including the presumptive share, by
   15 March.

A presumptive-only filer still gets one 100% March target. So does a mixed filer
whose non-presumptive income produces no tax after credits. The engine does not
model the separate s.234C / s.425 relief for capital gains or dividends received
during the year.

## Reproduced example

On 20 October 2026, the unmodified ITR-3 and ITR-4 interest-calculation functions
from the official AY 2026-27 common Mac utility v1.2.5 were executed in an
isolated JavaScript context. The date and rounding helpers also came from that
bundle. Explicit fictional intermediate fields supplied the income, regime,
credits and payment dates. Missing input reads failed the probe.

This was a calculation-component test. It did not run the complete native app,
validate a complete return, submit one, or test CPC processing.

Each row uses the new regime, a regular-age resident individual, no deductions
beyond the salary standard deduction, and ₹3,00,000 advance tax on 10 March 2026.

| Fictional income | Engine, split schedule | ITR-3 component | ITR-4 component |
|---|---:|---:|---:|
| Salary ₹15L gross + 44AD profit ₹8L | ₹3,945 | ₹3,945 | ₹3,949 |
| Salary ₹15L gross + 44ADA profit ₹8L | ₹3,945 | ₹3,945 | ₹3,949 |
| Only 44AD profit ₹22.25L | ₹0 | ₹0 | ₹0 |
| Only salary ₹23L gross | ₹10,788 | ₹10,788 | ₹10,793 |

The mixed rows use total taxable income ₹22,25,000, including salary after
standard deduction of ₹14,25,000. Both components remove presumptive profit
from the first three quarters and include it in March. The engine's ₹3,945
follows the ITR-3 component's floor-to-₹100 bases; ITR-4 rounds ₹4 higher.

The ₹10,788 alternative in [issue 19](https://github.com/karanb192/itr-wala/issues/19)
applies quarterly timing to the whole liability. It is not the observed
mixed-income result.

The current official Excel utilities corroborate the split through active
form-control and macro paths. ITR-3 v1.4 writes `Tax Calculated!R240` to the
normal-tax return output. ITR-4 v1.2 selects `TaxCalc!P51` for resident
presumptive income above the net-liability threshold. This Excel evidence is
static inspection, not a workbook execution.

## Sources and limits

The taxpayer-wide March reading follows
[s.211(1)(b)](https://www.incometaxindia.gov.in/w/section-211-64) and
[s.234C(1)(b)](https://www.incometaxindia.gov.in/w/section-234c-37).
For FY 2026-27, s.403(2), s.408(2) and s.425 of the
[amended 2025 Act](https://www.incometaxindia.gov.in/documents/d/guest/income_tax_act_2025_as_amended_by_fa_act_2026-pdf)
also refer to current or returned total income. Historical
[ITR-3 instructions, Annexure 5](https://www.incometax.gov.in/iec/foportal/sites/default/files/2021-05/Instructions_ITR3_AY2021_22.pdf)
allocate presumptive profit to March and other normal income earlier. The
implementation follows the observed utility split while retaining the statutory
cross-check.

The AY 2026-27 component probe does not establish TY 2026-27 utility behaviour,
CPC processing, or results for every credit, rebate, deduction, loss and
special-rate mix. Reconcile a filed return with the selected official utility or
a CA before treating payable/refund and regime savings as final.

## Sources and reproduction identifiers

The [official download page](https://www.incometax.gov.in/iec/foportal/downloads/income-tax-returns)
supplied these files. Version and hashes pin the inspected bytes.

| File | SHA-256 |
|---|---|
| [Common Mac v1.2.5 ZIP](https://www.incometax.gov.in/iec/foportal/sites/default/files/2026-10/ITDe-Filing-2026-1.2.5.dmg_.zip) | `061a8e0db0d4a7f15a2b5c5fb48b5a75dc4607edb5701bdb25a8cc41cbd0bfae` |
| [ITR-3 Excel v1.4 ZIP](https://www.incometax.gov.in/iec/foportal/sites/default/files/2026-10/ITR3_AY_26-27_V1.4.zip) | `01aa8e5c3275097ebec5a251d815467f0df6fc7705c397b16de58417ca6e586a` |
| [ITR-4 Excel v1.2 ZIP](https://www.incometax.gov.in/iec/foportal/sites/default/files/2026-08/ITR4_AY_26-27_V1.2.zip) | `8d3bdd230ae0e38cd6f79227e3d0aad3522d34580df3b51027cebb516fc436c0` |

The Mac executable embeds its frontend files under `frontend/dist/itr-offline/`.
The ITR-3 formula is the `Formula` entry for
`PartB_TTI.ComputationOfTaxLiability.IntrstPay.IntrstPayUs234C`.
The ITR-4 formula is the `Formula` entry for
`Total_Tax_Liability.Computatin_of_Tax.IntrstPayUs234C`.
Both use `JSONService.round` and `JSONService.dateDiff` from `main.js`.

| Extracted JavaScript file | SHA-256 |
|---|---|
| `projects_itr-offline_src_app_wrappers_itr3-lib-wrapper_module_ts.js` | `b6433737975a20e02f37eec755b5810791b730b65efb9e6c6bbe8149b8049598` |
| `projects_itr-offline_src_app_wrappers_itr4-lib-wrapper_module_ts.js` | `875b45644c2f057499725e47c2379034867c578619c4908abde1fd172b3f4519` |
| `main.js` | `9e5d5f75356709b3db0dcdd234138d5c78e0c7c3421fe61a7b7196b92807bb06` |
