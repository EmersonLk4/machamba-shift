# Preparação do ambiente no Windows (PowerShell). Correr na raiz do repositório:
#   powershell -ExecutionPolicy Bypass -File scripts\setup.ps1

$ErrorActionPreference = "Stop"

python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest

Write-Host ""
Write-Host "Ambiente pronto. Para activar:  .\.venv\Scripts\Activate.ps1"
Write-Host "Testar as APIs:                 python scripts\check_apis.py"
Write-Host "Abrir a aplicacao:              streamlit run app\O_que_plantar.py"
