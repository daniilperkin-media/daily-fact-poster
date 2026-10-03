@echo off
REM =============================================================================
REM  Daily Fact Poster — Windows Task Scheduler Setup
REM  Run once as Administrator to register a daily 9:00 AM job.
REM =============================================================================

SET SCRIPT_DIR=%~dp0
SET TASK_NAME=DailyFactPoster
SET LOG_FILE=%SCRIPT_DIR%logs\scheduler.log

:: Prefer the project virtualenv; fall back to python on PATH
SET PYTHON_EXE=python
IF EXIST "%SCRIPT_DIR%.venv\Scripts\python.exe" SET PYTHON_EXE=%SCRIPT_DIR%.venv\Scripts\python.exe
IF EXIST "%SCRIPT_DIR%.venv\Scripts\python.exe" GOTO :python_ok

echo [WARN] No .venv found in the project. Create one first:
echo        python -m venv .venv
echo        .venv\Scripts\pip install -r requirements.txt
WHERE python >nul 2>&1
IF ERRORLEVEL 1 (
    echo [ERROR] Python not found on PATH. Install Python or create .venv first.
    pause
    exit /b 1
)
:python_ok

:: Create logs directory
IF NOT EXIST "%SCRIPT_DIR%logs" MKDIR "%SCRIPT_DIR%logs"

echo.
echo Registering Windows Task Scheduler job: %TASK_NAME%
echo Script:   %SCRIPT_DIR%main.py
echo Python:   %PYTHON_EXE%
echo Schedule: Daily at 09:00
echo Log file: %LOG_FILE%
echo.

schtasks /create ^
    /tn "%TASK_NAME%" ^
    /tr "cmd /c \"%PYTHON_EXE%\" \"%SCRIPT_DIR%main.py\" >> \"%LOG_FILE%\" 2>&1" ^
    /sc DAILY ^
    /st 09:00 ^
    /f ^
    /rl HIGHEST ^
    /it ^
    /ru "%USERNAME%"

IF %ERRORLEVEL% EQU 0 (
    echo.
    echo [SUCCESS] Task "%TASK_NAME%" registered!
    echo.
    echo Useful commands:
    echo   Run now:   schtasks /run /tn "%TASK_NAME%"
    echo   View:      schtasks /query /tn "%TASK_NAME%"
    echo   Delete:    schtasks /delete /tn "%TASK_NAME%" /f
    echo   Edit time: schtasks /change /tn "%TASK_NAME%" /st HH:MM
) ELSE (
    echo.
    echo [ERROR] Registration failed. Make sure you ran this script as Administrator.
    echo Right-click the .bat file and choose "Run as administrator".
)

pause
