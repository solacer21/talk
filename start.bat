\
@echo off
setlocal ENABLEDELAYEDEXPANSION

REM === Path to this script ===
cd /d %~dp0

REM === Create venv if missing ===
if not exist venv (
  py -3 -m venv venv
)

REM === Activate venv ===
call venv\Scripts\activate

REM === Upgrade pip and install deps ===
python -m pip install --upgrade pip
pip install -r requirements.txt

REM === Start ngrok (detached window). If ngrok.exe not in PATH, put it in this folder. ===
start "" ngrok http --web-addr=127.0.0.1:4040 5000

REM === Wait a bit for ngrok to be ready ===
timeout /t 5 /nobreak >nul

REM === Set LINE Webhook to current ngrok https URL ===
python update_webhook.py

REM === Run Flask app ===
set FLASK_ENV=development
python app.py

pause
