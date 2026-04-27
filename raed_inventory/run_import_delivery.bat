@echo off
title Import Delivery Data 2026
cd /d "%~dp0backend"
echo.
echo  Importing January 2026 delivery data...
echo.
"C:\Users\islam\AppData\Local\Programs\Python\Python311\python.exe" import_delivery_2026.py
