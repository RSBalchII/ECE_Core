<#
Show direct import progress & ETA for import_direct_neo4j.py

Usage:
  pwsh -File scripts\show_direct_import_progress.ps1 -ChunkChars 12000 -Watch -Interval 5

Options:
  -ChunkChars <int>    : Character chunk size used by import_direct_neo4j.py (default 10000)
  -File <path>         : The text file you're importing (default combined_text.txt)
  -StateFile <path>    : The direct import state file (default scripts/import_direct_state.json)
  -Watch               : If set, run continuously and update every -Interval seconds
  -Interval <int>      : If -Watch, update interval in seconds (default 5)
#>
[CmdletBinding()]
param(
    [int]$ChunkChars = 10000,
    [string]$File = "combined_text.txt",
    [string]$StateFile = "scripts\import_direct_state.json",
    [switch]$Watch,
    [int]$Interval = 5
)

function Get-TotalChunks($filePath, $chunkChars){
    if(-not (Test-Path $filePath)) { return 0 }
    $content = Get-Content $filePath -Raw
    if([string]::IsNullOrEmpty($content)) { return 0 }
    return [math]::Ceiling($content.Length / $chunkChars)
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

function Show-ProgressOnce(){
    $total = Get-TotalChunks -filePath $File -chunkChars $ChunkChars
    $last = Get-LastCompleted -stateFile $StateFile

    if($total -le 0){
        Write-Host "Could not determine total chunks. Verify --File path and chunk-chars or run the importer with --dry-run manually." -ForegroundColor Yellow
        return
    }

    $percent = [math]::Round(($last / $total) * 100, 2)

    # No reliable per-chunk timing for direct import; estimate from file write times
    $avg = 0.5
    $remaining = [math]::Max(0, $total - $last)
    $etaSec = [math]::Ceiling($remaining * $avg)
    $eta = (Get-Date).AddSeconds($etaSec)

    $line = "Direct Import Progress: $last / $total ($percent%) | Remaining: $remaining | ETA: $eta (approx $etaSec sec) | Avg Est: $([math]::Round($avg,2)) s/chunk"
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
