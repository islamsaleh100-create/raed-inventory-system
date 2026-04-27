@echo off
REM ============================================================
REM  Pack C / Phase 1+2 - Sales Channels Unification
REM  Runs: alembic migration  -> seed 10 channels  -> unit tests -> API tests
REM  Double-click this file from File Explorer, or run from CMD.
REM ============================================================

setlocal
cd /d "%~dp0\backend"

if not exist "alembic.ini" (
    echo ERROR: Cannot find alembic.ini in %CD%
    echo Expected to run from: raed_inventory\backend
    pause
    exit /b 1
)

REM Use the same Python path as start_backend.bat
set "PYEXE=C:\Users\islam\AppData\Local\Programs\Python\Python311\python.exe"

if not exist "%PYEXE%" (
    echo ERROR: Cannot find Python at: %PYEXE%
    echo Open start_backend.bat and copy the Python path from there into this file.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   Pack C / Phase 1+2 - Sales Channels Unification
echo ============================================================
echo Using Python: %PYEXE%
echo Working dir:  %CD%

echo.
echo [1/4] Running Alembic migration (sales_channels tables)...
echo ----------------------------------------------------------
"%PYEXE%" -m alembic upgrade head
if errorlevel 1 goto :error

echo.
echo [2/4] Seeding 10 sales channels (7 apps + 3 payments)...
echo ----------------------------------------------------------
"%PYEXE%" seed_sales_channels.py
if errorlevel 1 goto :error

echo.
echo [3/4] Running unit tests (service layer)...
echo ----------------------------------------------------------
"%PYEXE%" -m pytest tests/test_sales_channels.py -v
if errorlevel 1 goto :error

echo.
echo [4/4] Running API tests...
echo ----------------------------------------------------------
"%PYEXE%" -m pytest tests/test_sales_channels_api.py -v
if errorlevel 1 goto :error

echo.
echo ============================================================
echo   SUCCESS - Pack C / Phase 1+2 ready
echo ============================================================
echo.
echo Next step: restart start_backend.bat, then refresh the browser.
pause
exit /b 0

:error
echo.
echo ============================================================
echo   FAILED at previous step. See output above for details.
echo ============================================================
pause
exit /b 1
