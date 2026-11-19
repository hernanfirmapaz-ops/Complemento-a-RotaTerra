$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

$env:PYTHONPATH = "."
$pythonExe = if (Test-Path ".\.venv\Scripts\python.exe") { ".\.venv\Scripts\python.exe" } else { "python" }

Write-Host "[RotaTerra 3D] El navegador se abrirá automáticamente en http://127.0.0.1:8000 ..." -ForegroundColor Cyan
Start-Process powershell -WindowStyle Hidden -ArgumentList "-NoProfile", "-Command", "for (`$i=0; `$i -lt 40; `$i++) { Start-Sleep -Milliseconds 500; try { `$r = Invoke-WebRequest -Uri 'http://127.0.0.1:8000/api/v1/health' -UseBasicParsing -TimeoutSec 1 -ErrorAction Stop; if (`$r.StatusCode -eq 200) { Start-Process 'http://127.0.0.1:8000'; break } } catch {} }"

Write-Host "[RotaTerra 3D] Levantando Visor 3D + API en http://127.0.0.1:8000 ..." -ForegroundColor Green
& $pythonExe -m uvicorn services.api.app.main:app --host 127.0.0.1 --port 8000
