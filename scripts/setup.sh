#!/usr/bin/env bash
# Preparação do ambiente em Linux ou macOS. Correr na raiz do repositório:
#   bash scripts/setup.sh
set -euo pipefail

python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m pytest

echo
echo "Ambiente pronto. Para activar:  source .venv/bin/activate"
echo "Testar as APIs:                 python scripts/check_apis.py"
echo "Abrir a aplicação:              streamlit run app/Home.py"
