@echo off
title Seed Delivery Data
cd /d "%~dp0backend"
echo.
echo  Loading delivery branches from Excel files...
echo.
"C:\Users\islam\AppData\Local\Programs\Python\Python311\python.exe" seed_delivery.py
echo.
echo  Done! Press any key to close.
pause
