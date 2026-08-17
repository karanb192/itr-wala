# itr-wala installer - copies the skill into your agent's skills directory.
#
# PREFERRED: clone the repo, read it, then run it from the checkout. The
# script installs the bytes you just reviewed and never touches the network:
#
#   .\install.ps1            # Claude Code
#   .\install.ps1 codex      # OpenAI Codex CLI
#   .\install.ps1 gemini     # Gemini CLI
#   .\install.ps1 all        # all of the above
#
# Scope: global (into $HOME) by default. Or install PROJECT-LOCAL, beside the
# documents the skill works on, so it exists only in that one project:
#
#   cd C:\Users\you\tax-2026; \path\to\itr-wala\install.ps1 -Here
#   .\install.ps1 -Project C:\Users\you\tax-2026 all
#
# Run outside a checkout, it clones $REPO - which every copy points at ITSELF,
# so an unattended run can never silently pull code nobody reviewed. Override:
#
#   $env:ITR_WALA_REF="<sha|tag|branch>"; .\install.ps1   # pin an exact reviewed commit
#   $env:ITR_WALA_NO_FETCH="1"; .\install.ps1             # refuse to fetch at all
#   $env:ITR_WALA_REPO="<url>"; .\install.ps1             # pull from a different repo

# --- Repo identity: the one line that differs between any two copies -------
# Everything else here is generic - it works unchanged in a fork AND in the
# original, because "the repo this script lives in" is the only thing that
# distinguishes them. DEFAULT_REPO must name THAT repo: an installer that
# defaults to a repo its operator does not control re-introduces exactly the
# trust-on-every-install problem the review-first workflow exists to remove.
# To pull from anywhere else, name it explicitly - e.g. the original project:
#   $env:ITR_WALA_REPO="https://github.com/karanb192/itr-wala.git"; .\install.ps1
$DEFAULT_REPO = "https://github.com/karanb192/itr-wala.git"   # point this at YOUR repo
# ---------------------------------------------------------------------------

$Repo = if ($env:ITR_WALA_REPO) { $env:ITR_WALA_REPO } else { $DEFAULT_REPO }
$Ref = if ($env:ITR_WALA_REF) { $env:ITR_WALA_REF } else { "" }
$Skill = "itr-wala"

function Show-Usage {
    Write-Host "Usage: install.ps1 [--here | -Here | --project DIR | -Project DIR] [claude|codex|gemini|all]"
    Write-Host "  --here, -Here         install into the current directory (project-local)"
    Write-Host "  --project, -Project   install into DIR (project-local)"
    Write-Host "  default               install into `$HOME (global, all projects)"
}

$Scope = "global"
$Base = if ($env:USERPROFILE) { $env:USERPROFILE } else { $HOME }
$Target = ""
$TempCreated = $false
$Src = ""

$i = 0
while ($i -lt $args.Count) {
    $arg = $args[$i]
    switch -Regex ($arg) {
        '^(--here|-Here|-here)$' {
            $Scope = "project"
            $Base = (Get-Location).Path
        }
        '^(--project|-Project|-project)$' {
            $Scope = "project"
            if ($i + 1 -ge $args.Count) {
                Write-Error "ERROR: --project needs a directory (e.g. -Project C:\tax-2026)"
                exit 1
            }
            $i++
            $projDir = $args[$i]
            if (-not (Test-Path -Path $projDir -PathType Container)) {
                Write-Error "ERROR: --project '$projDir' is not a directory."
                exit 1
            }
            $Base = (Resolve-Path -Path $projDir).Path
        }
        '^(-h|--help|-Help)$' {
            Show-Usage
            exit 0
        }
        '^(claude|codex|gemini|all)$' {
            $Target = $arg
        }
        default {
            Write-Error "ERROR: unknown argument '$arg'"
            Show-Usage
            exit 1
        }
    }
    $i++
}

if (-not $Target) {
    $Target = "claude"
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
if (-not $scriptDir) {
    $scriptDir = (Get-Location).Path
}

$localSkillPath = Join-Path $scriptDir "skills\$Skill\SKILL.md"
if (Test-Path $localSkillPath) {
    $Src = $scriptDir
    Write-Host "Installing from local checkout: $Src"
} elseif ($env:ITR_WALA_NO_FETCH -eq "1") {
    Write-Error "ERROR: ITR_WALA_NO_FETCH=1 and no checkout found beside this script."
    Write-Error "       Clone the repo and run .\install.ps1 from inside it."
    exit 1
} else {
    $tempGuid = [guid]::NewGuid().ToString("N")
    $Src = Join-Path ([System.IO.Path]::GetTempPath()) "itr-wala-$tempGuid"
    New-Item -ItemType Directory -Path $Src -Force | Out-Null
    $TempCreated = $true

    $fetchRef = if ($Ref) { $Ref } else { "HEAD" }
    Write-Host "Fetching $Repo $(if ($Ref) { "@ $Ref" }) ..."

    $env:GIT_TERMINAL_PROMPT = "0"
    try {
        git init --quiet $Src
        if ($LASTEXITCODE -ne 0) { throw "git init failed" }
        git -C $Src remote add origin $Repo
        if ($LASTEXITCODE -ne 0) { throw "git remote add failed" }
        git -C $Src fetch --depth 1 --quiet origin $fetchRef
        if ($LASTEXITCODE -ne 0) { throw "git fetch failed" }
        git -C $Src checkout --quiet FETCH_HEAD
        if ($LASTEXITCODE -ne 0) { throw "git checkout failed" }

        $fetchedCommit = (git -C $Src rev-parse HEAD).Trim()
        Write-Host "  fetched commit $fetchedCommit"
    } catch {
        Write-Error "ERROR: could not fetch $fetchRef from $Repo - check your network, the URL, and that the ref exists."
        if ($TempCreated -and (Test-Path $Src)) {
            Remove-Item -Path $Src -Recurse -Force -ErrorAction SilentlyContinue
        }
        exit 1
    }
}

$Installed = @()

function Install-Into {
    param([string]$DestDir)

    if (Test-Path $DestDir -PathType Leaf) {
        Remove-Item -Path $DestDir -Force
    }
    if (-not (Test-Path $DestDir)) {
        New-Item -ItemType Directory -Path $DestDir -Force | Out-Null
    }

    $targetPath = Join-Path $DestDir $Skill
    if (Test-Path $targetPath) {
        Write-Host "  replacing existing install at $targetPath"
        Remove-Item -Path $targetPath -Recurse -Force
    }

    $srcSkillPath = Join-Path $Src "skills\$Skill"
    Copy-Item -Path $srcSkillPath -Destination $targetPath -Recurse -Force

    Get-ChildItem -Path $targetPath -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
    Get-ChildItem -Path $targetPath -Recurse -File -Filter "*.pyc" -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue

    $script:Installed += $targetPath
    Write-Host "  installed -> $targetPath"
}

function Install-CodexHome {
    if ($Scope -eq "global") {
        $codexHome = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $Base ".codex" }
        Install-Into (Join-Path $codexHome "skills")
    }
}

if ($Scope -eq "project") {
    Write-Host "Scope: project-local -> $Base"
    if ($Base -eq $Src) {
        Write-Warning "  NOTE: that is this repo - you are installing the skill into its own"
        Write-Warning "        source tree. You probably want the directory your tax documents"
        Write-Warning "        live in: .\install.ps1 -Project C:\your-tax-folder"
    }
} else {
    Write-Host "Scope: global -> $Base"
}

switch ($Target) {
    "claude" {
        Install-Into (Join-Path $Base ".claude\skills")
    }
    "codex" {
        Install-Into (Join-Path $Base ".agents\skills")
        Install-CodexHome
    }
    "gemini" {
        Install-Into (Join-Path $Base ".gemini\skills")
    }
    "all" {
        Install-Into (Join-Path $Base ".claude\skills")
        Install-Into (Join-Path $Base ".agents\skills")
        Install-CodexHome
        Install-Into (Join-Path $Base ".gemini\skills")
    }
}

if ($TempCreated -and (Test-Path $Src)) {
    Remove-Item -Path $Src -Recurse -Force -ErrorAction SilentlyContinue
}

function Get-PythonCommand {
    foreach ($cmd in @("python3", "python", "py")) {
        try {
            $testProc = Start-Process -FilePath $cmd -ArgumentList '-c "import sys; sys.exit(0 if sys.version_info >= (3,9) else 1)"' -NoNewWindow -Wait -PassThru -ErrorAction SilentlyContinue
            if ($testProc -and $testProc.ExitCode -eq 0) {
                return $cmd
            }
        } catch {}
    }
    return "python"
}

$PythonCmd = Get-PythonCommand

Write-Host ""
Write-Host "Verifying the tax engine (golden test suite) in each installed copy..."
$Failed = 0

foreach ($dest in $Installed) {
    $testScript = Join-Path $dest "scripts\test_tax_engine.py"
    $env:PYTHONDONTWRITEBYTECODE = "1"

    if ($PythonCmd -eq "py") {
        & py -3 $testScript *>$null
    } else {
        & $PythonCmd $testScript *>$null
    }

    if ($LASTEXITCODE -eq 0) {
        Write-Host "  OK   $dest"
    } else {
        Write-Host "  FAIL $dest - run: $PythonCmd $testScript" -ForegroundColor Red
        $Failed = 1
    }
}

if ($Failed -ne 0) {
    Write-Warning "WARNING: verification failed (is Python 3.9+ on PATH?). Do not trust the skill until the self-test passes."
}

Write-Host ""
if ($Scope -eq "project") {
    Write-Host "Done. The skill is local to $Base - start your CLI from"
    Write-Host "that directory (or below it) and only that project sees it."
    Write-Host "Your tax documents still need to stay out of version control; the skill"
    Write-Host "writes a workspace .gitignore when you begin a filing."
} else {
    Write-Host "Done. Restart your CLI, then say: `"file my ITR`" (Claude: /itr-wala, Codex: `$itr-wala)"
}

exit $Failed
