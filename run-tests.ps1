# Runs every automated test: backend (pytest) and the browser end-to-end tests (Playwright).
# The backend (port 8000) and website (port 5173) must be running for the end-to-end part: start them with .\run-dev.ps1 first.
$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "== Backend tests ==" -ForegroundColor Cyan
Push-Location (Join-Path $root "backend"); python -m pytest tests -q; $b = $LASTEXITCODE; Pop-Location

Write-Host "== Language file check ==" -ForegroundColor Cyan
python (Join-Path $root "frontend\i18n\check_i18n.py") | Select-Object -Last 1

Write-Host "== Website type check ==" -ForegroundColor Cyan
Push-Location (Join-Path $root "frontend\web"); npm run typecheck; $t = $LASTEXITCODE

$e = 0
try { Invoke-RestMethod http://127.0.0.1:8000/health -TimeoutSec 3 | Out-Null; Invoke-WebRequest http://127.0.0.1:5173 -UseBasicParsing -TimeoutSec 3 | Out-Null; $up = $true } catch { $up = $false }
if ($up) {
    Write-Host "== Browser end-to-end tests ==" -ForegroundColor Cyan
    npx playwright test e2e/01-language-auth.spec.ts e2e/02-patient.spec.ts e2e/03-doctor-rx.spec.ts e2e/04-chat-rooms.spec.ts e2e/05-pulse-admin-community.spec.ts e2e/06-agents-offline-buddy.spec.ts e2e/08-transplant-hub.spec.ts
    $e = $LASTEXITCODE
} else { Write-Host "Skipped browser tests: start the app first with .\run-dev.ps1" -ForegroundColor Yellow }
Pop-Location

if ($b -eq 0 -and $t -eq 0 -and $e -eq 0) { Write-Host "ALL TESTS PASSED" -ForegroundColor Green } else { Write-Host "Some tests failed (backend=$b types=$t e2e=$e)" -ForegroundColor Red; exit 1 }
