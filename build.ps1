# PowerShell build script for Windows (run in project root)
# Usage: Open PowerShell and run: .\build.ps1

set -e

# Ensure outputs folder exists (PyInstaller --add-data requires source path)
if (-Not (Test-Path -Path ".\outputs")) {
  New-Item -ItemType Directory -Path .\outputs | Out-Null
}

# Build single-file executable
pyinstaller --onefile --noconfirm `
  --add-data "templates;templates" `
  --add-data "static;static" `
  --add-data "outputs;outputs" `
  --clean `
  --name "ImageConcatenator" `
  app.py

Write-Host "Build finished. Executable is in: .\dist\ImageConcatenator.exe"