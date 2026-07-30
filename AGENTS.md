# itr-wala

Agent skill for filing Indian income tax returns (ITR), FY 2025-26 / AY 2026-27.

- `DEFAULT_REPO` in `install.sh` must always name THIS repo, so any copy
  installs its own reviewed code by default - see CONTRIBUTING.md rule 5 and
  "Install from a branch you reviewed" in README.md.
- The skill lives at `skills/itr-wala/SKILL.md` (Agent Skills standard -
  works in Claude Code, Codex CLI, and Gemini CLI). Codex discovers it
  automatically inside this repo via `.agents/skills`.
- No install step is needed to use the skill from inside this repo: read
  `SKILL.md` and invoke the scripts by path. Installing only copies the skill
  somewhere an agent auto-discovers it - globally under `$HOME` by default,
  or into one project with `install.sh --here` / `--project DIR` (preferred
  for tax work: the skill sits beside the documents and nothing else sees it).
- All tax arithmetic is done by `skills/itr-wala/scripts/tax_engine.py`
  (stdlib-only Python, golden-tested). Agents must never compute tax figures
  themselves - see the Iron Rules in SKILL.md.
- Run the test suite before changing the engine:
  `python3 skills/itr-wala/scripts/test_tax_engine.py`
- Rates are pinned to AY 2026-27. A new assessment year means updating the
  constants block in `tax_engine.py`, the reference docs, and the golden
  tests together.
