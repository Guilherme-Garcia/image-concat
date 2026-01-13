# Image Concatenator (Flask + Pillow) — with reorder, resize, alignment, packaging tips
# Vibe coded with GitHub Copilot

This repository contains a small local web app that concatenates images with features:
- Drag & drop reordering in the browser (uploads and server-folder picks)
- Resize/fit options and alignment controls
- Packaging scripts and a GitHub Actions workflow to build a Windows single-file executable using PyInstaller

Quick start (local)
1. Create & activate a virtual environment (recommended):
   python -m venv venv
   .\venv\Scripts\Activate.ps1   # PowerShell (Windows)
   source venv/bin/activate      # Linux/macOS

2. Install dependencies:
   pip install -r requirements.txt

3. Run:
   python app.py

4. Open http://127.0.0.1:5000/ in your browser.

Build Windows single-file exe (local)
1. Install PyInstaller:
   pip install pyinstaller

2. Ensure `outputs` folder exists (build script does this automatically).
3. Run the provided build script (PowerShell):
   .\build.ps1

Result: .\dist\ImageConcatenator.exe

Build via GitHub Actions
The workflow `.github/workflows/build-windows.yml` will produce a Windows executable artifact when pushed to `main`.

Notes
- When using the server-folder mode, paths are constrained to the app root for safety.
- Uploaded files are stored temporarily in `uploads/` and removed after processing.
- Output files saved to the server go into the specified folder (defaults to `outputs/`).
- The packaged exe will store `uploads/` and `outputs/` next to the executable.
