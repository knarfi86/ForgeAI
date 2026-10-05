param(
    [string]$ProjectRoot = (Join-Path $env:USERPROFILE 'Desktop\ForgeAI')
)
$ErrorActionPreference = 'Stop'
$Python = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $Python)) {
    throw "ForgeAI-venv nicht gefunden: $Python. Projektpfad mit -ProjectRoot angeben."
}
& $Python (Join-Path $PSScriptRoot 'install.py') --project $ProjectRoot
exit $LASTEXITCODE
