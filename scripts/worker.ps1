# Run the RQ worker. Only needed when SR_QUEUE_BACKEND=rq (requires Redis/Memurai).
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
& .\.venv\Scripts\python.exe -m sr.worker.worker
