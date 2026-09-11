@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo [ERRO] Ambiente virtual .venv nao encontrado.
  echo Crie com: python -m venv .venv
  pause
  exit /b 1
)

call ".venv\Scripts\activate.bat"
python -c "import customtkinter, keyring" >nul 2>&1
if errorlevel 1 (
  echo Instalando dependencias da interface local...
  python -m pip install -r requirements.txt
  if errorlevel 1 (
    echo [ERRO] Nao foi possivel instalar as dependencias.
    pause
    exit /b 1
  )
)

rem Abre o Telegram Extractor com protecao adaptativa de PeerFlood/FloodWait.
start "" ".venv\Scripts\pythonw.exe" "local_app_v19.py"
exit /b 0
