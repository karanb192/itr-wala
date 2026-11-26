# Calculation corrections in 1.3.1

Recheck saved results from version 1.3.0 or earlier if any row applies. Both
FY 2025-26 and FY 2026-27 remain supported. A corrected result can change tax,
interest, the payment target or the regime comparison; it does not establish
that a filed return needs revision.

| Affected input | Previous behaviour | Correction |
|---|---|---|
| Two self-occupied home loans, especially alongside positive rental income | Applied the ₹2 lakh interest cap to each home | Applies one aggregate cap before combining property income |
| Late filing with income above the exemption before Chapter deductions, below it afterwards | Could omit the late fee | Tests the income-based filing obligation before those deductions; the fee amount still depends on total income |
| Business income with a valid old-regime election | Treated every late return as new-regime-only | Uses confirmed `business_regime`; missing election history makes the comparison provisional |
| House-property loss remaining after slab income, with several capital-gain categories | Fixed order could consume gains within the equity-LTCG exemption | Compares loss allocations, preserves that exemption where possible, and reports the chosen allocation |
| Employer NPS without `basic_plus_da` | Accepted the whole claim without a warning | Uses gross salary only as an upper bound and marks the result provisional until the eligible salary base is supplied |
| Medical-insurance claim over ₹1 lakh | Accepted an impossible aggregate claim | Validator rejects it; direct engine use caps it with a warning. Lower family-specific limits still require evidence |
| Central/State Government employer NPS under the old regime | Always used 10% when the salary base was present | `employer_type: "government"` uses 14%; `"other"` uses 10% old and 14% new |
| Slab income not already a multiple of ₹10 | Displayed rounded income but taxed the unrounded slab amount | Taxes the slab portion of rounded total income; special-rate buckets are not independently rounded to tens |

The medical-insurance ceiling is not a full eligibility calculator. The engine
still needs the documented eligible claim. HRA and donations also need a
documented computation or deterministic tool output; the model must not calculate them.

## Reproduced examples

Fictional annual tax including cess, before interest and fees unless stated.
These cases are pinned in `test_tax_engine.py` for both years.

| Input | Before | Corrected |
|---|---:|---:|
| Old regime, ₹6.8L gross salary, two self-occupied loans with ₹2L interest each, ₹3L rent from another property | ₹0 | ₹42,120 |
| Old regime, ₹3L presumptive income, ₹1L 80C, filed 15 September after the income year | Late fee ₹0 | Late fee ₹1,000 |
| Old regime, ₹2L house-property loss, ₹2L equity LTCG and ₹10L other LTCG | ₹97,500 | ₹81,250 |
| Old regime, ₹10,00,073 gross salary alone | ₹1,06,620 | ₹1,06,610 |

## Check an existing result

1. Preserve the original input and output. Update through your [existing install route](rebate-correction.md#update-your-existing-install); new computation JSON should identify engine `1.3.1` or later.
2. Keep the original `financial_year`, filing date and payment dates. Do not substitute today's date for a historical return.
3. Supply the missing NPS salary basis, employer category and business election history where relevant. Never infer an election from whichever regime is cheaper.
4. Recompute and compare with the filed return and processing intimation. Mirror the reported loss allocation in the official utility and check the final result there.
5. If a filed return differs, check the currently available correction route with the official portal or a CA before acting. This engine does not prepare revised or updated returns or their additional fees.

Existing files without the new optional fields remain readable. Each regime's
`input_verification_required` lists unresolved facts; the text output marks its
figures provisional. Do not use those figures as a final filing or payment instruction.
`comparison.savings` remains the absolute difference between the calculations;
`eligibility_locked` means the cheaper alternative may be unavailable.

The separate [mixed-presumptive instalment split](mixed-presumptive-interest.md)
now applies quarterly targets to the non-presumptive tax share and keeps the
presumptive share in March. Filing obligations triggered by specified transactions or
exemptions added back under the return-filing provisions are not fully modelled.

## Document handling

Use `decrypt_pdf.py` for encrypted AIS/TIS PDFs. It prompts without echo and
passes the password to qpdf over standard input. Decrypted PDF, AIS JSON and
26AS output files are created with owner-only permissions on POSIX systems;
Windows users should use a private folder with appropriate access permissions.
The validator also detects lowercase PAN and spaced or hyphenated Aadhaar shapes.

Missing OpenSSL now produces a dependency error. The AIS helper's existing
short-lived derived encryption key in the OpenSSL argument list remains unchanged;
these changes do not claim to remove every local-process exposure.

## Sources and limits

- Aggregate home-loan cap: [department house-property guide](https://incometaxindia.gov.in/tutorials/12.%20income-from-house-property.pdf); new Act s.22(5).
- Pre-deduction filing obligation: [s.139](https://www.incometaxindia.gov.in/w/section-139-59); new Act s.263(1)(a)(iii). Other mandatory filing triggers need separate verification.
- Business election: [Form 10-IEA FAQ, Q7/12/21](https://www.incometax.gov.in/iec/foportal/help/all-topics/e-filing-services/form%2010-iea-faq); new Act s.202(4).
- NPS and medical-insurance limits: [department deduction summary](https://www.incometaxindia.gov.in/w/deductions); new Act ss.124/126.
- Loss set-off and rounding: new Act ss.109/516 and [old Act s.288A](https://www.incometaxindia.gov.in/w/section-288a). Allocation is a statutory computation; no end-to-end official utility filing was performed for these cases.
- All new-Act counterparts: [Income-tax Act 2025 as amended by Finance Act 2026](https://www.incometaxindia.gov.in/documents/d/guest/income_tax_act_2025_as_amended_by_fa_act_2026-pdf).
- Hidden PDF password transport: [qpdf password-file documentation](https://qpdf.readthedocs.io/en/stable/cli.html#option-password-file).
