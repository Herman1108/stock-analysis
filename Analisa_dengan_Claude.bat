@echo off
chcp 65001 >nul
title Analisis Saham dengan Claude Code

echo ============================================================
echo     ANALISIS SAHAM DENGAN CLAUDE CODE AI
echo ============================================================
echo.

REM Check if stock code provided
if "%~1"=="" (
    set /p STOCK_CODE="Masukkan Kode Saham (contoh: BBCA): "
) else (
    set STOCK_CODE=%~1
)

echo.
echo [1/2] Mengumpulkan data saham %STOCK_CODE%...

cd /d "C:\Users\chuwi\stock-analysis"

REM First, export data to temp file
python -c "from analyze_to_narrative import generate_narrative; print(generate_narrative('%STOCK_CODE%'))" > "%TEMP%\stock_data_%STOCK_CODE%.txt" 2>nul

if errorlevel 1 (
    echo Error: Gagal mengambil data saham. Pastikan aplikasi stock-analysis berjalan.
    pause
    exit /b 1
)

echo [2/2] Mengirim ke Claude Code untuk analisis mendalam...
echo.

REM Call Claude Code with the data
claude -p "Berikut adalah data analisis saham %STOCK_CODE%. Tolong buatkan narasi edukatif yang komprehensif dalam Bahasa Indonesia, mencakup: 1) Ringkasan kondisi saham saat ini, 2) Interpretasi teknikal (support/resistance), 3) Analisis akumulasi/distribusi, 4) Analisis fundamental, 5) Rekomendasi dan strategi trading dengan money management, 6) Risiko yang perlu diperhatikan. Simpan hasilnya ke file 'C:\doc Herman\analisa analysis\Analisis_AI_%STOCK_CODE%_$(date +%%Y%%m%%d).txt'. Data: $(cat %TEMP%\stock_data_%STOCK_CODE%.txt)"

echo.
echo ============================================================
echo Analisis Claude Code selesai!
echo ============================================================

pause
