<#
.SYNOPSIS
    Launches the "Ghost Engine" (Headless Browser) for WebGPU Inference.
.DESCRIPTION
    Starts Edge/Chrome in headless mode with specific flags to force WebGPU execution.
    This acts as the background inference server for the Sovereign system.
#>

$TargetUrl = "http://localhost:8000/tools/model-server-chat.html?headless=true"
$UserDataDir = Join-Path $PSScriptRoot "..\browser_data\ghost_profile"

# Ensure User Data Directory exists
if (-not (Test-Path $UserDataDir)) {
    New-Item -ItemType Directory -Force -Path $UserDataDir | Out-Null
}

# 1. Define the "God Mode" Flags for Headless WebGPU
# --headless=new: The new implementation that supports full GPU acceleration
# --use-gl=angle: Forces the correct backend for D3D12/Vulkan on Windows
# --disable-web-security: Needed for local API fetches (Stealth Mode)
$GhostFlags = @(
    "--headless=new",
    "--hide-scrollbars",
    "--mute-audio",
    "--remote-debugging-port=9222", 
    "--user-data-dir=$UserDataDir",
    "--enable-unsafe-webgpu",
    "--enable-features=Vulkan,UseSkiaRenderer",
    "--disable-web-security",
    "--disable-site-isolation-trials",
    "--disable-gpu-watchdog",
    "--ignore-gpu-blocklist"
)

# 2. Find the Browser Executable (Prioritize Edge on Windows)
$EdgePath = "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
$ChromePath = "C:\Program Files\Google\Chrome\Application\chrome.exe"

if (Test-Path $EdgePath) {
    Write-Host "👻 Summoning Ghost Engine via Microsoft Edge..." -ForegroundColor Cyan
    Start-Process -FilePath $EdgePath -ArgumentList ($GhostFlags + $TargetUrl) -WindowStyle Hidden
}
elseif (Test-Path $ChromePath) {
    Write-Host "👻 Summoning Ghost Engine via Google Chrome..." -ForegroundColor Cyan
    Start-Process -FilePath $ChromePath -ArgumentList ($GhostFlags + $TargetUrl) -WindowStyle Hidden
}
else {
    Write-Error "❌ No supported browser found (Edge/Chrome). Install Edge Canary or Chrome."
}

Write-Host "✅ Ghost is listening. Use 'sov.py' to interact." -ForegroundColor Green