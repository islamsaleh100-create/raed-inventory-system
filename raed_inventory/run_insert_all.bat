@echo off
title Insert All Branches
echo.
echo  *** Close the backend window first, then press any key ***
echo.
pause
cd /d "%~dp0backend"
"C:\Users\islam\AppData\Local\Programs\Python\Python311\python.exe" insert_all.py
