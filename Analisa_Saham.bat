@echo off
chcp 65001 >nul
title HermanStock - Analisis Saham ke Narasi

echo ============================================================
echo        HERMANSTOCK - ANALISIS SAHAM KE NARASI EDUKATIF
echo ============================================================
echo.

REM Check if stock code provided as argument
if "%~1"=="" (
    set /p STOCK_CODE="Masukkan Kode Saham (contoh: BBCA): "
) else (
    set STOCK_CODE=%~1
)

echo.
echo Menganalisis saham %STOCK_CODE%...
echo.

cd /d "C:\Users\chuwi\stock-analysis"
python analyze_to_narrative.py %STOCK_CODE%

echo.
echo ============================================================
echo Analisis selesai! File tersimpan di:
echo C:\doc Herman\analisa analysis
echo ============================================================
echo.

REM Open the output folder
start "" "C:\doc Herman\analisa analysis"

pause
