# itr-wala

[![tests](https://github.com/karanb192/itr-wala/actions/workflows/tests.yml/badge.svg)](https://github.com/karanb192/itr-wala/actions/workflows/tests.yml)

**File your Indian income tax return from your terminal. No CA, no ₹3,000 fee, no 3 hours on the portal. Every rupee of tax math computed by tested code, not by an LLM.**

⏳ **AY 2026-27 deadlines: ITR-1/2 → 31 July 2026 · ITR-3/4 (non-audit) → 31 August 2026.**

```
# Review-first (recommended): clone, read it, install the bytes you just read
git clone https://github.com/karanb192/itr-wala.git
cd itr-wala && ./install.sh          # macOS / Linux / Git Bash (PowerShell: .\install.ps1)

# Or scope it to just the folder your tax documents live in
cd ~/tax-2026 && ~/itr-wala/install.sh --here    # PowerShell: .\install.ps1 -Here

# Claude Code plugin (name whichever repo you trust)
/plugin marketplace add karanb192/itr-wala
/plugin install itr-wala@itr-wala
```

Run from a checkout, `install.sh` **never touches the network** - it copies the files you just read. See [Install from a branch you reviewed](#install-from-a-branch-you-reviewed) for why that matters when the tool handles your salary and bank data.

![itr-wala demo: golden tests pass, income validates against document totals, both regimes computed - ₹42,811 found](demo/demo.gif)

Then open your agent and say **"file my ITR"**. Hand it your Form 16 and AIS. It does the rest - except the three things only you should ever do: **pay, submit, e-verify**.

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

1. **47 golden tests** - every expected value hand-derived from the statute first: the 87A rebate cliff and its marginal relief, capital-gains exemption ordering, s.71 loss set-off, the surcharge tiers (including the exclusive-income tests for the 25%/37% slabs and the 15% ceiling on capital-gains tax), and 234A/B/C/F interest down to the month-counting and challan-date edge cases.
2. **A 104-test suite for the input validator** - the gate that rejects malformed, mistyped, or PAN-bearing inputs before they can reach the engine.
3. **A property-based fuzzer** (`scripts/fuzz_engine.py`) - generates thousands of randomized, boundary-biased returns and asserts invariants the law implies: more income can never mean less tax in the new regime, cess is exactly 4%, rounding follows s.288A/288B, recommendations match the cheaper legal option. Seeded and deterministic; CI replays 3,000 cases on every commit, and 350,000+ were swept before release.

The skill runs the golden suite in front of you before touching your return:

```
$ python3 skills/itr-wala/scripts/test_tax_engine.py
...............................................
Ran 47 tests in 0.002s
OK
```

(Installed as a plugin and can't find the path? Just ask the agent to "run the itr-wala self-test".)

If your CA can show you their test suite, hire them.

These layers exist because they catch real bugs. Hand-deriving every scenario caught an early build that denied surcharge marginal relief on capital-gains-heavy incomes, and the fuzzer caught a one-in-350,000 floating-point rounding edge where ₹52,880 more salary computed ₹10 less tax. Both are fixed and pinned as regression tests. That find-fix-pin loop is the thing a prompt-only tax tool cannot run.

## What a session looks like

1. **Self-test** - the engine proves its math before you trust it.
2. **Documents** - drop Form 16 + AIS (JSON) into a folder; it tells you exactly where to download each one.
3. **Extract & validate** - every number transcribed verbatim into `income.json`, then a strict validator cross-checks totals against your documents. Unknown key? Rejected. TDS doesn't match 26AS? Flagged.
4. **Deduction hunt** - a proactive interview (80C, 80D, NPS, HRA, home loan…), because the portal will never ask you.
5. **Both regimes, computed** - a comparison table with the exact rupee savings. The regime gap is routinely five figures; this table is where it shows up.
6. **Filing pack** - every portal field mapped to its value, in order, plus the final payable/refund figure the portal must match to the rupee.
7. **The portal, together** - it narrates each schedule; you type. It never sees your password or OTP. You alone click Pay, Submit, and e-Verify.

## The artifact you actually share

Real output, reproducible from the bundled (fictional) example - `python3 skills/itr-wala/scripts/tax_engine.py skills/itr-wala/assets/example-income.json`:

```
Income-tax computation - FY 2025-26 (AY 2026-27)
================================================================
[NEW REGIME]
  Gross total income               26,06,700
  Total income                     25,06,700
  TOTAL TAX                         3,00,350
  NET PAYABLE (-ve=refund)               720

[OLD REGIME]
  Gross total income               22,09,300
  Total income                     18,74,300
  TOTAL TAX                         3,39,730
  NET PAYABLE (-ve=refund)            43,530

================================================================
  RECOMMENDED: NEW regime (saves Rs. 42,811)
```

## Privacy, honestly

- The **Python scripts run entirely on your machine**. Tax math never leaves.
- Documents you ask the AI to read are **processed by the model** - that part does leave your machine, like anything you paste into an AI tool. The skill tells you this up front and invites you to **redact PAN/Aadhaar/account numbers first**: they're not needed for computation, and that's enforced as a mechanism, not a plea - **the validator rejects any input file containing a PAN-shaped or Aadhaar-shaped string**.
- A generated `.gitignore` keeps tax documents out of your repos.
- Built by someone who [files his own taxes with it](https://karanbansal.in) - and who happens to do security for a living (DEFCON/OWASP speaker, Head of AI at an application-security company).

## What it covers (and refuses)

**In scope (AY 2026-27, resident individuals):** salary (multiple employers, retirement exemptions like gratuity and leave encashment in both regimes), house property including s.71 loss set-off, equity/MF capital gains (111A/112A/112, grandfathering-aware exemption ordering), debt MF, crypto/VDA, lottery and online-game winnings (115BB/115BBJ), interest & dividends, family pension with the s.57(iia) deduction, s.89 arrears relief, presumptive income (44AD/ADA basics), all Chapter VI-A deductions, both regimes, surcharge with marginal relief, advance-tax interest computed to actual challan dates, late fees, belated returns (including the s.115BAC(6) rule that locks belated filers out of the old regime - it will tell you, not let you find out from a notice), ITR-1/2/3/4 form selection.

**Out of scope - it will say so and point you to a CA rather than guess:** non-residents/RNOR, F&O and intraday, audit cases, foreign tax credit (Form 67/DTAA), ESOP deferral, the property indexation option, buyback capital-loss entries, agricultural income above ₹5,000. Partial coverage is computed honestly; the rest is never silently approximated.

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
Rates live in one constants block, pinned to AY 2026-27, with the test suite enforcing them. The skill refuses to compute other years rather than silently using stale slabs. New Finance Act → one PR → tests updated.

**Windows, macOS, and Linux are all supported.** On Windows PowerShell use `.\install.ps1`, or use `./install.sh` in Git Bash, WSL, or macOS/Linux.

## Install options

Clone first, then run `./install.sh` (or `.\install.ps1` on Windows PowerShell) from inside the checkout - it copies the files in front of you and makes no network calls at all.

**Which agent** - the positional argument:

| Tool | How (macOS/Linux/Git Bash) | How (Windows PowerShell) |
|---|---|---|
| Claude Code (plain skill) | `./install.sh` | `.\install.ps1` |
| OpenAI Codex CLI | `./install.sh codex` (invoke with `$itr-wala`) | `.\install.ps1 codex` |
| Gemini CLI | `./install.sh gemini` | `.\install.ps1 gemini` |
| Everything | `./install.sh all` | `.\install.ps1 all` |
| Claude Code plugin (updates with `/plugin marketplace update itr-wala`) | `/plugin marketplace add karanb192/itr-wala` → `/plugin install itr-wala@itr-wala` | Same |

**Global or project-local** - the scope flag:

| Scope | Command (Bash) | Command (PowerShell) | Lands in |
|---|---|---|---|
| Global (default) | `./install.sh all` | `.\install.ps1 all` | `~/.claude/skills/`, `~/.agents/skills/`, `~/.codex/skills/`, `~/.gemini/skills/` |
| Project-local | `cd ~/tax-2026 && /path/to/itr-wala/install.sh --here all` | `cd C:\tax-2026; \path\to\itr-wala\install.ps1 -Here all` | `~/tax-2026/.claude/skills/`, `.agents/skills/`, `.gemini/skills/` |
| Project-local, named | `./install.sh --project ~/tax-2026 all` | `.\install.ps1 -Project C:\tax-2026 all` | the same, without the `cd` |

**Project-local is usually the better fit for tax work.** The skill lives beside the return it prepared, so next year's copy cannot quietly follow you into unrelated projects, and deleting the folder removes it completely - which matters for a tool whose whole value is that you know exactly what version ran against your Form 16. Start your CLI from that directory (or below it) for the skill to be found.

Project-scoped discovery is well established for Claude Code (`.claude/skills/`) and for Codex via the cross-agent `.agents/skills/`; the per-project path is less settled for other CLIs, so if yours doesn't pick the skill up, check its docs for project-scoped skill locations and fall back to a global install. (`~/.codex/skills` is a global-only location - a project-local install skips it deliberately.)

Requirements: `python3` 3.9+ (stdlib only - zero pip installs), `git` only if you let the installer fetch rather than running it from a checkout.

## Install from a branch you reviewed

This tool reads your Form 16, AIS, bank interest and capital gains. For something in that position, "I read the code once" only means something if **the code you read is the code that runs**. A `curl … | bash` one-liner cannot give you that - it installs whatever is on `main` at the moment you run it, from a repo you do not control, and re-decides that question on every update. That is true of this repo as much as any other.

So the installer is built for a fork-review-pin workflow instead:

**1. Fork it.** Your fork is a snapshot you control. Nobody can change it under you.

**2. Read it.** The whole thing is ~4,200 lines with **zero third-party dependencies**, which is what makes a real review tractable in an evening. Worth confirming for yourself: no `import requests`/`urllib`/`socket` anywhere; `tax_engine.py` and `validate_income.py` read one JSON file and write only to stdout; no `eval`/`exec`/`base64`; the CI workflow uploads nothing. Check `.gitignore` covers the document names you actually use.

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
- One-click `.skill` bundle for Claude desktop

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
