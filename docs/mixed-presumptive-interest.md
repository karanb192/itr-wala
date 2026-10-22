# Mixed presumptive income needs interest verification

If a return combines eligible presumptive income with salary, rent, interest or
gains, treat the engine's instalment interest and final payable/refund as
provisional. Reconcile them with the selected official utility or a CA before
filing. For advance-tax planning, confirm the schedule before relying on a
March-only target.

The engine keeps its statutory interpretation and arithmetic. Its JSON output
adds `verification_required` for eligible mixed-income cases with at least
₹10,000 liability after TDS/TCS in an evaluated regime. Text output shows that
notice before the figures. The notice names the affected regimes. For estimates,
the threshold uses expected annual credits.

Both supported financial years remain available, including historical
recomputation. This change does not adjust saved figures, introduce a new tax
rate, or certify that a return is ready.

## What was reproduced

On 20 October 2026, the unmodified ITR-3 and ITR-4 interest-calculation functions
from the official AY 2026-27 common Mac utility v1.2.5 were executed in an
isolated JavaScript context. The date and rounding helpers also came from that
bundle. Explicit fictional intermediate fields supplied the income, regime,
credits and payment dates. Missing input reads failed the probe.

This was a calculation-component test. It did not run the complete native app,
validate a complete return, submit one, or test CPC processing.

Each row uses the new regime, a regular-age resident individual, no deductions
beyond the salary standard deduction, and ₹3,00,000 advance tax on 10 March 2026.

| Fictional income | Engine 1.3.0 interest | ITR-3 component | ITR-4 component |
|---|---:|---:|---:|
| Salary ₹15L gross + 44AD profit ₹8L | ₹0 | ₹3,945 | ₹3,949 |
| Salary ₹15L gross + 44ADA profit ₹8L | ₹0 | ₹3,945 | ₹3,949 |
| Only 44AD profit ₹22.25L | ₹0 | ₹0 | ₹0 |
| Only salary ₹23L gross | ₹10,788 | ₹10,788 | ₹10,793 |

The mixed rows use total taxable income ₹22,25,000, including salary after
standard deduction of ₹14,25,000. Both components remove presumptive profit
from the first three quarters and include it in March. Their rounding differs.
The ₹10,788 alternative in [issue 19](https://github.com/karanb192/itr-wala/issues/19)
applies quarterly timing to the whole liability. It is not the observed
mixed-income result.

The current official Excel utilities corroborate the split through active
form-control and macro paths. ITR-3 v1.4 writes `Tax Calculated!R240` to the
normal-tax return output. ITR-4 v1.2 selects `TaxCalc!P51` for resident
presumptive income above the net-liability threshold. This Excel evidence is
static inspection, not a workbook execution.

## Why the arithmetic remains unchanged

The taxpayer-wide March interpretation follows
[s.211(1)(b)](https://www.incometaxindia.gov.in/w/section-211-64) and
[s.234C(1)(b)](https://www.incometaxindia.gov.in/w/section-234c-37).
For FY 2026-27, s.403(2), s.408(2) and s.425 of the
[amended 2025 Act](https://www.incometaxindia.gov.in/documents/d/guest/income_tax_act_2025_as_amended_by_fa_act_2026-pdf)
also refer to current or returned total income. The department's
[tax-payment FAQ](https://www.incometax.gov.in/iec/foportal/help/all-topics/e-filing-services/tax-payments-faq)
describes the entire liability for eligible presumptive taxpayers.

The official component behavior differs from that reading. Historical
[ITR-3 instructions, Annexure 5](https://www.incometax.gov.in/iec/foportal/sites/default/files/2021-05/Instructions_ITR3_AY2021_22.pdf)
also allocate presumptive profit to March and other normal income earlier.
That establishes a concrete reconciliation risk, not a settled legal conclusion.

A numerical correction needs a complete validated return for the selected form,
documented rounding treatment and coverage for credits, rebates, deductions,
losses and special-rate income. AY 2026-27 results do not establish TY 2026-27
utility behavior. [Issue 19](https://github.com/karanb192/itr-wala/issues/19)
remains open.

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
