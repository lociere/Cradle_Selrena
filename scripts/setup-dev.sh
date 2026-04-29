#!/usr/bin/env bash
set -euo pipefail

PYTHON_CORE_DIR="core/python-soul"

echo "Initializing development environment for Cradle_Selrena"

echo "Installing Python dependencies for core (via uv)..."
cd "$PYTHON_CORE_DIR"
uv sync
cd -

echo "Installing node dependencies via pnpm..."
pnpm install

echo "Bootstrap complete. Activate with: source $PYTHON_CORE_DIR/.venv/bin/activate"
# Note: PYTHON_CORE_DIR = core/python-soul (renamed from core/cradle-selrena-core)
