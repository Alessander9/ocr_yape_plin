"""
Módulo OCR híbrido.
===================
Motor principal: PaddleOCR
Motor de respaldo: Tesseract
Estrategia: ensemble + reconciliación por confianza.
"""

import time
import numpy as np
from typing import List, Tuple, Optional, Dict, Any
from loguru import logger
from PIL import Image


# ── Inicialización lazy de motores ────────────────────────────────────────────
_paddle_ocr = None
_tesseract_disponible = False


def _init_paddle():
    global _paddle_ocr
    if _paddle_ocr is None:
        try:
            # Disable MKL-DNN/OneDNN to avoid fused_conv2d crashes on Windows
            import os
            os.environ["FLAGS_use_mkldnn"] = "0"
            os.environ["MKLDNN_CACHE_CAPACITY"] = "0"
            os.environ["FLAGS_use_onednn"] = "0"

            from paddleocr import PaddleOCR
            _paddle_ocr = PaddleOCR(
                use_angle_cls=True,
                lang="es",
                use_gpu=False,
                show_log=False,
                enable_mkldnn=False,
            )
            logger.info("PaddleOCR inicializado correctamente.")
        except Exception as e:
            logger.warning(f"PaddleOCR no disponible: {e}")
            _paddle_ocr = None
    return _paddle_ocr


def _init_tesseract():
    global _tesseract_disponible
    try:
        import pytesseract
        import os
        import platform

        # On Windows, set the explicit path if not already in PATH
        if platform.system() == "Windows":
            tesseract_paths = [
                r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
            ]
            for tp in tesseract_paths:
                if os.path.isfile(tp):
                    pytesseract.pytesseract.tesseract_cmd = tp
                    break

        pytesseract.get_tesseract_version()
        _tesseract_disponible = True
        logger.info("Tesseract inicializado correctamente.")
    except Exception as e:
        logger.warning(f"Tesseract no disponible: {e}")
        _tesseract_disponible = False
    return _tesseract_disponible


class ResultadoMotor:
    """Resultado crudo de un motor OCR."""
    def __init__(self, texto: str, confianza: float, motor: str, lineas: List[Tuple[str, float]]):
        self.texto = texto
        self.confianza = confianza
        self.motor = motor
        self.lineas = lineas  # [(texto_linea, confianza_linea), ...]


def ocr_con_paddle(imagen_np: np.ndarray) -> Optional[ResultadoMotor]:
    """
    Ejecuta PaddleOCR sobre un array numpy.
    Retorna ResultadoMotor o None si falla.
    """
    paddle = _init_paddle()
    if paddle is None:
        return None

    try:
        resultado = paddle.ocr(imagen_np, cls=True)
        if not resultado or not resultado[0]:
            return ResultadoMotor("", 0.0, "PaddleOCR", [])

        lineas = []
        textos = []
        confianzas = []

        for bloque in resultado:
            if bloque is None:
                continue
            for item in bloque:
                if item and len(item) >= 2:
                    texto_item = item[1][0] if item[1] else ""
                    conf_item = float(item[1][1]) if item[1] and len(item[1]) > 1 else 0.0
                    if texto_item.strip():
                        lineas.append((texto_item.strip(), conf_item))
                        textos.append(texto_item.strip())
                        confianzas.append(conf_item)

        texto_completo = "\n".join(textos)
        conf_global = float(np.mean(confianzas)) if confianzas else 0.0

        return ResultadoMotor(texto_completo, conf_global, "PaddleOCR", lineas)

    except Exception as e:
        logger.warning(f"PaddleOCR falló: {e}")
        return None


def ocr_con_tesseract(imagen_np: np.ndarray) -> Optional[ResultadoMotor]:
    """
    Ejecuta Tesseract OCR sobre un array numpy.
    Prueba múltiples PSM modes y toma el mejor resultado.
    Retorna ResultadoMotor o None si falla.
    """
    if not _init_tesseract():
        return None

    try:
        import pytesseract
        from pytesseract import Output

        img_pil = Image.fromarray(imagen_np)

        # Determine available languages
        lang = "spa+eng"
        try:
            pytesseract.image_to_string(img_pil, lang="spa+eng", config="--psm 3")
        except Exception:
            lang = "eng"

        # Try multiple PSM modes for best coverage
        psm_modes = [3, 6, 4]  # 3=fully automatic, 6=uniform block, 4=single column
        best_result = None
        best_text_len = 0

        for psm in psm_modes:
            try:
                config = f"--psm {psm} -l {lang}"
                data = pytesseract.image_to_data(img_pil, config=config, output_type=Output.DICT)

                lineas_dict: Dict[int, List[Tuple[str, float]]] = {}
                for i, palabra in enumerate(data["text"]):
                    conf = int(data["conf"][i])
                    num_linea = data["line_num"][i]
                    # Accept all words with conf > -1 (Tesseract uses -1 for empty entries)
                    if conf > -1 and palabra.strip():
                        if num_linea not in lineas_dict:
                            lineas_dict[num_linea] = []
                        lineas_dict[num_linea].append((palabra.strip(), max(conf, 1) / 100.0))

                resultado_lineas = []
                for num_linea in sorted(lineas_dict.keys()):
                    texto_linea = " ".join(p for p, _ in lineas_dict[num_linea])
                    conf_linea = float(np.mean([c for _, c in lineas_dict[num_linea]]))
                    resultado_lineas.append((texto_linea, conf_linea))

                texto_completo = "\n".join(t for t, _ in resultado_lineas)
                total_len = len(texto_completo)

                if total_len > best_text_len:
                    best_text_len = total_len
                    conf_global = float(np.mean([c for _, c in resultado_lineas])) if resultado_lineas else 0.0
                    best_result = ResultadoMotor(texto_completo, conf_global, "Tesseract", resultado_lineas)
                    logger.debug(f"Tesseract PSM {psm}: {total_len} chars, {len(resultado_lineas)} lines")

            except Exception as e:
                logger.debug(f"Tesseract PSM {psm} falló: {e}")
                continue

        return best_result

    except Exception as e:
        logger.warning(f"Tesseract falló: {e}")
        return None


def reconciliar_resultados(resultados: List[ResultadoMotor]) -> Tuple[str, float, str, List[Tuple[str, float]]]:
    """
    Reconcilia los resultados de múltiples motores/versiones.
    Selecciona el mejor resultado por confianza global.

    Retorna: (texto, confianza, motor, lineas)
    """
    validos = [r for r in resultados if r is not None and r.texto.strip()]
    if not validos:
        return "", 0.0, "ninguno", []

    # Ordenar por confianza descendente
    validos.sort(key=lambda r: r.confianza, reverse=True)

    mejor = validos[0]

    # Si hay múltiples, verificar divergencia
    if len(validos) > 1:
        segunda = validos[1]
        # Si la segunda tiene confianza similar, fusionar las líneas detectadas
        if abs(mejor.confianza - segunda.confianza) < 0.05:
            # Combinar textos para ampliar cobertura
            lineas_extra = [l for l in segunda.lineas if l[0] not in mejor.texto]
            if lineas_extra:
                texto_extra = "\n".join(t for t, _ in lineas_extra)
                texto_fusionado = mejor.texto + "\n" + texto_extra
                return texto_fusionado, mejor.confianza, f"{mejor.motor}+{segunda.motor}", mejor.lineas + lineas_extra

    return mejor.texto, mejor.confianza, mejor.motor, mejor.lineas


def ejecutar_ocr_sobre_versiones(
    versiones: List[np.ndarray],
) -> Tuple[str, float, str, List[Tuple[str, float]]]:
    """
    Ejecuta el stack OCR completo sobre todas las versiones preprocesadas.
    Estrategia de 5 capas:
      1. PaddleOCR sobre imagen original (v0)
      2. PaddleOCR sobre imagen mejorada (v1, v2)
      3. Tesseract sobre imagen binarizada (v3, v4)
      4. PaddleOCR sobre versión de baja calidad ampliada (v5 si existe)
      5. Reconciliación por confianza + cobertura
    """
    inicio = time.time()
    resultados = []

    for i, version in enumerate(versiones):
        logger.debug(f"OCR capa {i+1}/{len(versiones)}")

        # PaddleOCR para versiones 0-2 y 5
        if i in [0, 1, 2, 5]:
            r = ocr_con_paddle(version)
            if r:
                resultados.append(r)

        # Tesseract para versiones 3-4 (binarizadas)
        if i in [3, 4]:
            r = ocr_con_tesseract(version)
            if r:
                resultados.append(r)

        # Si ya tenemos resultado de alta confianza, podemos continuar igualmente
        # para asegurarnos de no perder nada (prioridad: precisión > velocidad)

    # Fallback: si nada funcionó, intentar Tesseract en versión original
    if not resultados and versiones:
        logger.warning("PaddleOCR sin resultados, usando Tesseract como fallback.")
        r = ocr_con_tesseract(versiones[0])
        if r:
            resultados.append(r)

    texto, confianza, motor, lineas = reconciliar_resultados(resultados)
    duracion = round(time.time() - inicio, 2)
    logger.debug(f"OCR completado en {duracion}s | motor: {motor} | confianza: {confianza:.2f}")

    return texto, confianza, motor, lineas
