$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

if (-not (Test-Path "$root\.venv\Scripts\python.exe")) {
  python -m venv .venv
}

& "$root\.venv\Scripts\python.exe" -m pip install --upgrade pip
& "$root\.venv\Scripts\python.exe" -m pip install -r requirements.txt

Write-Host "Starting CMS Explorer at http://127.0.0.1:5000/cms/explorer"
& "$root\.venv\Scripts\python.exe" app.py
