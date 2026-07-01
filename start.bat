@echo off
REM ============================================================
REM  S&T COCKPIT - one-click launcher
REM  Double-click this file to open the app in your browser.
REM ============================================================
cd /d "%~dp0"
title S^&T Cockpit
echo.
echo   Starting the S^&T Cockpit...
echo   Your browser will open at http://localhost:8501
echo.
echo   KEEP THIS WINDOW OPEN while you use the app.
echo   Close it (or press Ctrl+C) to stop the app.
echo.

python -m streamlit run app.py

echo.
echo   App stopped. You can close this window.
pause
