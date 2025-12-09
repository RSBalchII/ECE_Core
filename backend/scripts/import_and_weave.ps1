param(
    [string]$File = "combined_text.txt",
    [string]$Api = "http://127.0.0.1:8000",
    [int]$MaxTokens = 3000,
    [int]$BatchSize = 10,
    [switch]$DryRun,
    [switch]$WeaveDryRun
)

if (-Not (Test-Path $File)) {
    Write-Error "File not found: $File"
    exit 1
}

Write-Host "Importing $File to ECE_Core ($Api)"
$dryArg = if ($DryRun) { '--dry-run' } else { '' }

Write-Host "Running import_and_verify.py (this will POST memory chunks)"
python .\scripts\import_and_verify.py --file $File --api $Api --max-tokens $MaxTokens --batch-size $BatchSize $dryArg

Write-Host "Running MemoryWeaver (dry-run recommended)"
$weaveDryArg = if ($WeaveDryRun) { '--dry-run' } else { '' }
python .\scripts\weave_recent.py --hours 24 --threshold 0.75 --csv-out weaver_result.csv $weaveDryArg

Write-Host "Done. Review weaver_result.csv for proposed commits. Remove --dry-run to commit."
