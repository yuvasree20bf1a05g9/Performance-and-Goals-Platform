# Windows one-click setup + run:  powershell -ExecutionPolicy Bypass -File run.ps1 [-DataProfile starter|full]
param([string]$DataProfile = "full")
$ErrorActionPreference = "Stop"
if (-not (Test-Path ".venv")) { python -m venv .venv }
& .\.venv\Scripts\python.exe -m pip install --upgrade pip -q
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt -q
& .\.venv\Scripts\python.exe manage.py all --open --profile $DataProfile
