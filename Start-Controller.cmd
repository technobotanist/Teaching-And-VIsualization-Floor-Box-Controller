@echo off
setlocal
title T^&V HDMI Floor Box Controller
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\Start-Controller.ps1" -AutoInstall %*
set "ControllerExitCode=%ERRORLEVEL%"
if not "%ControllerExitCode%"=="0" (
    echo.
    echo Controller startup failed. Review the message above, then try again.
    pause
)
exit /b %ControllerExitCode%