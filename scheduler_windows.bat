@echo off
REM =============================================================================
REM  Daily Fact Poster — Windows Task Scheduler Setup
REM  Run once as Administrator to register a daily 9:00 AM job.
REM =============================================================================

SET SCRIPT_DIR=%~dp0
SET TASK_NAME=DailyFactPoster
SET LOG_FILE=%SCRIPT_DIR%logs\scheduler.log

:: Detect python path
WHERE python >nul 2>&1
IF ERRORLEVEL 1 (
    echo [ERROR] Python not found on PATH. Install Python and try again.
    pause & exit /b 1
)

:: Create logs directory
IF NOT EXIST "%SCRIPT_DIR%logs" MKDIR "%SCRIPT_DIR%logs"

echo.
echo Registering Windows Task Scheduler job: %TASK_NAME%
echo Script:   %SCRIPT_DIR%main.py
echo Schedule: Daily at 09:00
echo Log file: %LOG_FILE%
echo.

schtasks /create ^
    /tn "%TASK_NAME%" ^
    /tr "cmd /c python \"%SCRIPT_DIR%main.py\" >> \"%LOG_FILE%\" 2>&1" ^
    /sc DAILY ^
    /st 09:00 ^
    /f ^
    /rl HIGHEST ^
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
