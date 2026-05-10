@echo off
::::::::::::::
:: AUTONOMOUS SALES MACHINE — DAILY MASTER SCRIPT
::::::::::::::
:: Schedule this with Windows Task Scheduler to run every morning at 9 AM.
::::::::::::::

cd /d "%~dp0"

echo ==========================================
echo AUTONOMOUS AI SALES MACHINE
echo %date% %time%
echo ==========================================

:: ── Step 1: Find latest Lead-OS output ────────────────────
:: If you want to scan first, uncomment the next line:
:: python lead_os_v2.py --city "Hyderabad" --niche "skin" --count 25

:: ── Step 2: Import latest leads into sales queue ──────────
:: Find the most recent output folder and import leads.json
for /f "delims=" %%d in ('dir /b /ad /od output') do set LATEST=%%d
if defined LATEST (
    echo Importing from output\%LATEST%\leads.json
    python sales_engine.py --import-file "output\%LATEST%\leads.json"
) else (
    echo No output folders found. Run Lead-OS first.
    goto :check_followups
)

:: ── Step 3: Process outreach for new leads ────────────────
:check_followups
echo.
echo Running outreach campaign...
python sales_engine.py --process

:: ── Step 4: Show status ───────────────────────────────────
echo.
python sales_engine.py --status

echo.
echo ==========================================
echo PIPELINE COMPLETE
echo ==========================================
pause
