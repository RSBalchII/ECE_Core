<#
.SYNOPSIS
    Launches the WebGPU Bridge with an ephemeral Firewall rule.
.DESCRIPTION
    1. Picks a random port (or uses -Port).
    2. Adds a Windows Firewall 'Allow' rule for that port.
    3. Starts webgpu_bridge.py.
    4. Removes the Firewall rule immediately upon exit.
#>

param (
    [int]$Port = 0
)

# 1. Pick Port
if ($Port -eq 0) {
    $Port = Get-Random -Minimum 9000 -Maximum 9999
}

$RuleName = "SovereignCoda-Bridge-$Port"

try {
    Write-Host "🔒 [Sovereign Coda] Configuring Secure Network..." -ForegroundColor Cyan

    # 2. Add Firewall Rule (Requires Admin usually, logic checks availability)
    # Check if running as Admin
    $isElevated = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")
    
    if (-not $isElevated) {
        Write-Warning "⚠️  Not running as Administrator. Firewall rules might fail."
        Write-Warning "    Please right-click this script and 'Run as Administrator' if basic access fails."
        Write-Host "    Attempting to proceed (Localhost will work, LAN might not)..." -ForegroundColor DarkGray
    } else {
        Write-Host "    + Opening TCP Port $Port..." -ForegroundColor Green
        New-NetFirewallRule -DisplayName $RuleName -Direction Inbound -LocalPort $Port -Protocol TCP -Action Allow -Profile Private,Domain | Out-Null
    }

    # 3. Launch Bridge
    $env:BRIDGE_PORT = $Port
    $env:BRIDGE_HOST = "0.0.0.0"
    
    Write-Host "🚀 Launching Bridge on Port $Port..." -ForegroundColor Cyan
    python tools/webgpu_bridge.py

} catch {
    Write-Error "An error occurred: $_"
} finally {
    # 4. Cleanup
    if ($isElevated) {
        Write-Host "`n🔒 [Sovereign Coda] Cleaning up Firewall Rules..." -ForegroundColor Cyan
        try {
            Remove-NetFirewallRule -DisplayName $RuleName -ErrorAction SilentlyContinue
            Write-Host "    + Rule '$RuleName' Removed." -ForegroundColor Green
        } catch {
            Write-Warning "Failed to remove firewall rule. Please remove '$RuleName' manually."
        }
    }
}
