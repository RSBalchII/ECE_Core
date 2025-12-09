<#
Show import progress & ETA for import_via_chat.py

Usage:
  pwsh -File scripts\show_import_progress.ps1 -ChunkSize 300 -Watch -Interval 5

Options:
  -ChunkSize <int>    : Token chunk size used by import script (default 300)
  -StateFile <path>   : The resume JSON state file (default scripts/import_via_chat_state.json)
  -LogFile <path>     : The import log file to check (default import_full_run.log)
  -AvgSecPerChunk <float> : Optional override average seconds per chunk
  -Watch              : If set, run continuously and update every -Interval seconds
  -Interval <int>     : If -Watch, update interval in seconds (default 5)
#>
[CmdletBinding()]
param(
    [int]$ChunkSize = 300,
    [string]$File = "combined_text.txt",
    [string]$StateFile = "scripts\import_via_chat_state.json",
    [string]$LogFile = "import_full_run.log",
    [double]$AvgSecPerChunk = 0.0,
    [switch]$Watch,
    [int]$Interval = 5
)

function Get-TotalChunks($filePath, $chunkSize){
    # Run a dry-run chunker to count chunks
    $pv = "python scripts/import_via_chat.py --file $filePath --dry-run --chunk-size $chunkSize"
    try{
        $out = & $pv 2>&1
        foreach($line in $out){
            if($line -match "Found\s+(\d+)\s+chunks"){
                return [int]$matches[1]
            }
        }
    } catch {
        # fallback: compute naive by file length / chunk bytes
        if(Test-Path $filePath){
            $content = Get-Content $filePath -Raw
            $approx = [math]::Ceiling($content.Length / ($chunkSize * 4))
            return $approx
        }
    }
    return 0
}

function Get-LastCompleted($stateFile){
    if(Test-Path $stateFile){
        $json = Get-Content $stateFile -Raw | ConvertFrom-Json
        if($null -ne $json.last_completed_chunk){
            return [int]$json.last_completed_chunk
        }
    }
    return 0
}

function Get-PostedCountFromLog($logFile){
    if(-not (Test-Path $logFile)) { return 0 }
    $lines = Get-Content $logFile
    # Find last "Posted X chunks" line
    for($i = $lines.Length - 1; $i -ge 0; $i--){
        $l = $lines[$i]
        if($l -match "Posted\s+(\d+)\s+chunks"){
            return [int]$matches[1]
        }
    }
    return 0
}

function Get-AvgSecFromLog($logFile, $postedCount){
    if(-not (Test-Path $logFile)) { return 0 }
    try{
        $fi = Get-Item $logFile
        $createTime = $fi.CreationTimeUtc
        $lastWrite = $fi.LastWriteTimeUtc
        if($postedCount -gt 0){
            $elapsed = (Get-Date).ToUniversalTime() - $createTime
            $secs = $elapsed.TotalSeconds
            if($secs -gt 1){
                return $secs / $postedCount
            }
        }
    }catch{
        return 0
    }
    return 0
}

function Show-ProgressOnce(){
    $total = Get-TotalChunks -filePath $File -chunkSize $ChunkSize
    $last = Get-LastCompleted -stateFile $StateFile
    # If the statefile is not present, maybe we can query the log "Posted X chunks"
    if($last -eq 0){
        $postedCount = Get-PostedCountFromLog -logFile $LogFile
        if($postedCount -gt 0){ $last = $postedCount }
    }

    if($total -le 0){
        Write-Host "Could not determine total chunks. Verify --file path and chunk-size or run the dry-run manually." -ForegroundColor Yellow
        return
    }

    $percent = [math]::Round(($last / $total) * 100, 2)

    $avg = 0.0
    if($AvgSecPerChunk -gt 0){
        $avg = $AvgSecPerChunk
    } else {
        $postedCount = Get-PostedCountFromLog -logFile $LogFile
        if($postedCount -gt 0){
            $avg = Get-AvgSecFromLog -logFile $LogFile -postedCount $postedCount
        }
        if($avg -le 0){ $avg = 1.0 } # default
    }

    $remaining = [math]::Max(0, $total - $last)
    $etaSec = [math]::Ceiling($remaining * $avg)
    $eta = (Get-Date).AddSeconds($etaSec)

    # Show single line progress
    $line = "Progress: $last / $total ($percent%) | Remaining: $remaining | ETA: $eta (approx $etaSec sec) | Avg: $([math]::Round($avg,2)) s/chunk"
    Write-Host $line
}

if($Watch){
    while($true){
        Clear-Host
        Show-ProgressOnce
        Start-Sleep -Seconds $Interval
    }
} else {
    Show-ProgressOnce
}

# EOF
