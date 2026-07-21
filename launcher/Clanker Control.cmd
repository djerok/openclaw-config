@echo off
setlocal
title Clanker Control
set PY=C:\Users\ericc\AppData\Local\Programs\Python\Python312\python.exe
set CTL=C:\Users\ericc\.openclaw\clanker_control.py
if not exist "%PY%" set PY=python3

:menu
cls
echo.
echo   ============================================
echo      CLANKER  --  Discord bot control panel
echo   ============================================
echo.
echo      [1]  START    (bot + watcher + voice + status board)
echo      [2]  STOP     (shut everything down)
echo      [3]  STATUS   (what's running right now)
echo      [4]  RESTART  (stop, then start)
echo.
echo      [Q]  Quit this panel  (leaves the bot as-is)
echo.
set "choice="
set /p choice=   Pick a number:
if /i "%choice%"=="1" goto start
if /i "%choice%"=="2" goto stop
if /i "%choice%"=="3" goto status
if /i "%choice%"=="4" goto restart
if /i "%choice%"=="Q" goto end
goto menu

:start
echo.
echo   Starting the clanker stack...
"%PY%" "%CTL%" start
echo.
pause
goto menu

:stop
echo.
echo   Stopping everything...
"%PY%" "%CTL%" stop
echo.
pause
goto menu

:status
echo.
"%PY%" "%CTL%" status
echo.
pause
goto menu

:restart
echo.
echo   Stopping...
"%PY%" "%CTL%" stop
echo.
echo   Starting...
"%PY%" "%CTL%" start
echo.
pause
goto menu

:end
endlocal
