<#
.SYNOPSIS
  Archive root-level start scripts that are wrappers for canonical dev scripts.
>
Param(
  [switch]$Force
)
Set-StrictMode -Version Latest
$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Definition
$RepoRoot = Resolve-Path "$ScriptRoot\..\.."
$ArchiveDir = Join-Path $RepoRoot 'archive\startup-scripts'
if (-not (Test-Path $ArchiveDir)) { New-Item -ItemType Directory -Path $ArchiveDir | Out-Null }
Write-Host "Scanning $RepoRoot for root-level wrappers that call scripts/dev/start-*" -ForegroundColor Cyan
$files = Get-ChildItem -Path $RepoRoot -Filter 'start-*.*' -File -ErrorAction SilentlyContinue
$candidates = @()
foreach ($f in $files) {
  $content = Get-Content -LiteralPath $f.FullName -ErrorAction SilentlyContinue
  if ($content -match 'scripts/dev/start-') {
    Write-Host " - Candidate: $($f.Name)" -ForegroundColor Green
    $candidates += $f
  } else {
    Write-Host " - Skip (not a wrapper): $($f.Name)" -ForegroundColor Yellow
  }
}
if ($candidates.Count -eq 0) {
  Write-Host "No root-level wrappers to archive." -ForegroundColor Yellow; exit 0
}
if (-not $Force) {
  $confirm = Read-Host "Archive $($candidates.Count) files to $ArchiveDir? (y/N)"
  if ($confirm -notin @('y','Y')) { Write-Host 'Canceling.'; exit 0 }
}
foreach ($f in $candidates) {
  $dest = Join-Path $ArchiveDir $f.Name
  Write-Host "Archiving $($f.Name) -> $dest" -ForegroundColor Magenta
  Move-Item -Force -LiteralPath $f.FullName -Destination $dest
}
Write-Host "Done. Archived $($candidates.Count) files to $ArchiveDir" -ForegroundColor Cyan
