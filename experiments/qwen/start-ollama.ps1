param(
    [Parameter(Mandatory=$true)][string]$OllamaExe,
    [switch]$Approved
)
$ErrorActionPreference = 'Stop'
if (-not $Approved) { throw 'Run only after explicit installation/model/run approval; pass -Approved.' }
$exePath = (Resolve-Path -LiteralPath $OllamaExe).Path
$repoPath = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '../..')).Path
$modelPath = Join-Path $repoPath '.local/qwen-models'
New-Item -ItemType Directory -Force -Path $modelPath | Out-Null
# These variables affect this shell/process only; no registry or machine settings.
$env:OLLAMA_HOST = '127.0.0.1:11435'
$env:OLLAMA_MODELS = $modelPath
$env:OLLAMA_NO_CLOUD = '1'
$env:OLLAMA_MAX_LOADED_MODELS = '1'
$env:OLLAMA_NUM_PARALLEL = '1'
$env:OLLAMA_MAX_QUEUE = '1'
$env:OLLAMA_CONTEXT_LENGTH = '8192'
$env:OLLAMA_KEEP_ALIVE = '0'
$env:OLLAMA_DEBUG = '0'
# Foreground dedicated server; Ctrl+C stops only this experiment. No auto-pull.
& $exePath serve
exit $LASTEXITCODE
