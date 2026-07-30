# Contributing

Thanks for wanting to make Indian tax filing less painful. Contributions of every size are welcome, from a typo in a portal note to next year's rate tables. A few rules keep this tool trustworthy; everything else is fair game.

## Ground rules

1. **The engine stays deterministic and dependency-free.** `tax_engine.py` and `validate_income.py` are stdlib-only Python 3.9+. No pip installs, ever. That is what lets anyone run them anywhere and read every line.
2. **Every rupee change ships with a test.** If your PR changes any computed figure, add a golden test to `test_tax_engine.py` with the expected value derived by hand from the statute, and cite the section plus a source link in the PR description. The test comes from the law, never from the engine's own output.
3. **The LLM never does arithmetic.** Everything in `SKILL.md` and `references/` must keep computation inside the scripts. If you find prose that invites the model to calculate anything itself, that is a bug worth an issue on its own.
4. **No real tax data, anywhere.** No real PAN, Aadhaar, names, or figures from an actual return in issues, PRs, or test fixtures. Start from `skills/itr-wala/assets/example-income.json` and change only what you need. The validator rejects PAN-shaped and Aadhaar-shaped strings by design; do not work around it.
5. **The installer defaults to its own repo.** `DEFAULT_REPO` in `install.sh` must name the repository the script lives in - every copy points it at itself. An installer defaulting to a repo its operator does not control means every install silently re-trusts code nobody reviewed, which defeats the point of a tool this auditable. Its *value* is the one line that legitimately differs between any two copies of this project; everything else (`ITR_WALA_REF`, `ITR_WALA_NO_FETCH`, `ITR_WALA_REPO`, the scope flags) must stay generic, so the mechanism merges cleanly in any direction. Resist adding knobs that only make sense downstream of somewhere - "install the *other* repo's version" is already `ITR_WALA_REPO=<url>`.

## Running the tests

From the repo root:

```bash
python3 skills/itr-wala/scripts/test_tax_engine.py        # golden tests, hand-derived expected values
python3 skills/itr-wala/scripts/test_validate_income.py   # input validator suite
python3 skills/itr-wala/scripts/fuzz_engine.py            # property-based fuzzer (seeded, deterministic)
```

All three must pass. CI runs them on Python 3.9 and 3.12, plus a 3,000-case fuzz sweep, on every push and PR.

## What help is most wanted

- **Wrong-rate or wrong-interest reports.** Top priority in season. Open an issue with a minimal `income.json` repro and what the figure should be, with the section of the Act.
- **Portal walkthrough fixes.** `references/portal-walkthrough.md` rots fastest because the e-filing portal changes without notice. Quote the file and line you are correcting.
- **Coverage gaps.** RSU/ESPP and Schedule FA, the s.112 property indexation option, revised returns, native Windows support. Check the README roadmap before starting something big, and open an issue first for anything that touches the engine.
- **Next year.** When the Finance Act changes rates, the constants block in `tax_engine.py`, the reference docs, and the golden tests all move together in one PR.

## Style

Match what is already there: plain Python, no type-annotation ceremony, comments only where the statute forces something non-obvious. Reference docs are written for an agent to read mid-filing, so keep them terse and factual.
