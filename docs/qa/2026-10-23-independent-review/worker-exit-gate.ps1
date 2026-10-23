param([ValidateSet(0, 17)][int]$InjectedExitCode = 0)
# Private, opt-in demonstration of the proposed CI gate. No shared Compose changes.
# Expected: -InjectedExitCode 0 => exit 0; -InjectedExitCode 17 => exit 1.
$ErrorActionPreference = 'Stop'
$taskProject = 'f2r-qa-worker-' + [guid]::NewGuid().ToString('N')
$workerImage = 'sha256:502a889308438970214d3f5cbc70e81311b9ef8ccc0c4e936504b065250e192f'
$containerId = $null
$gateExit = 1
$compose = @"
services:
  worker:
    image: $workerImage
    pull_policy: never
    read_only: true
    network_mode: none
    command: ["python", "-B", "-c", "raise SystemExit($InjectedExitCode)"]
"@
try {
    $compose | docker compose -p $taskProject -f - up -d
    if ($LASTEXITCODE -ne 0) { throw 'The isolated Compose launch failed.' }
    Write-Output 'Detached Compose startup returned 0; now checking the process result.'
    $containerId = docker ps -aq --filter "label=com.docker.compose.project=$taskProject" --filter 'label=com.docker.compose.service=worker'
    if (@($containerId).Count -ne 1 -or -not $containerId) { throw 'Expected exactly one owned worker.' }
    $deadline = [DateTime]::UtcNow.AddSeconds(15)
    do {
        $entry = @(docker inspect $containerId | ConvertFrom-Json)[0]
        if ($LASTEXITCODE -ne 0) { throw 'Could not inspect the owned worker.' }
        if ($entry.State.Status -eq 'exited') { break }
        Start-Sleep -Milliseconds 100
    } while ([DateTime]::UtcNow -lt $deadline)
    if ($entry.State.Status -ne 'exited') { throw 'The finite worker did not finish within the test bound.' }
    Write-Output "Worker process exit code: $($entry.State.ExitCode)"
    if ($entry.State.ExitCode -eq 0) {
        Write-Output 'PASS: worker diagnostics completed successfully.'
        $gateExit = 0
    } else {
        Write-Output 'FAIL: deployment gate rejects unsuccessful worker diagnostics.'
    }
} finally {
    if ($containerId) {
        $entry = @(docker inspect $containerId | ConvertFrom-Json)[0]
        if ($entry.Config.Labels.'com.docker.compose.project' -eq $taskProject) {
            docker rm --force $containerId | Out-Null
        }
    }
}
exit $gateExit
