$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent $PSScriptRoot
$PythonBin = Join-Path $RootDir ".venv\Scripts\python.exe"

if (-not (Test-Path $PythonBin)) {
    Write-Error "Missing virtualenv interpreter: $PythonBin`nCreate it with: py -m venv .venv"
}

Write-Host "[Windows 1/5] Checking required packages in .venv"
& $PythonBin -m pip show requests python-dotenv pillow | Out-Null

Write-Host "[Windows 2/5] Checking run_nai_job help"
& $PythonBin (Join-Path $RootDir "src\run_nai_job.py") --help | Out-Null

Write-Host "[Windows 3/5] Checking nai_cli_v2 help"
& $PythonBin (Join-Path $RootDir "src\nai_cli_v2.py") --help | Out-Null

Write-Host "[Windows 4/5] Checking JSON bridge dry-run"
& $PythonBin (Join-Path $RootDir "src\run_nai_job.py") --json '{"prompt":"smoke test","mode":"text"}' --dry-run | Out-Null

Write-Host "[Windows 5/5] Checking payload preview mode"
& $PythonBin (Join-Path $RootDir "src\nai_cli_v2.py") --prompt "smoke test" --debug-payload | Out-Null

Write-Host "Windows smoke test passed."
