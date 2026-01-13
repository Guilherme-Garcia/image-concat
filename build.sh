#!/usr/bin/env bash
set -e
mkdir -p outputs
pyinstaller --onefile --noconfirm \
  --add-data "templates:templates" \
  --add-data "static:static" \
  --add-data "outputs:outputs" \
  --clean \
  --name "ImageConcatenator" \
  app.py

echo "Build finished. See dist/ImageConcatenator"