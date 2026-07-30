#!/usr/bin/env bash
# itr-wala installer - copies the skill into your agent's skills directory.
#
# PREFERRED: clone the repo, read it, then run it from the checkout. The
# script installs the bytes you just reviewed and never touches the network:
#
#   ./install.sh            # Claude Code
#   ./install.sh codex      # OpenAI Codex CLI
#   ./install.sh gemini     # Gemini CLI
#   ./install.sh all        # all of the above
#
# Scope: global (into $HOME) by default. Or install PROJECT-LOCAL, beside the
# documents the skill works on, so it exists only in that one project:
#
#   cd ~/tax-2026 && /path/to/itr-wala/install.sh --here
#   ./install.sh --project ~/tax-2026 all
#
# Run outside a checkout, it clones $REPO - which every copy points at ITSELF,
# so an unattended run can never silently pull code nobody reviewed. Override:
#
#   ITR_WALA_REF=<sha|tag|branch> ./install.sh   # pin an exact reviewed commit
#   ITR_WALA_NO_FETCH=1 ./install.sh             # refuse to fetch at all
#   ITR_WALA_REPO=<url> ./install.sh             # pull from a different repo
#
# Claude Code users can skip this entirely (name whichever repo you trust):
#   /plugin marketplace add karanb192/itr-wala
#   /plugin install itr-wala@itr-wala
#
# macOS and Linux. Windows: use WSL, or copy skills/itr-wala into
# %USERPROFILE%\.claude\skills manually.

set -euo pipefail

# --- Repo identity: the one line that differs between any two copies -------
# Everything else here is generic - it works unchanged in a fork AND in the
# original, because "the repo this script lives in" is the only thing that
# distinguishes them. DEFAULT_REPO must name THAT repo: an installer that
# defaults to a repo its operator does not control re-introduces exactly the
# trust-on-every-install problem the review-first workflow exists to remove.
# To pull from anywhere else, name it explicitly - e.g. the original project:
#   ITR_WALA_REPO=https://github.com/karanb192/itr-wala.git ./install.sh
DEFAULT_REPO="https://github.com/karanb192/itr-wala.git"   # point this at YOUR repo
# ---------------------------------------------------------------------------

# Remote source, used ONLY when this script is not run from a checkout.
REPO="${ITR_WALA_REPO:-$DEFAULT_REPO}"
REF="${ITR_WALA_REF:-}"        # empty = default-branch tip (unpinned)
SKILL="itr-wala"

usage() {
  echo "Usage: install.sh [--here | --project DIR] [claude|codex|gemini|all]"
  echo "  --here          install into the current directory (project-local)"
  echo "  --project DIR   install into DIR (project-local)"
  echo "  default         install into \$HOME (global, all projects)"
}

# BASE is the root the agent skill directories hang off: $HOME for a global
# install, a project directory for a local one. Everything downstream just
# writes under $BASE, so the two scopes share one code path.
BASE="$HOME"
SCOPE="global"
TARGET=""
while [ $# -gt 0 ]; do
  case "$1" in
    --here)
      SCOPE="project"; BASE="$PWD" ;;
    --project)
      SCOPE="project"
      if [ $# -lt 2 ]; then
        echo "ERROR: --project needs a directory (e.g. --project ~/tax-2026)" >&2
        exit 1
      fi
      if [ ! -d "$2" ]; then
        echo "ERROR: --project '$2' is not a directory." >&2
        exit 1
      fi
      BASE="$(cd "$2" && pwd)"; shift ;;
    -h|--help) usage; exit 0 ;;
    claude|codex|gemini|all) TARGET="$1" ;;
    *)
      echo "ERROR: unknown argument '$1'" >&2
      usage >&2
      exit 1 ;;
  esac
  shift
done
TARGET="${TARGET:-claude}"

# init+fetch rather than clone: resolves a tag, branch OR commit SHA through
# one path, so ITR_WALA_REF can pin an exact reviewed commit. Every step gates
# the next explicitly - `set -e` does NOT apply inside a command on the left of
# `||`, so a failed fetch would otherwise fall through to the checkout.
fetch_source() {
  export GIT_TERMINAL_PROMPT=0        # fail instead of hanging on a credential prompt
  git init --quiet "$SRC" || return 1
  git -C "$SRC" remote add origin "$REPO" || return 1
  git -C "$SRC" fetch --depth 1 --quiet origin "${REF:-HEAD}" || return 1
  git -C "$SRC" checkout --quiet FETCH_HEAD || return 1
}

if [ -f "$(dirname "$0")/skills/$SKILL/SKILL.md" ]; then
  SRC="$(cd "$(dirname "$0")" && pwd)"
  echo "Installing from local checkout: $SRC"
elif [ "${ITR_WALA_NO_FETCH:-0}" = "1" ]; then
  echo "ERROR: ITR_WALA_NO_FETCH=1 and no checkout found beside this script." >&2
  echo "       Clone the repo and run ./install.sh from inside it." >&2
  exit 1
else
  SRC="$(mktemp -d)"
  trap 'rm -rf "$SRC"' EXIT
  echo "Fetching $REPO${REF:+ @ $REF} ..."
  if ! fetch_source; then
    echo "ERROR: could not fetch ${REF:-HEAD} from $REPO - check your network," >&2
    echo "       the URL, and that the ref exists." >&2
    exit 1
  fi
  echo "  fetched commit $(git -C "$SRC" rev-parse HEAD)"
fi

INSTALLED=()
install_into() {
  mkdir -p "$1"
  if [ -e "$1/$SKILL" ]; then
    echo "  replacing existing install at $1/$SKILL"
    rm -rf "${1:?}/$SKILL"
  fi
  cp -R "$SRC/skills/$SKILL" "$1/$SKILL"
  find "$1/$SKILL" -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true
  find "$1/$SKILL" -name '*.pyc' -delete 2>/dev/null || true
  INSTALLED+=("$1/$SKILL")
  echo "  installed -> $1/$SKILL"
}

install_codex_home() {
  # ~/.codex/skills is the original, global-only Codex location. A
  # project-local install uses the cross-agent .agents/skills alone.
  if [ "$SCOPE" = "global" ]; then
    install_into "${CODEX_HOME:-$HOME/.codex}/skills"
  fi
}

if [ "$SCOPE" = "project" ]; then
  echo "Scope: project-local -> $BASE"
  if [ "$BASE" = "$SRC" ]; then
    echo "  NOTE: that is this repo - you are installing the skill into its own" >&2
    echo "        source tree. You probably want the directory your tax documents" >&2
    echo "        live in: install.sh --project ~/your-tax-folder" >&2
  fi
else
  echo "Scope: global -> $BASE"
fi

case "$TARGET" in
  claude)  install_into "$BASE/.claude/skills" ;;
  codex)
    install_into "$BASE/.agents/skills"   # current cross-agent standard location
    install_codex_home
    ;;
  gemini)  install_into "$BASE/.gemini/skills" ;;
  all)
    install_into "$BASE/.claude/skills"
    install_into "$BASE/.agents/skills"
    install_codex_home
    install_into "$BASE/.gemini/skills"
    ;;
esac

echo
echo "Verifying the tax engine (golden test suite) in each installed copy..."
FAILED=0
for dest in "${INSTALLED[@]}"; do
  if PYTHONDONTWRITEBYTECODE=1 python3 "$dest/scripts/test_tax_engine.py" >/dev/null 2>&1; then
    echo "  OK   $dest"
  else
    echo "  FAIL $dest - run: python3 $dest/scripts/test_tax_engine.py" >&2
    FAILED=1
  fi
done
if [ "$FAILED" -ne 0 ]; then
  echo "WARNING: verification failed (is python3 3.9+ on PATH?). Do not trust the skill until the self-test passes." >&2
fi

echo
if [ "$SCOPE" = "project" ]; then
  echo "Done. The skill is local to $BASE - start your CLI from"
  echo "that directory (or below it) and only that project sees it."
  echo "Your tax documents still need to stay out of version control; the skill"
  echo "writes a workspace .gitignore when you begin a filing."
else
  echo "Done. Restart your CLI, then say: \"file my ITR\" (Claude: /itr-wala, Codex: \$itr-wala)"
fi
exit "$FAILED"
