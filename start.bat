@echo off
REM Double-click to start RAGNAROK, then use it at http://localhost:7860
cd /d "%~dp0"

if not exist venv\Scripts\python.exe (
    echo First run: installing RAGNAROK. This takes a few minutes...
    python -m venv venv || (echo Python 3.12 is required: https://www.python.org/downloads/ & pause & exit /b 1)
    venv\Scripts\python.exe -m pip install -r requirements.txt || (pause & exit /b 1)
)

if not exist .env (
    copy .env.example .env >nul
    echo Add your OpenAI and Pinecone keys to the file that just opened, save it, then run start.bat again.
    notepad .env
    exit /b 0
)

echo Starting RAGNAROK at http://localhost:7860  (close this window to stop it)
start "" cmd /c "timeout /t 8 >nul & start http://localhost:7860"
venv\Scripts\python.exe -m uvicorn server:app --port 7860
pause
