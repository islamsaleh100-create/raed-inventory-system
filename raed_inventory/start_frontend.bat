@echo off
title Frontend - Port 3000
cd /d "%~dp0frontend"
echo.
powershell -NoProfile -Command "$ip=(Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.*' } | Select-Object -First 1).IPAddress; if ($ip) { Write-Host ('LAN URL: http://' + $ip + ':3000') } else { Write-Host 'LAN URL: http://^<IPv4^>:3000 (from ipconfig)' }"
echo  Local: http://localhost:3000
echo  Starting Frontend on 0.0.0.0:3000 ...
echo  Press CTRL+C to stop
echo.
npm run dev -- --host 0.0.0.0 --port 3000
pause
