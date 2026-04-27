@echo off
title Reset Admin Password
echo.
echo  Stop the backend window first, then press any key...
pause
cd /d "%~dp0backend"
"C:\Users\islam\AppData\Local\Programs\Python\Python311\python.exe" reset_password.py
echo.
pause
