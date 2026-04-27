@echo off
title Backend - Port 8010
cd /d "%~dp0backend"
echo.
echo  Starting Backend on http://localhost:8010 (LAN: http://^<IPv4^>:8010)
echo  Press CTRL+C to stop
echo.
"C:\Users\islam\AppData\Local\Programs\Python\Python311\python.exe" -m uvicorn app.main:app --host 0.0.0.0 --port 8010 --reload
pause
