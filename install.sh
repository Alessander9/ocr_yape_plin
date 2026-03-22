#!/usr/bin/env bash
# ============================================================
# install.sh — Instalador del sistema OCR Yape & Plin
# Compatible con Ubuntu/Debian y macOS (con Homebrew)
# ============================================================

set -e

echo ""
echo "============================================================"
echo "  OCR Yape & Plin — Instalación automática"
echo "============================================================"
echo ""

# ── Verificar Python ──────────────────────────────────────────
if ! command -v python3 &>/dev/null; then
  echo "[ERROR] Python3 no está instalado. Instálalo antes de continuar."
  exit 1
fi

PY_VER=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "[INFO] Python encontrado: $PY_VER"

# ── Crear entorno virtual ─────────────────────────────────────
echo "[INFO] Creando entorno virtual..."
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip --quiet

# ── Instalar Tesseract en sistema ─────────────────────────────
echo "[INFO] Verificando Tesseract..."
if command -v tesseract &>/dev/null; then
  echo "[OK] Tesseract ya instalado: $(tesseract --version | head -1)"
else
  if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    echo "[INFO] Instalando Tesseract (Ubuntu/Debian)..."
    sudo apt-get install -y tesseract-ocr tesseract-ocr-spa > /dev/null
  elif [[ "$OSTYPE" == "darwin"* ]]; then
    echo "[INFO] Instalando Tesseract (macOS via brew)..."
    brew install tesseract tesseract-lang
  else
    echo "[WARN] Sistema no reconocido. Instala Tesseract manualmente:"
    echo "       https://tesseract-ocr.github.io/tessdoc/Installation.html"
  fi
fi

# ── Instalar dependencias Python ──────────────────────────────
echo "[INFO] Instalando dependencias Python..."
pip install -r requirements.txt --quiet

echo ""
echo "============================================================"
echo "  Instalación completada!"
echo ""
echo "  Para iniciar el servidor:"
echo "    source venv/bin/activate"
echo "    cd backend && python main.py"
echo ""
echo "  La interfaz estará en: http://localhost:8000"
echo "============================================================"
echo ""
