@echo off
REM Opens the Clanker control panel (buttons: Start / Stop / Restart / Refresh).
REM pythonw = no console window; the GUI window is the whole UI.
set PYW=C:\Users\ericc\AppData\Local\Programs\Python\Python312\pythonw.exe
if not exist "%PYW%" set PYW=pythonw
start "" "%PYW%" "C:\Users\ericc\.openclaw\clanker_gui.py"
