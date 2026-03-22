"""
OCR Yape & Plin - Backend Principal
====================================
FastAPI app para procesamiento OCR de comprobantes de pago.
"""

import os
# MUST be set before paddle is imported anywhere in the process
os.environ["FLAGS_use_mkldnn"] = "0"
os.environ["FLAGS_use_onednn"] = "0"
os.environ["MKLDNN_CACHE_CAPACITY"] = "0"

import sys
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from loguru import logger

# Agregar path del proyecto
sys.path.insert(0, str(Path(__file__).parent))

from routers.ocr_router import router as ocr_router
from routers.export_router import router as export_router

# ── Configurar logger ─────────────────────────────────────────────────────────
LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

logger.remove()
logger.add(
    sys.stderr,
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}",
    level="INFO",
)
logger.add(
    LOG_DIR / "ocr_{time:YYYY-MM-DD}.log",
    rotation="1 day",
    retention="7 days",
    level="DEBUG",
    encoding="utf-8",
)

# ── Crear app ─────────────────────────────────────────────────────────────────
app = FastAPI(
    title="OCR Yape & Plin",
    description="Sistema OCR de alta precisión para comprobantes YAPE y PLIN",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(ocr_router, prefix="/api/ocr", tags=["OCR"])
app.include_router(export_router, prefix="/api/export", tags=["Exportar"])

# ── Servir frontend estático ──────────────────────────────────────────────────
FRONTEND_DIR = Path(__file__).parent.parent / "frontend"

@app.get("/", response_class=FileResponse)
async def serve_index():
    if (FRONTEND_DIR / "index.html").exists():
        return FileResponse(str(FRONTEND_DIR / "index.html"))
    return {"error": "Frontend no encontrado localmente"}

if FRONTEND_DIR.exists():
    # Montamos el resto de archivos (.js, .css, imágenes) en la raíz
    # IMPORTANTE: Esto debe ir DESPUÉS de los otros routers para no pisarlos
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR)), name="frontend")

# ── Directorio de uploads y exports ───────────────────────────────────────────
for d in ["uploads", "exports"]:
    (Path(__file__).parent.parent / d).mkdir(exist_ok=True)


@app.get("/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
