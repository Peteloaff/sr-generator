# One-time setup: create venv, install deps, create .env, migrate DB.
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

if (-not (Test-Path ".venv")) { python -m venv .venv }
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -e ".[dev,rq]"

if (-not (Test-Path ".env")) { Copy-Item ".env.example" ".env"; Write-Host "created .env" }

& .\.venv\Scripts\python.exe -m alembic upgrade head
Write-Host "`nSetup complete. Run:  .\scripts\dev.ps1"
