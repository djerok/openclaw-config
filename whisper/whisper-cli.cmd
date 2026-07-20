@echo off
REM OpenClaw calls this as the transcription command; basename "whisper-cli" so OpenClaw
REM reads the -of <base>.txt output. It just hands OpenClaw's args to the load-aware router.
"C:\Users\ericc\AppData\Local\Programs\Python\Python312\python.exe" "%~dp0whisper_router.py" %*
