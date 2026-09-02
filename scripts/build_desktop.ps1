# Build the SR Generator desktop app: a single folder under dist/ containing
# "SR Generator.exe" that runs the whole stack locally (FastAPI + web UI +
# SQLite + local storage), no Python or Node install required on the target PC.
#
#   powershell -ExecutionPolicy Bypass -File scripts\build_desktop.ps1
#
# Prereqs on the build machine: Python 3.12 with this repo installed
# (pip install -e ".[cloud,desktop]"), and Node 18+ for the web build.

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo

Write-Host "==> Building the web UI (static export)..." -ForegroundColor Cyan
Push-Location apps/web
if (-not (Test-Path node_modules)) { npm ci }
$env:STATIC_EXPORT = "1"
$env:NEXT_PUBLIC_API_BASE = "/api"
npm run build
Pop-Location
if (-not (Test-Path apps/web/out/index.html)) {
    throw "web build did not produce apps/web/out/index.html"
}
# Guard against MSYS/Git-Bash mangling "/api" into "C:/Program Files/Git/api"
# (happens if the web build is run from Git Bash instead of this script).
$mangled = Select-String -Path apps/web/out/_next/static/chunks/*.js `
    -Pattern "Program Files/Git/api", ":/Git/api" -List
if ($mangled) { throw "web build baked a mangled API base ($($mangled[0].Line)). Re-run this script from PowerShell, not Git Bash." }

Write-Host "==> Freezing the backend with PyInstaller..." -ForegroundColor Cyan
python -m PyInstaller sr_generator.spec --noconfirm --clean

$out = Join-Path $repo "dist/SR Generator/SR Generator.exe"
if (-not (Test-Path $out)) { throw "PyInstaller did not produce $out" }

Write-Host ""
Write-Host "Done. App folder: dist/SR Generator" -ForegroundColor Green
Write-Host "Run it:           `"$out`"" -ForegroundColor Green
Write-Host "User data lives in ~/.sr-generator (delete it for a clean slate)."
