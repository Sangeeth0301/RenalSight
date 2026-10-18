# RenalSight: one-command local start (Windows PowerShell)
#   .\run-dev.ps1            start the backend (port 8000) and the website (port 5173), seed demo accounts, open the browser
#   .\run-dev.ps1 -Reset     also delete the local database first (fresh demo data)
param([switch]$Reset, [switch]$NoBrowser)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$backend = Join-Path $root "backend"
$web = Join-Path $root "frontend\web"

function Need($cmd, $hint) { if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) { Write-Host "Missing '$cmd'. $hint" -ForegroundColor Red; exit 1 } }
Need python "Install Python 3.11+ from python.org."
Need node "Install Node.js 20+ from nodejs.org."

# 1) backend setup
if (-not (Test-Path (Join-Path $backend ".env"))) {
    $key = python -c "import secrets; print(secrets.token_urlsafe(48))"
    @("SECRET_KEY=$key", "LLM_CHAIN=gemini,groq,openai,xai,ollama,rules", "OLLAMA_ENABLED=false", "BUDDY_MESSAGES_PER_MINUTE=30") | Set-Content -Path (Join-Path $backend ".env") -Encoding utf8
    Write-Host "Created backend\.env (add your AI provider keys there; the app works without them)." -ForegroundColor Yellow
}
python -c "import fastapi, uvicorn, sqlalchemy, xgboost, lifelines, shap, fitz" 2>$null
if ($LASTEXITCODE -ne 0) { Write-Host "Installing Python packages..." -ForegroundColor Cyan; python -m pip install -r (Join-Path $backend "requirements.txt") }
if ($Reset -and (Test-Path (Join-Path $backend "renalsight.db"))) { Remove-Item (Join-Path $backend "renalsight.db") -Force; Write-Host "Database reset." -ForegroundColor Yellow }

# 2) frontend setup
if (-not (Test-Path (Join-Path $web "node_modules"))) { Write-Host "Installing website packages..." -ForegroundColor Cyan; Push-Location $web; npm install; Pop-Location }

# 3) start both servers in their own windows
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$backend'; python -m uvicorn app.main:app --port 8000 --host 127.0.0.1" -WindowStyle Normal
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$web'; npm run dev" -WindowStyle Normal

# 4) wait for the API, then seed demo accounts
Write-Host "Waiting for the backend..." -ForegroundColor Cyan
for ($i = 0; $i -lt 60; $i++) { try { Invoke-RestMethod http://127.0.0.1:8000/health -TimeoutSec 2 | Out-Null; break } catch { Start-Sleep 1 } }
Push-Location $backend
python seed_demo.py
python create_admin.py admin@example.com "Demo@12345" "Admin" 2>$null
Pop-Location

Write-Host ""
Write-Host "RenalSight is running:" -ForegroundColor Green
Write-Host "  Website : http://127.0.0.1:5173"
Write-Host "  API docs: http://127.0.0.1:8000/docs"
Write-Host "  Demo logins (password Demo@12345): asha@example.com (patient), dr.rao@example.com (doctor), admin@example.com, brother@example.com (family)"
if (-not $NoBrowser) { Start-Process "http://127.0.0.1:5173" }
