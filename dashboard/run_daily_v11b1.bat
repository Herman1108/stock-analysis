@echo off
REM ============================================================
REM RUN DAILY V11B1 CALCULATIONS
REM Jalankan setelah update data harian
REM ============================================================

echo.
echo ============================================================
echo   DAILY V11B1 CALCULATION
echo ============================================================
echo.

REM Activate virtual environment if exists
if exist "C:\Users\chuwi\stock-analysis\venv\Scripts\activate.bat" (
    call C:\Users\chuwi\stock-analysis\venv\Scripts\activate.bat
)

REM Navigate to dashboard directory
cd /d C:\Users\chuwi\stock-analysis\dashboard

REM Run the calculation script
echo Running calculate_daily_v11b1.py...
echo.

python calculate_daily_v11b1.py %*

echo.
echo ============================================================
echo   DONE
echo ============================================================
echo.

pause
