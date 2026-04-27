$ErrorActionPreference = "Stop"

$projectRoot = "C:\raed_inventory_system\raed_inventory"
$backendRoot = Join-Path $projectRoot "backend"
$frontendRoot = Join-Path $projectRoot "frontend"
$pythonExe = "C:\Users\islam\AppData\Local\Programs\Python\Python311\python.exe"
$nodeExe = "C:\Program Files\nodejs\node.exe"
$viteCli = Join-Path $frontendRoot "node_modules\vite\bin\vite.js"
$dbPath = Join-Path $backendRoot "raed_inventory_local.db"
$skipSeed = $env:SKIP_SEED -eq "1"

$env:PYTHONUTF8 = "1"
if (Test-Path Env:PATH) {
    Remove-Item Env:PATH
}

function Stop-ListenerIfExists {
    param([int]$Port)

    try {
        $connections = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction Stop
        $processIds = $connections | Select-Object -ExpandProperty OwningProcess -Unique
        foreach ($processId in $processIds) {
            Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
        }
        if ($processIds) {
            Start-Sleep -Seconds 1
        }
    } catch {
        # Ignore when the port is not in use or when the current shell cannot inspect listeners.
    }
}

Push-Location $backendRoot
try {
    Stop-ListenerIfExists -Port 8010

    if (-not $skipSeed -and -not (Test-Path $dbPath)) {
        Write-Host "Seeding backend database..."
        & $pythonExe "seed.py"
    } elseif ($skipSeed) {
        Write-Host "Skipping seed because SKIP_SEED=1"
    } else {
        Write-Host "Skipping seed because database already exists: $dbPath"
    }

    Write-Host "Starting backend on http://localhost:8010 ..."
    $backendOut = Join-Path $backendRoot "backend.log"
    $backendErr = Join-Path $backendRoot "backend.err.log"
    Start-Process -FilePath $pythonExe `
        -ArgumentList "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8010" `
        -WorkingDirectory $backendRoot `
        -RedirectStandardOutput $backendOut `
        -RedirectStandardError $backendErr
} finally {
    Pop-Location
}

Push-Location $frontendRoot
try {
    Stop-ListenerIfExists -Port 3000

    Write-Host "Starting frontend on http://localhost:3000 ..."
    $frontendOut = Join-Path $frontendRoot "frontend.log"
    $frontendErr = Join-Path $frontendRoot "frontend.err.log"
    Start-Process -FilePath $nodeExe `
        -ArgumentList $viteCli, "--host", "0.0.0.0", "--port", "3000" `
        -WorkingDirectory $frontendRoot `
        -RedirectStandardOutput $frontendOut `
        -RedirectStandardError $frontendErr
} finally {
    Pop-Location
}

Write-Host "Frontend: http://localhost:3000"
Write-Host "API Docs:  http://localhost:8010/api/docs"
