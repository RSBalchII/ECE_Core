<#
convert_anchor_to_submodule.ps1

Replace the anchor/ folder in the monorepo with a submodule pointing to the provided remote.
This assumes the target repo exists and that the working directory is a clean checkout.

Usage:
  pwsh ./convert_anchor_to_submodule.ps1 -RemoteUrl "https://github.com/External-Context-Engine/Anchor-.git" [-Branch main] [-DryRun]

This will:
  - Remove the anchor folder from index
  - Add the submodule at the anchor/ path
  - Commit the change referencing the submodule

IMPORTANT: This will create commits changing the repo index. Back up or ensure containing changes are reviewed.
#>

param(
    [Parameter(Mandatory=$true)]
    [string]$RemoteUrl,
    [string]$Branch = "main",
    [switch]$DryRun
)

function RunCmd($cmd){
    Write-Host "PS> $cmd"
    if (-not $DryRun) { iex $cmd }
}

Write-Host "== Convert anchor/ to submodule -> $RemoteUrl (branch: $Branch) =="

if (-not (Test-Path -Path "./anchor" -PathType Container)) {
    Write-Error "Anchor directory not found in the current path. Run from repo root."
    exit 1
}

# Ensure a clean working tree prior to removal
$status = git status --porcelain
if ($status.Trim().Length -ne 0) {
    Write-Error "Working tree not clean. Please stash/commit before running this script." -ForegroundColor Red
    exit 1
}

Write-Host "Removing anchor/ from index (preserve files locally)"
RunCmd "git rm -r --cached anchor"
RunCmd "git commit -m 'Remove anchor directory (prepare to add as submodule)'"

Write-Host "Adding submodule at anchor -> $RemoteUrl"
RunCmd "git submodule add $RemoteUrl anchor"
RunCmd "git submodule update --init --recursive"

RunCmd "git add .gitmodules anchor"
RunCmd "git commit -m 'Add anchor as submodule pointing to $RemoteUrl'"

Write-Host "Converted anchor directory into a submodule. Please push changes to parent repo and ensure anchor remote is reachable." -ForegroundColor Green
