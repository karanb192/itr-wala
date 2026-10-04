# itr-wala

[![tests](https://github.com/karanb192/itr-wala/actions/workflows/tests.yml/badge.svg)](https://github.com/karanb192/itr-wala/actions/workflows/tests.yml) [![skills.sh installs](https://skills.sh/b/karanb192/itr-wala)](https://skills.sh/karanb192/itr-wala) [![GitHub stars](https://img.shields.io/github/stars/karanb192/itr-wala?style=flat-square)](https://github.com/karanb192/itr-wala/stargazers)

**File your Indian income tax return from your terminal. No CA, no ₹3,000 fee, no 3 hours on the portal. Every rupee of tax math computed by tested code, not by an LLM.**

**New: plan FY 2026-27 advance tax alongside existing FY 2025-26 filing support.**

⏳ **For supported non-audit AY 2026-27 returns, the original due date was 31 July without business/profession or 31 August with business/profession. You can still file a belated return until 31 December 2026, or assessment completion if earlier: late fee ₹1,000 if income is up to ₹5 lakh, else ₹5,000 (section 234F), plus applicable interest.** [Statutory dates](https://egazette.gov.in/WriteReadData/2026/271439.pdf).

> **Seen in the wild:** a [reel by @ezsnippet](https://www.instagram.com/reels/DcbBPwszsVR/) (3.7M followers) walked through this repo: *"ab tum bina CA ke bhi Income Tax return bhar sakte ho, ITR-Wala use karke."* 1.2M views in a week, and the repo's busiest week so far. Filed with itr-wala? [Two lines in this thread](https://github.com/karanb192/itr-wala/issues/10) help the next filer.

```
# Review-first (recommended): clone, read it, install the bytes you just read
git clone https://github.com/karanb192/itr-wala.git
cd itr-wala && ./install.sh          # also: codex, gemini, all

# Or scope it to just the folder your tax documents live in
cd ~/tax-2026 && ~/itr-wala/install.sh --here

# Claude Code plugin (name whichever repo you trust)
/plugin marketplace add karanb192/itr-wala
/plugin install itr-wala@itr-wala

# Codex plugin (same repo doubles as a Codex marketplace)
codex plugin marketplace add https://github.com/karanb192/itr-wala
codex plugin add itr-wala@itr-wala

# Or the skills.sh one-liner (fetches the default branch head; pick your agent when prompted)
npx skills add karanb192/itr-wala
```

Run from a checkout, `install.sh` **never touches the network** - it copies the files you just read. See [Install from a branch you reviewed](#install-from-a-branch-you-reviewed) for why that matters when the tool handles your salary and bank data.

Historical FY 2025-26 recording (July 2026): the GIF shows the earlier 47-test build. Run the current self-test for the current suite and year selection.

![itr-wala demo: golden tests pass, income validates against document totals, both regimes computed - ₹42,811 found](demo/demo.gif)

Then open your agent and say **"file my ITR"**. Hand it your Form 16 and AIS. It does the rest - except the three things only you should ever do: **pay, submit, e-verify**.

Or say **"Plan my advance tax for FY 2026-27"**. It asks for an as-of date,
your approved annual forecast, expected full-year TDS/TCS and actual paid
challans. Python computes the next payment. Forecasts stay labelled as estimates;
they never become filing figures without final evidence. No future filing fees,
interest assessment or estimated refund is mixed into the payment target.
See [the advance-tax workflow](skills/itr-wala/references/advance-tax.md).

The agent confirms **which financial year** and whether you are **filing a return or planning advance tax**.
Each year has its own dates and legal labels; an unknown year is rejected.

| Income year | What you can use it for | Legal year |
|---|---|---|
| FY 2025-26, April 2025 to March 2026 | Return preparation and belated filing | AY 2026-27, Income-tax Act 1961 |
| FY 2026-27, April 2026 to March 2027 | Annual tax comparison and advance-tax targets, including 15 December 2026 and 15 March 2027 | Tax Year 2026-27, Income-tax Act 2025 |

For FY 2026-27, final return forms and portal fields must be verified before
filing guidance. The bundled AY 2026-27 walkthrough remains for FY 2025-26.
See the [new-year rules and sources](skills/itr-wala/references/rates-fy2026-27.md).
The government [estimator manual](https://www.incometax.gov.in/iec/foportal/help/all-topics/e-filing-services/income-and-tax-estimator-um)
also distinguishes these two legal years.

## Existing-user calculation correction

Engine 1.2.0 could understate FY 2025-26 new-regime tax when special-rate income
pushed total income above ₹12 lakh. The correction adds ₹62,400 in the illustrated
no-surcharge case and more when surcharge applies, before any resulting interest.
If you relied on that engine, recompute and compare with
your filed return and any processing intimation. See the [affected-input examples
and next steps](docs/rebate-correction.md). A model-independent engine can still
contain bugs; the tests do not replace review.

## Why this exists

Every AI-tax demo you saw this season had the same silent flaw: **the model was doing the arithmetic.** LLMs are magnificent at reading a Form 16 and terrible at applying s.87A marginal relief. One transposed digit and your "free filing" costs you a tax notice.

itr-wala splits the work the way it should be split:

| The AI does | Deterministic Python does |
|---|---|
| Reads your Form 16, AIS, broker P&L | Every slab, rebate, surcharge, cess calculation |
| Interviews you for missed deductions | Old vs new regime comparison |
| Explains every number in plain language | 87A marginal relief, 111A/112A/VDA special rates |
| Walks you through the portal | 234A/B/C interest, 234F late fee |
| | Schema validation that rejects typo'd inputs |
| | Cross-checks your TDS against 26AS/AIS totals |

The math is defended in three layers, all shipped in the repo and run in CI on every commit:

1. **84 tax tests** with hand-derived rupee expectations: rebates on total income including special gains, marginal relief, both-year rate goldens, surcharge and loss set-off, challan dates, expected credits, senior exemption and mixed presumptive income.
2. **127 validator tests** reject malformed, mistyped, PAN-bearing or wrong-year inputs, forecasts mixed into returns, and future payments counted as already paid.
3. **A property-based fuzzer** (`scripts/fuzz_engine.py`) checks determinism, rounding, cess, component totals, comparisons, income monotonicity and payment targets. CI runs 3,000 cases for each year/purpose combination, 12,000 per Python version. A fresh 360,000-case sweep (90,000 per combination, seed 42) passed on the revised engine. The earlier FY 2025-26 release also underwent its 350,000+ case sweep.

The skill runs the golden suite in front of you before touching your return:

```sh
python3 skills/itr-wala/scripts/test_tax_engine.py
```

The suite must finish with `OK` before the workflow continues.

(Installed as a plugin and can't find the path? Just ask the agent to "run the itr-wala self-test".)

If your CA can show you their test suite, hire them.

These layers exist because they catch real bugs. Hand-deriving every scenario caught an early build that denied surcharge marginal relief on capital-gains-heavy incomes, and the fuzzer caught a one-in-350,000 floating-point rounding edge where ₹52,880 more salary computed ₹10 less tax. Both are fixed and pinned as regression tests. That find-fix-pin loop is the thing a prompt-only tax tool cannot run.

## What a session looks like

1. **Year and purpose, then self-test** - confirm which income year and whether this is a return or an advance-tax estimate.
2. **Documents** - drop Form 16 + AIS (JSON) into a folder; it tells you exactly where to download each one.
3. **Extract & validate** - every number transcribed verbatim into `income.json`, then a strict validator cross-checks totals against your documents. Unknown key? Rejected. TDS doesn't match 26AS? Flagged.
4. **Deduction hunt** - a proactive interview (80C, 80D, NPS, HRA, home loan…), because the portal will never ask you.
5. **Both regimes, computed** - a comparison table with the exact rupee savings. The regime gap is routinely five figures; this table is where it shows up.
6. **Filing pack** - every portal field mapped to its value, in order, plus the final payable/refund figure the portal must match to the rupee.
7. **The portal, together** - it narrates each schedule; you type. It never sees your password or OTP. You alone click Pay, Submit, and e-Verify.

## The artifact you actually share

Real output, reproducible from the bundled (fictional) example - `python3 skills/itr-wala/scripts/tax_engine.py skills/itr-wala/assets/example-income.json`:

```
Income-tax computation for FY 2025-26 (AY 2026-27)
Income-tax Act, 1961
================================================================

[NEW REGIME]
  Gross total income                                    26,06,700
  Deductions                                             1,00,000
  Total income                                          25,06,700
  Tax on slab income                                     2,75,425
  s.111A STCG (equity)                                      9,000
  s.112A LTCG (equity)                                      4,375
  Cess (4%)                                                11,552
  TOTAL TAX                                              3,00,350
  Instalment interest s.234C                                  366
  NET PAYABLE (-ve=refund)                                    720

[OLD REGIME]
  Gross total income                                    22,09,300
  Deductions                                             3,35,000
  Total income                                          18,74,300
  Tax on slab income                                     3,13,290
  s.111A STCG (equity)                                      9,000
  s.112A LTCG (equity)                                      4,375
  Cess (4%)                                                13,067
  TOTAL TAX                                              3,39,730
  Advance-tax shortfall interest s.234B                     1,588
  Instalment interest s.234C                                2,209
  NET PAYABLE (-ve=refund)                                 43,530

================================================================
  RECOMMENDED: NEW regime (saves Rs. 42,811)
  New: 3,00,716   Old: 3,43,527
```

An advance-tax estimate is reproducible too:

```sh
python3 skills/itr-wala/scripts/validate_income.py skills/itr-wala/assets/example-advance-fy2026-27.json
python3 skills/itr-wala/scripts/tax_engine.py skills/itr-wala/assets/example-advance-fy2026-27.json
```

The fictional [fixture](skills/itr-wala/assets/example-advance-fy2026-27.json)
uses ₹20L of other-source income, no salary, as of 10 December 2026. New-regime
annual tax is ₹2,08,000; less ₹8,000 expected annual TDS gives ₹2,00,000.
The December cumulative target is ₹1,50,000; less ₹90,000 already paid leaves
**₹60,000 by 15 December 2026**. The old-regime comparison is ₹2,25,750.
Choose one payment plan after confirming the applicable regime. These are
fixture results, not a ₹20L salary example.

## Optional invitation

After filing is complete, the skill may offer one optional star invitation. An advance-tax estimate does not trigger it.
It records the offer in `~/.cache/itr-wala/star-invitation.json`
(or under `XDG_CACHE_HOME`) before asking, so later conversations skip it.
Clearing the cache or using another machine can reset the record. Starring
through GitHub CLI requires an explicit yes. If the helper cannot run or
write its record, the skill skips the invitation.

## Privacy, honestly

- The **Python scripts run entirely on your machine**. Tax math never leaves.
- Documents you ask the AI to read are **processed by the model** - that part does leave your machine, like anything you paste into an AI tool. The skill tells you this up front and invites you to **redact PAN/Aadhaar/account numbers first**: they're not needed for computation, and that's enforced as a mechanism, not a plea - **the validator rejects any input file containing a PAN-shaped or Aadhaar-shaped string**.
- A generated `.gitignore` keeps tax documents out of your repos.
- Built by someone who [files his own taxes with it](https://karanbansal.in) - and who happens to do security for a living (DEFCON/OWASP speaker, Head of AI at an application-security company).

## What it covers (and refuses)

**In scope (AY 2026-27, resident individuals):** salary (multiple employers, retirement exemptions like gratuity and leave encashment in both regimes), house property including s.71 loss set-off, equity/MF capital gains (111A/112A/112, grandfathering-aware exemption ordering), debt MF, crypto/VDA, lottery and online-game winnings (115BB/115BBJ), interest & dividends, family pension with the s.57(iia) deduction, s.89 arrears relief, eligible presumptive income (44AD/44ADA; 44AE excluded), supported Chapter VI-A deductions, both regimes, surcharge with marginal relief, advance-tax interest computed to actual challan dates, late fees, belated returns (including the s.115BAC(6) rule that locks belated filers out of the old regime - it will tell you, not let you find out from a notice), ITR-1/2/3/4 form selection.

**FY 2026-27:** the same supported income categories have annual computation and advance-tax planning, with expected annual credits and dated payments.
For FY 2026-27, annual computation works after year end; notified return forms
and the official utility must be checked before producing a portal field map.
Revised returns and their fees remain unsupported.

**Out of scope:** non-residents/RNOR, F&O/intraday, audit, foreign tax credit,
ESOP deferral, property indexation caps, buyback loss entries and FY 2026-27
buybacks, SGB exemption classification, business-trust distribution
classification, agricultural income above ₹5,000, and unsupported years.
Government old-regime NPS and income-timing interest exceptions need separate
review; adding a year does not add those capabilities.

**Hard boundaries, always:** never your password or OTP, never clicks Pay/Submit/e-Verify, never fabricates a deduction. Lowest *legal* tax.

## FAQ

**Can I trust an LLM with my taxes?**
No - that's the point. You're trusting a tested Python engine with the math and an LLM with reading PDFs and explaining things, which are the two things each is actually good at. Run the test suite yourself.

**But the LLM still reads the documents - what if it misreads a number?**
True, and worth being precise about: transcription is the one step the model touches, so a misread digit is the residual risk. That's why every figure is cross-checked against *independent* documents (Form 16 vs 26AS vs AIS - a single-document misread fails validation), recorded next to its source citation, and shown to you in the filing pack before anything is filed. If the model misreads and every cross-check misses it, you'll see the wrong number *with its citation* - not a hidden one.

**Why not just use ClearTax/Quicko/a CA?**
Use whatever you trust. This is for people who'd rather review every number themselves than pay ₹3,000+ to hope someone else did. The filing pack it generates is also a great ₹0 first draft to hand a CA for a cheap review.

**Is this allowed?**
Yes. You prepare your own return and file it yourself on the government portal - same as using the portal's own forms, just with better preparation. This tool never submits anything on your behalf.

**What happens next year?**
Select the income year explicitly. FY 2025-26 and FY 2026-27 are supported;
other years fail closed. Covered numerical rates are shared only where the
reviewed statutes agree, while dates and legal labels come from a year profile.
Legacy JSON without a year still uses FY 2025-26 with a warning. A later
Finance Act needs another sourced rule review and hand-derived tests.

**Windows?**
WSL works today; native Windows paths are on the roadmap. macOS and Linux are first-class.

## Install options

Clone first, then run `./install.sh` from inside the checkout - it copies the files in front of you and makes no network calls at all.

**Which agent** - the positional argument:

| Tool | How |
|---|---|
| Claude Code (plain skill) | `./install.sh` |
| OpenAI Codex CLI | `./install.sh codex` (invoke with `$itr-wala`) |
| Gemini CLI | `./install.sh gemini` |
| Everything | `./install.sh all` |
| Claude Code plugin (updates with `/plugin marketplace update itr-wala`) | `/plugin marketplace add karanb192/itr-wala` → `/plugin install itr-wala@itr-wala` |
| OpenAI Codex plugin (updates with `codex plugin marketplace upgrade`) | `codex plugin marketplace add https://github.com/karanb192/itr-wala` → `codex plugin add itr-wala@itr-wala` |
| [skills.sh](https://skills.sh/karanb192/itr-wala) CLI, any supported agent | `npx skills add karanb192/itr-wala` (fetches the default branch head; built-in agent picker) |

**Global or project-local** - the scope flag:

| Scope | Command | Lands in |
|---|---|---|
| Global (default) | `./install.sh all` | `~/.claude/skills/`, `~/.agents/skills/`, `~/.codex/skills/`, `~/.gemini/skills/` |
| Project-local | `cd ~/tax-2026 && /path/to/itr-wala/install.sh --here all` | `~/tax-2026/.claude/skills/`, `.agents/skills/`, `.gemini/skills/` |
| Project-local, named | `./install.sh --project ~/tax-2026 all` | the same, without the `cd` |

**Project-local is usually the better fit for tax work.** The skill lives beside the return it prepared, so next year's copy cannot quietly follow you into unrelated projects, and deleting the folder removes it completely - which matters for a tool whose whole value is that you know exactly what version ran against your Form 16. Start your CLI from that directory (or below it) for the skill to be found.

Project-scoped discovery is well established for Claude Code (`.claude/skills/`) and for Codex via the cross-agent `.agents/skills/`; the per-project path is less settled for other CLIs, so if yours doesn't pick the skill up, check its docs for project-scoped skill locations and fall back to a global install. (`~/.codex/skills` is a global-only location - a project-local install skips it deliberately.)

Requirements: `python3` 3.9+ (stdlib only - zero pip installs), `git` only if you let the installer fetch rather than running it from a checkout.

## Install from a branch you reviewed

This tool reads your Form 16, AIS, bank interest and capital gains. For something in that position, "I read the code once" only means something if **the code you read is the code that runs**. A `curl … | bash` one-liner cannot give you that - it installs whatever is on `main` at the moment you run it, from a repo you do not control, and re-decides that question on every update. That is true of this repo as much as any other.

So the installer is built for a fork-review-pin workflow instead:

**1. Fork it.** Your fork is a snapshot you control. Nobody can change it under you.

**2. Read it.** The computation and validation scripts use **zero third-party dependencies**. Worth confirming for yourself: no `import requests`/`urllib`/`socket` anywhere; `tax_engine.py` and `validate_income.py` read one JSON file and write only to stdout; no `eval`/`exec`/`base64`; the CI workflow uploads nothing. Check `.gitignore` covers the document names you actually use.

**3. Point the installer at your fork** - one line, near the top of `install.sh`:

```bash
DEFAULT_REPO="https://github.com/karanb192/itr-wala.git"   # point this at YOUR repo
```

It must name the repo the script *lives in*. An installer defaulting to a repo its operator does not control re-introduces the exact problem this avoids.

**4. Pin what you reviewed**, if you install somewhere other than the checkout:

| Variable | Effect |
|---|---|
| `ITR_WALA_REF=<sha\|tag\|branch>` | Fetch exactly this commit. Pin the SHA you reviewed and updates stop being silent |
| `ITR_WALA_NO_FETCH=1` | Refuse to reach the network at all; install only from a real checkout |
| `ITR_WALA_REPO=<url>` | Pull from a different repo - e.g. `https://github.com/karanb192/itr-wala.git` for the original. Explicit opt-in, never the default |

Worked example - install a specific reviewed commit on a second machine:

```bash
ITR_WALA_REF=05c88d0 ./install.sh all
#   fetched commit 05c88d0cf13f45528039b77c3e61542a15783b51
```

The installer prints the resolved commit hash on every fetch, so an unattended run stays auditable after the fact.

**What this does not fix.** Reviewing the code does not change the tool's central privacy tradeoff: the Python runs locally, but the *documents you hand the AI are read by the model*, and that leaves your machine. See [Privacy, honestly](#privacy-honestly). Pinning also cannot vouch for a document you were sent - the model reads whatever text a PDF contains.

*Everything above except the `DEFAULT_REPO` value is generic - it works unchanged in this repo, in the original, and in any fork of either, because the repo a copy lives in is the only thing that distinguishes them. Patches welcome in any direction.*

## Roadmap

- Generate the **offline-utility upload JSON** against the official published schema (upload one file instead of typing 20 schedules). The format's empirical traps (schema-valid files that import blank, the camelCase-prefill trap) are documented by [CivicTaxes](https://github.com/CivicResources/CivicTaxes/blob/main/docs/utility-json-contract.md) (MIT, community-maintained)
- RSU/ESPP + Schedule FA depth (the most underserved, highest-anxiety segment). For bulk FA entry, [CivicTaxes' CSV upload doc](https://github.com/CivicResources/CivicTaxes/blob/main/docs/csv-upload-format.md) records what the utility's parser actually accepts
- Revised-return (s.139(5)) workflow through 31 Mar 2027 - belated returns already work, so this repo doesn't expire on Aug 1
- Native Windows installer · one-click `.skill` bundle for Claude desktop

## Contributing

This is meant to be a community tool. Rates change every Finance Act, portal notes rot mid-season, and edge cases surface all year. PRs and issues are welcome - see [CONTRIBUTING.md](CONTRIBUTING.md). The one hard rule: any change to a tax figure ships with a hand-derived test and its statutory source.

## Found a bug?

It's filing season - bug reports get priority, wrong-rate reports get top priority.

- **Computation bug:** open an issue with a *minimal* `income.json` that reproduces it. Start from `skills/itr-wala/assets/example-income.json` and change only what's needed. **Never paste your real numbers, documents, PAN, or portal screenshots with identifiers.** The validator refuses PAN-shaped strings for exactly this reason.
- **Doc/portal-flow bug:** quote the reference file and line; the portal changes often and field notes rot fastest.

## Credits

- [shivprime94/file-itr](https://github.com/shivprime94/file-itr) (MIT) - the first Indian ITR skill; its hard-won portal field notes and AIS SFT-code research informed our reference docs. This project's thesis is different (deterministic engine + validators + tests vs. pure prompting), but they walked first.
- [robbalian/claude-tax-filing](https://github.com/robbalian/claude-tax-filing) - proved the scripts-not-vibes pattern for US returns.
- [anthropics/skills](https://github.com/anthropics/skills) - the skill-structure conventions this follows.

## License

MIT - see [LICENSE](LICENSE). Reference material adapted from the MIT-licensed [file-itr](https://github.com/shivprime94/file-itr).

## Disclaimer

itr-wala is open-source software, not a chartered accountant, and nothing here is professional tax advice. It computes with tested code and shows you everything, but **you** review, you file, and responsibility for your return stays with you. When in doubt, hand the generated filing pack to a CA - it's built for exactly that.

---

*Found it useful? Send it to the friend who still hasn't filed. ⭐*
