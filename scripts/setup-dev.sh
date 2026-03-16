#!/usr/bin/env bash
set -euo pipefail

echo "Initializing development environment for Cradle_Selrena"

if [ ! -d ".venv" ]; then
  python3 -m venv .venv
  echo "Created .venv"
else
  echo ".venv already exists"
fi

echo "Installing Python dependencies for core..."
. .venv/bin/activate
pip install --upgrade pip
pip install -r core/cradle-selrena-core/requirements.txt

echo "Installing node dependencies via pnpm..."
pnpm install

echo "Bootstrap complete. Activate with: source .venv/bin/activate"
