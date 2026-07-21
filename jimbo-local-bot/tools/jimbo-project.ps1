$ErrorActionPreference = 'Stop'

$pythonPath = 'C:\Users\dlbat\AppData\Local\Programs\Python\Python313\python.exe'
$projectPath = Split-Path -Parent $PSScriptRoot
$botPath = Join-Path $projectPath 'jimbo_bot.py'
$testsPath = Join-Path $projectPath 'tests'
$actionPath = Join-Path $PSScriptRoot 'jimbo-action.json'
$runtimePath = Join-Path $projectPath 'runtime'
$pidPath = Join-Path $runtimePath 'jimbo.pid'
$stdoutPath = Join-Path $runtimePath 'listener.stdout.log'
$stderrPath = Join-Path $runtimePath 'listener.stderr.log'

if (-not (Test-Path -LiteralPath $pythonPath -PathType Leaf)) {
    throw "Python executable not found: $pythonPath"
}
if (-not (Test-Path -LiteralPath $actionPath -PathType Leaf)) {
    throw "Jimbo action file not found: $actionPath"
}

$request = Get-Content -LiteralPath $actionPath -Raw | ConvertFrom-Json
$action = [string] $request.action
if ($action -notin @('test', 'bot', 'start', 'stop', 'restart', 'status')) {
    throw "Unsupported Jimbo project action '$action'"
}
$botArguments = @($request.arguments | ForEach-Object { [string] $_ })

function Get-JimboProcess {
    if (-not (Test-Path -LiteralPath $pidPath -PathType Leaf)) { return $null }
    $savedPid = 0
    if (-not [int]::TryParse((Get-Content -LiteralPath $pidPath -Raw).Trim(), [ref] $savedPid)) {
        Remove-Item -LiteralPath $pidPath -Force
        return $null
    }
    $process = Get-Process -Id $savedPid -ErrorAction SilentlyContinue
    if ($null -eq $process) { Remove-Item -LiteralPath $pidPath -Force }
    return $process
}

function Stop-JimboListener {
    $process = Get-JimboProcess
    if ($null -eq $process) { Write-Output 'Jimbo listener is not running.'; return }
    Stop-Process -Id $process.Id
    $process.WaitForExit(5000) | Out-Null
    Remove-Item -LiteralPath $pidPath -Force -ErrorAction SilentlyContinue
    Write-Output "Stopped Jimbo listener PID $($process.Id)."
}

function Start-JimboListener {
    $process = Get-JimboProcess
    if ($null -ne $process) { Write-Output "Jimbo listener is already running as PID $($process.Id)."; return }
    New-Item -ItemType Directory -Path $runtimePath -Force | Out-Null
    $arguments = @('-u', $botPath) + $botArguments
    $process = Start-Process -FilePath $pythonPath -ArgumentList $arguments `
        -WorkingDirectory $projectPath -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath
    Set-Content -LiteralPath $pidPath -Value $process.Id -NoNewline
    Write-Output "Started Jimbo listener PID $($process.Id)."
}

Push-Location $projectPath
try {
    switch ($action) {
        'test' {
            & $pythonPath -m unittest discover -s $testsPath -v
        }
        'bot' {
            & $pythonPath -u $botPath @botArguments
        }
        'start' { Start-JimboListener }
        'stop' { Stop-JimboListener }
        'restart' { Stop-JimboListener; Start-JimboListener }
        'status' {
            $process = Get-JimboProcess
            if ($null -eq $process) { Write-Output 'Jimbo listener is not running.' }
            else { Write-Output "Jimbo listener is running as PID $($process.Id)." }
        }
    }
    if ($action -in @('test', 'bot')) { exit $LASTEXITCODE }
    exit 0
}
finally {
    Pop-Location
}
