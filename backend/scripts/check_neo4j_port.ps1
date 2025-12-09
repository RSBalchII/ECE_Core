# Script: check_neo4j_port.ps1
# Purpose: Diagnose whether port 7687 is bound and which process owns it.




























Write-Host "To stop a process with PID $pid (if safe): Stop-Process -Id $pid -Force"
nWrite-Host "If you find an unexpected process (not Neo4j), consider stopping it or changing port bindings in its configuration."}    Write-Host "Could not determine PID for port listener."} else {    }        Write-Host "Failed to locate process with PID $pid. Perhaps it recently exited."    } else {        try { $wmi = Get-CimInstance Win32_Process -Filter "ProcessId = $pid"; $wmi.CommandLine } catch { }        Write-Host "Command Line: "        Write-Host "Process name: $($proc.ProcessName)"    if ($proc) {    $proc = Get-Process -Id $pid -ErrorAction SilentlyContinue    Write-Host "PID owning port $port: $pid"if ($pid) {$pid = $connections.OwningProcess[0]
n$connections | Format-Table -AutoSize}    exit 0    Write-Host "No listener found on port $port. That's a good sign."if (-not $connections) {$connections = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
nWrite-Host "Checking who is listening on port $port...")    [int]$port = 7687
nparam(n# Requires: PowerShell (Windows)