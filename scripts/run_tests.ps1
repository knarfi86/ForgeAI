$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$ReportDir = Join-Path $ProjectRoot "test_reports"

if (-not (Test-Path $Python)) {
    Write-Error "ForgeAI-venv wurde nicht gefunden: $Python"
}

New-Item -ItemType Directory -Path $ReportDir -Force | Out-Null

$Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$TextReport = Join-Path $ReportDir "test-$Timestamp.txt"
$JsonReport = Join-Path $ReportDir "test-$Timestamp.json"

Push-Location $ProjectRoot

try {
    Write-Host ""
    Write-Host "=== ForgeAI Test Runner ==="
    Write-Host ""

    $PythonVersion = & $Python --version 2>&1
    Write-Host $PythonVersion
    Write-Host ""

    Write-Host "=== compileall ==="
    & $Python -m compileall forgeai 2>&1
    $CompileExit = $LASTEXITCODE

    Write-Host ""
    Write-Host "=== git diff --check ==="
    git diff --check
    $DiffExit = $LASTEXITCODE

    Write-Host ""
    Write-Host "=== pytest ==="

    $PytestOutput = & $Python -m pytest -v 2>&1
    $PytestExit = $LASTEXITCODE

    $PytestOutput | Tee-Object -FilePath $TextReport

    $Status = if ($CompileExit -eq 0 -and $DiffExit -eq 0 -and $PytestExit -eq 0) {
        "PASS"
    } else {
        "FAIL"
    }

    $GitStatus = git status --short | Out-String
    $GitCommit = git rev-parse HEAD

    $Report = [ordered]@{
        timestamp = (Get-Date).ToString("o")
        status = $Status
        python = $PythonVersion.ToString()
        git_commit = $GitCommit
        compileall_exit_code = $CompileExit
        diff_check_exit_code = $DiffExit
        pytest_exit_code = $PytestExit
        git_status = $GitStatus.Trim()
        pytest_output_file = $TextReport
    }

    $Report | ConvertTo-Json -Depth 5 | Set-Content -Path $JsonReport -Encoding UTF8

    Write-Host ""
    Write-Host "=== Ergebnis: $Status ==="
    Write-Host "Textreport: $TextReport"
    Write-Host "JSON-Report: $JsonReport"

    if ($Status -eq "PASS") {
        exit 0
    }

    exit 1
}
finally {
    Pop-Location
}
