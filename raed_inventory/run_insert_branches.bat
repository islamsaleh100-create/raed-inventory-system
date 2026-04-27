@echo off
title Insert Branches
cd /d "%~dp0backend"
echo.
echo  Loading branches into the system...
echo  (Make sure the backend is running first)
echo.
"C:\Users\islam\AppData\Local\Programs\Python\Python311\python.exe" insert_branches.py
