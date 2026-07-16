param(
    [Parameter(Position = 0)]
    [string] $Command
)

$ErrorActionPreference = 'Stop'

$passwordPath = 'D:\factorio-server\config\rconpw'
$clientPath = 'D:\factorio-rcon\rcon-0.10.3-win64\rcon.exe'
$address = '127.0.0.1:27015'
$commandPath = Join-Path $PSScriptRoot 'rcon-command.txt'

if ([string]::IsNullOrWhiteSpace($Command)) {
    $Command = (Get-Content -LiteralPath $commandPath -Raw).Trim()
}
if ([string]::IsNullOrWhiteSpace($Command)) {
    throw "Factorio RCON command is empty: $commandPath"
}

$password = (Get-Content -LiteralPath $passwordPath -Raw).Trim()
if ([string]::IsNullOrWhiteSpace($password)) {
    throw "Factorio RCON password file is empty: $passwordPath"
}

# rcon.exe treats separate positional arguments as separate queries. Supplying
# exactly one complete command over stdin prevents chat text from being split
# into one query per word.
$Command | & $clientPath -a $address -p $password
exit $LASTEXITCODE
