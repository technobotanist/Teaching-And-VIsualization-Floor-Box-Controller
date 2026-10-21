@echo off
call "%~dp0Start-Controller.cmd" -Simulate %*
exit /b %ERRORLEVEL%
