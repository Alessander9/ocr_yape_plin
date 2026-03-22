"""
Router de la API OCR.
======================
Endpoints para subir imágenes y obtener resultados OCR.
"""

import uuid
import shutil
import asyncio
from pathlib import Path
from typing import List
from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from loguru import logger

from modules.procesador import procesar_lote
from modules.models import ResumenLote

router = APIRouter()

UPLOAD_DIR = Path(__file__).parent.parent.parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

EXTENSIONES_VALIDAS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff"}


def _guardar_archivo(archivo: UploadFile, directorio: Path) -> Path:
    """Guarda el archivo subido y retorna la ruta."""
    ext = Path(archivo.filename).suffix.lower()
    nombre_unico = f"{uuid.uuid4().hex}{ext}"
    ruta = directorio / nombre_unico
    with open(ruta, "wb") as f:
        shutil.copyfileobj(archivo.file, f)
    return ruta


def _limpiar_archivos(rutas: List[Path]):
    """Elimina archivos temporales después del procesamiento."""
    for ruta in rutas:
        try:
            ruta.unlink(missing_ok=True)
        except Exception:
            pass


@router.post(
    "/procesar",
    response_model=ResumenLote,
    summary="Procesar capturas de YAPE/PLIN",
    description="Sube una o varias imágenes para extraer datos OCR estructurados.",
)
async def procesar_capturas(
    background_tasks: BackgroundTasks,
    archivos: List[UploadFile] = File(..., description="Imágenes PNG, JPG, WEBP, etc."),
):
    if not archivos:
        raise HTTPException(status_code=400, detail="No se proporcionaron archivos.")

    if len(archivos) > 50:
        raise HTTPException(status_code=400, detail="Máximo 50 archivos por lote.")

    # Guardar archivos temporalmente
    rutas_guardadas = []
    for archivo in archivos:
        ext = Path(archivo.filename or "").suffix.lower()
        if ext not in EXTENSIONES_VALIDAS:
            raise HTTPException(
                status_code=400,
                detail=f"Formato no permitido: {archivo.filename}. "
                       f"Usar: {', '.join(EXTENSIONES_VALIDAS)}"
            )
        ruta = _guardar_archivo(archivo, UPLOAD_DIR)
        rutas_guardadas.append((ruta, archivo.filename))
        logger.info(f"Archivo recibido: {archivo.filename} -> {ruta.name}")

    # Renombrar con nombre original para el resultado
    rutas_procesamiento = []
    for ruta, nombre_original in rutas_guardadas:
        # Crear un archivo temporal con el nombre original para trazabilidad
        ruta_nombrada = ruta.parent / f"{ruta.stem}_{Path(nombre_original).name}"
        ruta.rename(ruta_nombrada)
        rutas_procesamiento.append(ruta_nombrada)

    try:
        # Run CPU-bound OCR processing in a thread to avoid blocking the event loop
        resumen = await asyncio.to_thread(procesar_lote, rutas_procesamiento)
    except Exception as e:
        logger.error(f"Error procesando lote: {e}")
        # Limpiar en error
        _limpiar_archivos(rutas_procesamiento)
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")

    # Limpiar archivos en background
    background_tasks.add_task(_limpiar_archivos, rutas_procesamiento)

    return resumen


@router.get("/health", summary="Estado del servicio OCR")
async def health_ocr():
    """Verifica qué motores OCR están disponibles."""
    estado = {"status": "ok", "motores": {}}

    try:
        from paddleocr import PaddleOCR
        estado["motores"]["paddleocr"] = "disponible"
    except ImportError:
        estado["motores"]["paddleocr"] = "no instalado"

    try:
        import pytesseract
        pytesseract.get_tesseract_version()
        estado["motores"]["tesseract"] = "disponible"
    except Exception:
        estado["motores"]["tesseract"] = "no instalado"

    return estado
