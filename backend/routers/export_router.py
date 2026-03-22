"""
Router de exportación.
=======================
Endpoints para generar y descargar Excel y PDF.
"""

import uuid
import json
from pathlib import Path
from typing import List
from fastapi import APIRouter, HTTPException, Body
from fastapi.responses import FileResponse
from loguru import logger

from modules.models import ResultadoOCR, ResumenLote
from modules.exportador_excel import exportar_excel
from modules.exportador_pdf import exportar_pdf

router = APIRouter()

EXPORTS_DIR = Path(__file__).parent.parent.parent / "exports"
EXPORTS_DIR.mkdir(exist_ok=True)


def _resultados_desde_body(data: dict) -> List[ResultadoOCR]:
    """Parsea la lista de resultados desde el body JSON."""
    resultados_raw = data.get("resultados", [])
    resultados = []
    for r in resultados_raw:
        try:
            resultados.append(ResultadoOCR(**r))
        except Exception as e:
            logger.warning(f"Error parseando resultado: {e}")
    return resultados


@router.post(
    "/excel",
    summary="Exportar resultados a Excel",
    response_class=FileResponse,
)
async def exportar_a_excel(data: dict = Body(...)):
    """
    Recibe los resultados OCR y genera un archivo Excel para descargar.
    """
    resultados = _resultados_desde_body(data)
    if not resultados:
        raise HTTPException(status_code=400, detail="No hay resultados para exportar.")

    nombre = f"reporte_ocr_{uuid.uuid4().hex[:8]}.xlsx"
    ruta = EXPORTS_DIR / nombre

    try:
        exportar_excel(resultados, ruta)
    except Exception as e:
        logger.error(f"Error generando Excel: {e}")
        raise HTTPException(status_code=500, detail=f"Error generando Excel: {str(e)}")

    return FileResponse(
        path=str(ruta),
        filename="reporte_ocr_yape_plin.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@router.post(
    "/pdf",
    summary="Exportar resultados a PDF",
    response_class=FileResponse,
)
async def exportar_a_pdf(data: dict = Body(...)):
    """
    Recibe los resultados OCR y genera un PDF profesional para descargar.
    """
    resultados = _resultados_desde_body(data)
    if not resultados:
        raise HTTPException(status_code=400, detail="No hay resultados para exportar.")

    nombre = f"reporte_ocr_{uuid.uuid4().hex[:8]}.pdf"
    ruta = EXPORTS_DIR / nombre

    try:
        exportar_pdf(resultados, ruta)
    except Exception as e:
        logger.error(f"Error generando PDF: {e}")
        raise HTTPException(status_code=500, detail=f"Error generando PDF: {str(e)}")

    return FileResponse(
        path=str(ruta),
        filename="reporte_ocr_yape_plin.pdf",
        media_type="application/pdf",
    )


@router.post(
    "/json",
    summary="Descargar resultados en JSON",
)
async def exportar_a_json(data: dict = Body(...)):
    """Retorna los resultados como JSON descargable."""
    resultados = _resultados_desde_body(data)
    if not resultados:
        raise HTTPException(status_code=400, detail="No hay resultados para exportar.")

    nombre = f"resultados_ocr_{uuid.uuid4().hex[:8]}.json"
    ruta = EXPORTS_DIR / nombre

    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(
            [r.model_dump(mode="json") for r in resultados],
            f,
            ensure_ascii=False,
            indent=2,
            default=str,
        )

    return FileResponse(
        path=str(ruta),
        filename="resultados_ocr.json",
        media_type="application/json",
    )
