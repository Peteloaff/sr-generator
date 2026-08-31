# Run the API (and, with inline queue, the job runner lives in-process).
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
& .\.venv\Scripts\python.exe -m alembic upgrade head
& .\.venv\Scripts\python.exe -m uvicorn sr.api.main:app --reload --port 8000
