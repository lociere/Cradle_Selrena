Write-Host "Initializing development environment for Cradle_Selrena"

# Create Python virtual environment
if (-Not (Test-Path -Path ".venv")) {
    python -m venv .venv
    Write-Host "Created .venv"
} else {
    Write-Host ".venv already exists"
}

Write-Host "Installing Python dependencies for core..."
& .\.venv\Scripts\pip.exe install --upgrade pip
& .\.venv\Scripts\pip.exe install -r core\cradle-selrena-core\requirements.txt

Write-Host "Installing node dependencies via pnpm..."
pnpm install

Write-Host "Bootstrap complete. Activate the Python venv with: .\.venv\Scripts\Activate.ps1"
