param(
    [int]$Port = 8000,
    [switch]$Demo,
    [switch]$InspectDatabase
)
$ErrorActionPreference = 'Stop'
$env:PYTHONPATH = Join-Path $PSScriptRoot 'src'
$env:PYTHONIOENCODING = 'utf-8'
$envFile = Join-Path $PSScriptRoot '.env'
if (Test-Path -LiteralPath $envFile) {
    foreach ($line in (Get-Content -LiteralPath $envFile -Encoding UTF8)) {
        if ($line.Trim() -eq '' -or $line.Trim().StartsWith('#')) { continue }
        if ($line -notmatch '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=(.*)$') { throw 'Invalid .env line: expected NAME=value' }
        $variableName = $Matches[1]
        $variableValue = $Matches[2].Trim()
        if ($variableValue.Length -ge 2 -and (($variableValue.StartsWith('"') -and $variableValue.EndsWith('"')) -or ($variableValue.StartsWith("'") -and $variableValue.EndsWith("'")))) {
            $variableValue = $variableValue.Substring(1, $variableValue.Length - 2)
        }
        if ($null -eq [Environment]::GetEnvironmentVariable($variableName, 'Process')) {
            [Environment]::SetEnvironmentVariable($variableName, $variableValue, 'Process')
        }
    }
}
$config = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'config.json') -Raw -Encoding UTF8 | ConvertFrom-Json
if ($config.collection.mode -eq 'database' -or $InspectDatabase) {
    $database = $config.database
    $defaults = @{}
    $defaults[$database.host_env] = '127.0.0.1'
    $defaults[$database.port_env] = '3306'
    $defaults[$database.user_env] = 'root'
    foreach ($name in $defaults.Keys) {
        if (-not [Environment]::GetEnvironmentVariable($name, 'Process')) {
            [Environment]::SetEnvironmentVariable($name, $defaults[$name], 'Process')
        }
    }
    if ($null -eq [Environment]::GetEnvironmentVariable($database.password_env, 'Process')) {
        $secret = Read-Host 'MySQL password (not saved)' -AsSecureString
        $credential = [pscredential]::new('database', $secret)
        [Environment]::SetEnvironmentVariable($database.password_env, $credential.GetNetworkCredential().Password, 'Process')
        $credential = $null
        $secret = $null
    }
}
$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    $python = 'python'
}
$arguments = @('-m', 'public_sentiment', '--data-dir', $PSScriptRoot, '--port', $Port)
if ($Demo) { $arguments += '--demo' }
if ($InspectDatabase) { $arguments += '--inspect-database' }
& $python @arguments
exit $LASTEXITCODE
