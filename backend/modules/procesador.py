"""
Orquestador principal del procesamiento OCR.
============================================
Coordina todas las capas: preprocesado → OCR → parsing → validación.
"""

import time
from pathlib import Path
from typing import List
from loguru import logger

from modules.preprocesador import preprocesar_imagen
from modules.ocr_engine import ejecutar_ocr_sobre_versiones
from modules.parser import parsear_comprobante
from modules.detector_duplicados import RegistroHashes
from modules.models import ResultadoOCR, ResumenLote, NivelConfianza


EXTENSIONES_PERMITIDAS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff"}


def procesar_archivo(
    ruta: Path,
    registro_hashes: RegistroHashes,
) -> ResultadoOCR:
    """
    Procesa un único archivo de imagen.
    Retorna el resultado OCR estructurado.
    """
    inicio = time.time()
    nombre = ruta.name
    logger.info(f"Procesando: {nombre}")

    # Verificar extensión
    if ruta.suffix.lower() not in EXTENSIONES_PERMITIDAS:
        return ResultadoOCR(
            archivo=nombre,
            extension_archivo=ruta.suffix,
            error=f"Formato no soportado: {ruta.suffix}",
            observaciones=[f"El sistema sólo acepta: {', '.join(EXTENSIONES_PERMITIDAS)}"],
        )

    # Hash y detección de duplicados
    try:
        hash_md5, es_duplicado = registro_hashes.verificar_y_registrar(ruta)
    except Exception as e:
        logger.warning(f"Error calculando hash de {nombre}: {e}")
        hash_md5 = "error"
        es_duplicado = False

    # Preprocesamiento
    try:
        versiones, calidad = preprocesar_imagen(ruta)
    except Exception as e:
        logger.error(f"Error en preprocesamiento de {nombre}: {e}")
        return ResultadoOCR(
            archivo=nombre,
            extension_archivo=ruta.suffix,
            hash_imagen=hash_md5,
            posible_duplicado=es_duplicado,
            error=f"Error en preprocesamiento: {str(e)}",
            observaciones=["No se pudo preprocesar la imagen."],
        )

    # OCR sobre todas las versiones
    try:
        texto, confianza_ocr, motor, lineas = ejecutar_ocr_sobre_versiones(versiones)
    except Exception as e:
        logger.error(f"Error en OCR de {nombre}: {e}")
        return ResultadoOCR(
            archivo=nombre,
            extension_archivo=ruta.suffix,
            hash_imagen=hash_md5,
            posible_duplicado=es_duplicado,
            calidad_imagen_estimada=calidad,
            error=f"Error en OCR: {str(e)}",
            observaciones=["Fallo en el motor OCR."],
        )

    # Parsing semántico y validación
    tiempo_total = round(time.time() - inicio, 2)
    resultado = parsear_comprobante(
        texto=texto,
        nombre_archivo=nombre,
        confianza_ocr=confianza_ocr,
        motor_ocr=motor,
        hash_img=hash_md5,
        calidad_imagen=calidad,
        tiempo_seg=tiempo_total,
    )
    resultado.posible_duplicado = es_duplicado

    logger.info(
        f"✓ {nombre} | tipo={resultado.tipo_app} | "
        f"monto={resultado.monto} | confianza={resultado.confianza_global:.2f} | "
        f"tiempo={tiempo_total}s"
    )
    return resultado


def procesar_lote(rutas: List[Path]) -> ResumenLote:
    """
    Procesa un lote de archivos de imagen.
    Retorna el resumen con todos los resultados.
    """
    registro = RegistroHashes()
    resultados: List[ResultadoOCR] = []

    for ruta in rutas:
        resultado = procesar_archivo(ruta, registro)
        resultados.append(resultado)

    # Calcular estadísticas del lote
    exitosos = sum(1 for r in resultados if r.nivel_confianza == NivelConfianza.ALTA)
    con_dudas = sum(1 for r in resultados if r.nivel_confianza in [NivelConfianza.MEDIA, NivelConfianza.BAJA])
    errores = sum(1 for r in resultados if r.error)
    n_yape = sum(1 for r in resultados if r.tipo_app and r.tipo_app.value == "YAPE")
    n_plin = sum(1 for r in resultados if r.tipo_app and r.tipo_app.value == "PLIN")
    n_desc = len(resultados) - n_yape - n_plin
    montos = [r.monto for r in resultados if r.monto is not None]
    confs = [r.confianza_global for r in resultados if r.confianza_global is not None]
    duplicados = sum(1 for r in resultados if r.posible_duplicado)

    return ResumenLote(
        total_archivos=len(resultados),
        exitosos=exitosos,
        con_dudas=con_dudas,
        errores=errores,
        capturas_yape=n_yape,
        capturas_plin=n_plin,
        capturas_desconocidas=n_desc,
        suma_montos=sum(montos),
        promedio_confianza=sum(confs) / len(confs) if confs else 0.0,
        posibles_duplicados=duplicados,
        resultados=resultados,
    )
