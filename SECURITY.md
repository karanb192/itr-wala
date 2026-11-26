# Security Policy

itr-wala handles salary, bank and tax data, so security reports are handled privately and ahead of feature work.

## Reporting a vulnerability

Report privately. Do not open a public issue.

- Use [private vulnerability reporting](https://github.com/karanb192/itr-wala/security/advisories/new) on this repository.

This is a one-maintainer project. I aim to acknowledge a report within a week. Once fixed, reporters are credited in the release notes unless they prefer otherwise.

**Never include real tax data in a report.** No PAN, Aadhaar, account numbers, documents or portal screenshots with identifiers. Reproduce the problem with made-up data, whichever fits the report: a minimal `income.json` built from `skills/itr-wala/assets/example-income.json`, a fictional document, or the install command you ran.

## In scope

- The installer (`install.sh`) fetching, writing or running something other than the files in the checkout or the ref you named.
- A crafted document or `income.json` that makes a script execute code, write outside its working folder or reach the network.
- Personal data, such as a PAN, written to logs, test fixtures or any file the tool creates outside your tax folder.
- A way to make the skill pay, submit or e-verify. Those three steps belong to the taxpayer.
- The validator accepting input it documents as refused, such as PAN-shaped strings.

## Not a vulnerability

- **Documents you hand the AI are read by the model.** That leaves your machine, like anything you paste into an AI tool. It is the tool's stated tradeoff, described in the README under "Privacy, honestly".
- **A wrong tax figure.** That is a bug with top priority, not a security issue. Open a public issue with a minimal `income.json`.

## Supported versions

Fixes land on the `main` branch. Update by the route you installed with, keeping the same install scope: see [Update your existing install](docs/rebate-correction.md#update-your-existing-install). If you pinned a commit with `ITR_WALA_REF`, review the fix and move the pin.
