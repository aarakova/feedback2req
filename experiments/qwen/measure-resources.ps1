param(
    [Parameter(Mandatory=$true)][int]$ServerProcessId,
    [Parameter(Mandatory=$true)][string]$Output,
    [ValidateRange(1,900)][int]$Seconds = 180
)
$ErrorActionPreference = 'Stop'
$repoPath = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '../..')).Path
$allowedPath = [IO.Path]::GetFullPath((Join-Path $repoPath '.local/qwen-runs')) + [IO.Path]::DirectorySeparatorChar
$outputPath = [IO.Path]::GetFullPath($Output)
if (-not $outputPath.StartsWith($allowedPath, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Resource output must be under this worktree .local/qwen-runs.'
}
$rootProcess = Get-Process -Id $ServerProcessId
if ($rootProcess.ProcessName -notlike '*ollama*') { throw 'Select the dedicated Ollama server process.' }
$startTime = $rootProcess.StartTime
$stream = [IO.File]::Open($outputPath, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write)
$writer = [IO.StreamWriter]::new($stream, [Text.UTF8Encoding]::new($false))
$deadline = [DateTime]::UtcNow.AddSeconds($Seconds)
try {
    while ([DateTime]::UtcNow -lt $deadline) {
        $currentRoot = Get-Process -Id $ServerProcessId -ErrorAction SilentlyContinue
        if (-not $currentRoot -or $currentRoot.StartTime -ne $startTime) { break }
        $processTable = @(Get-CimInstance Win32_Process | Select-Object ProcessId,ParentProcessId)
        $ids = @($ServerProcessId)
        do {
            $previousCount = $ids.Count
            $ids = @($ids + @($processTable | Where-Object { $_.ParentProcessId -in $ids } | ForEach-Object { [int]$_.ProcessId }) | Sort-Object -Unique)
        } while ($ids.Count -gt $previousCount)
        $processes = @(Get-Process -Id $ids -ErrorAction SilentlyContinue)
        $sample = @{
            measured_at = [DateTime]::UtcNow.ToString('o')
            process_ids = $ids
            working_set_sum_bytes = ($processes | Measure-Object WorkingSet64 -Sum).Sum
            private_bytes_sum = ($processes | Measure-Object PrivateMemorySize64 -Sum).Sum
            cpu_seconds_sum_observed_processes = ($processes | Measure-Object CPU -Sum).Sum
            gpu_vram_bytes = $null
            limitations = 'Sampled process tree, not exact peak; shared pages may be counted twice; exited processes may be missed; CPU sum may drop on runner restart; VRAM unmeasured.'
        }
        $writer.WriteLine(($sample | ConvertTo-Json -Compress))
        $writer.Flush()
        Start-Sleep -Milliseconds 1000
    }
} finally {
    $writer.Dispose()
    $stream.Dispose()
}
