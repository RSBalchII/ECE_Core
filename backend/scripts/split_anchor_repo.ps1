<#
split_anchor_repo.ps1

Create a separate Git repository for the anchor/ folder by
creating a subtree split, pushing it up to a remote, and leaving a
branch that can be tested. Does not delete anything by default.

Usage:
  pwsh ./split_anchor_repo.ps1 -RemoteUrl "https://github.com/External-Context-Engine/Anchor-.git" [-Branch main] [-Push]

Flags:
  -RemoteUrl   The Git remote to push the Anchor repo to.
  -Branch      The branch to push to (default: main).
  -Push        Actually push the split branch to the remote (safe default: no push).
  -ReplaceWithSubmodule Replace current anchor/ with submodule after push (optional)
  -DryRun      Only show the commands that would run.
#>

param(
    [Parameter(Mandatory=$true)]
    [string]$RemoteUrl,
    [string]$Branch = "main",
    [switch]$Push,
    [switch]$ReplaceWithSubmodule,
    [switch]$DryRun
)

function RunCmd($cmd){
    Write-Host "PS> $cmd"
    if (-not $DryRun) { iex $cmd }
}

Write-Host "== Split Anchor Subtree -> $RemoteUrl (branch: $Branch) =="

# Ensure we are at the repo root (expected to find anchor/)
if (-not (Test-Path -Path "./anchor" -PathType Container)) {
    Write-Error "Anchor directory not found in the current path. Run from the monorepo root."
    exit 1
}

# Make sure the working tree is clean
$status = git status --porcelain
if ($status.Trim().Length -ne 0) {
    Write-Host "Working tree is not clean. Please commit/stash changes before running this script." -ForegroundColor Yellow
    exit 1
}

# Create a unique split branch name
$time = Get-Date -Format "yyyyMMddHHmmss"
$splitBranch = "anchor-only-$time"

Write-Host "Creating split branch: $splitBranch" -ForegroundColor Cyan
RunCmd "git subtree split -P anchor -b $splitBranch"

Write-Host "Verifying branch exists: $splitBranch"
if (-not (git show-ref --verify --quiet refs/heads/$splitBranch)) {
    Write-Error "Failed to create branch $splitBranch"
    exit 1
}

Write-Host "Adding anchor remote: anchor-remote -> $RemoteUrl"
RunCmd "git remote remove anchor-remote 2>$null || true"
RunCmd "git remote add anchor-remote $RemoteUrl"

if ($Push) {
    Write-Host "Pushing branch to anchor-remote as $Branch to create the new repo" -ForegroundColor Cyan
    RunCmd "git push anchor-remote $splitBranch:$Branch"
} else {
    Write-Host "Dry-run or -Push not set: not pushing to remote. To push, re-run with -Push flag." -ForegroundColor Yellow
}

if ($ReplaceWithSubmodule -and $Push) {
    Write-Host "Replacing anchor/ directory with submodule referencing $RemoteUrl" -ForegroundColor Cyan
    RunCmd "git rm -r --cached anchor"
    RunCmd "git commit -m 'Remove anchor directory for submodule replacement'"
    RunCmd "git submodule add $RemoteUrl anchor"
    RunCmd "git add .gitmodules anchor"
    RunCmd "git commit -m 'Add anchor as a submodule'"
    Write-Host "Submodule added. Please push to origin manually (git push origin <branch>)" -ForegroundColor Green
}

Write-Host "Done. Local split branch: $splitBranch. If pushed, the new remote should have the anchor code." -ForegroundColor Green
