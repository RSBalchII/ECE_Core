# archive_v3_cleanup.ps1

$ArchiveDir = "archive\v2_ghost_shell"
New-Item -ItemType Directory -Force -Path $ArchiveDir | Out-Null

# List of obsolete files to move
$Obsolete = @(
    "start-bridge.bat",                   # Replaced by start-anchor.bat
    "start-ghost-shell.bat",              # Replaced by start-anchor.bat
    "start-sovereign-console.bat",        # Legacy
    "start-sovereign-console-hotreload.bat", # Legacy
    "secure-bridge-launch.ps1"            # Legacy
)

foreach ($file in $Obsolete) {
    if (Test-Path $file) {
        Write-Host "📦 Archiving $file..." -ForegroundColor Gray
        Move-Item $file $ArchiveDir -Force
    }
}

# Handle files in scripts directory separately
$ScriptFiles = @(
    "scripts\launch-ghost.ps1",           # Logic moved to start-anchor.bat
    "scripts\hot_reload_gpu.py"           # Functionality merged or deprecated for now
)

foreach ($file in $ScriptFiles) {
    if (Test-Path $file) {
        Write-Host "📦 Archiving $file..." -ForegroundColor Gray
        $destDir = Join-Path $ArchiveDir "scripts"
        New-Item -ItemType Directory -Force -Path $destDir | Out-Null
        Move-Item $file $destDir -Force
    }
}

Write-Host "✅ Cleanup Complete. System is now pure Anchor." -ForegroundColor Green