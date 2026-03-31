@echo off
setlocal

cd /d %~dp0

if not exist .venv (
    echo [INFO] Criando ambiente virtual Python...
    python -m venv .venv
)

call .venv\Scripts\activate

echo [INFO] Instalando dependencias...
python -m pip install --upgrade pip
pip install -r requirements.txt

echo [INFO] Iniciando FastAPI em 0.0.0.0:8000...
uvicorn app.main:app --host 0.0.0.0 --port 8000

endlocal
