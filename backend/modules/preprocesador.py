"""
Módulo de preprocesamiento de imagen.
========================================
Pipeline multi-paso para mejorar la legibilidad de capturas antes del OCR.
Genera múltiples versiones de cada imagen para maximizar la tasa de éxito.
"""

import cv2
import numpy as np
from pathlib import Path
from PIL import Image, ImageEnhance, ImageFilter
from typing import List, Tuple
from loguru import logger


def estimar_calidad(img: np.ndarray) -> str:
    """
    Estima la calidad de una imagen para ayudar a decidir el nivel
    de preprocesamiento necesario.
    Retorna: 'alta', 'media' o 'baja'
    """
    gris = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
    # Laplaciano: mide nitidez
    laplacian_var = cv2.Laplacian(gris, cv2.CV_64F).var()
    # Contraste aproximado
    contraste = float(gris.std())

    if laplacian_var > 200 and contraste > 40:
        return "alta"
    elif laplacian_var > 80 and contraste > 20:
        return "media"
    else:
        return "baja"


def corregir_orientacion(img: np.ndarray) -> np.ndarray:
    """
    Intenta corregir inclinaciones leves usando Hough lines.
    Solo corrige si el ángulo detectado es menor a 15°.
    """
    try:
        gris = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
        bordes = cv2.Canny(gris, 50, 150, apertureSize=3)
        lineas = cv2.HoughLinesP(bordes, 1, np.pi / 180, 100, minLineLength=100, maxLineGap=10)
        if lineas is None:
            return img

        angulos = []
        for linea in lineas:
            x1, y1, x2, y2 = linea[0]
            if x2 - x1 != 0:
                angulo = np.degrees(np.arctan2(y2 - y1, x2 - x1))
                if abs(angulo) < 15:
                    angulos.append(angulo)

        if not angulos:
            return img

        angulo_mediano = np.median(angulos)
        if abs(angulo_mediano) < 0.5:
            return img

        h, w = img.shape[:2]
        centro = (w // 2, h // 2)
        M = cv2.getRotationMatrix2D(centro, angulo_mediano, 1.0)
        rotada = cv2.warpAffine(img, M, (w, h), flags=cv2.INTER_CUBIC,
                                 borderMode=cv2.BORDER_REPLICATE)
        return rotada
    except Exception as e:
        logger.debug(f"No se pudo corregir orientación: {e}")
        return img


def recortar_contenido(img: np.ndarray) -> np.ndarray:
    """
    Detecta bordes y recorta el contenido útil eliminando márgenes vacíos.
    """
    try:
        gris = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img.copy()
        # Umbral para detectar contenido (no blanco)
        _, mascara = cv2.threshold(gris, 240, 255, cv2.THRESH_BINARY_INV)
        coords = cv2.findNonZero(mascara)
        if coords is None:
            return img
        x, y, w, h = cv2.boundingRect(coords)
        # Agregar margen de 5px
        margin = 5
        x = max(0, x - margin)
        y = max(0, y - margin)
        w = min(img.shape[1] - x, w + 2 * margin)
        h = min(img.shape[0] - y, h + 2 * margin)
        return img[y:y+h, x:x+w]
    except Exception as e:
        logger.debug(f"No se pudo recortar contenido: {e}")
        return img


def mejorar_contraste_clahe(gris: np.ndarray) -> np.ndarray:
    """Mejora el contraste local usando CLAHE."""
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    return clahe.apply(gris)


def reducir_ruido(gris: np.ndarray) -> np.ndarray:
    """Reduce el ruido de forma rápida usando Median Blur."""
    return cv2.medianBlur(gris, 3)


def enfocar(gris: np.ndarray) -> np.ndarray:
    """Aplica sharpening para mejorar la definición del texto."""
    kernel = np.array([[0, -1, 0],
                        [-1, 5, -1],
                        [0, -1, 0]])
    return cv2.filter2D(gris, -1, kernel)


def binarizar_adaptativo(gris: np.ndarray) -> np.ndarray:
    """Binarización adaptativa local (buena para texto sobre fondo variable)."""
    return cv2.adaptiveThreshold(
        gris, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        blockSize=11,
        C=2
    )


def binarizar_otsu(gris: np.ndarray) -> np.ndarray:
    """Binarización global con Otsu (buena para texto claro sobre fondo uniforme)."""
    _, binaria = cv2.threshold(gris, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return binaria


def reescalar_para_ocr(img: np.ndarray, min_alto: int = 800) -> np.ndarray:
    """
    Reescala la imagen si es demasiado pequeña para OCR.
    El mínimo recomendado es 300 DPI; para capturas de móvil esto suele ser suficiente.
    """
    h, w = img.shape[:2]
    if h < min_alto:
        factor = min_alto / h
        nuevo_w = int(w * factor)
        img = cv2.resize(img, (nuevo_w, min_alto), interpolation=cv2.INTER_CUBIC)
    return img


def preprocesar_imagen(ruta: Path) -> Tuple[List[np.ndarray], str]:
    """
    Pipeline completo de preprocesamiento.
    Genera múltiples versiones de la imagen para el ensemble OCR.

    Retorna:
        - Lista de imágenes procesadas (en orden de prioridad recomendada)
        - Calidad estimada de la imagen original ('alta', 'media', 'baja')
    """
    # Cargar imagen
    img_pil = Image.open(ruta).convert("RGB")
    img_np = np.array(img_pil)
    img_bgr = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)

    calidad = estimar_calidad(img_bgr)
    logger.debug(f"Calidad estimada de {ruta.name}: {calidad}")

    versiones = []

    # ── Versión 1: original reescalada ────────────────────────────────────────
    v1 = reescalar_para_ocr(img_bgr.copy())
    v1_corr = corregir_orientacion(v1)
    versiones.append(cv2.cvtColor(v1_corr, cv2.COLOR_BGR2RGB))

    # ── Versión 2: escala de grises + contraste CLAHE ─────────────────────────
    gris_base = cv2.cvtColor(v1_corr, cv2.COLOR_BGR2GRAY)
    gris_clahe = mejorar_contraste_clahe(gris_base)
    versiones.append(cv2.cvtColor(gris_clahe, cv2.COLOR_GRAY2RGB))

    # ── Versión 3: ruido reducido + enfoque ───────────────────────────────────
    gris_limpio = reducir_ruido(gris_clahe)
    gris_enfocado = enfocar(gris_limpio)
    versiones.append(cv2.cvtColor(gris_enfocado, cv2.COLOR_GRAY2RGB))

    # ── Versión 4: binarización adaptativa ───────────────────────────────────
    binaria_adapt = binarizar_adaptativo(gris_enfocado)
    versiones.append(cv2.cvtColor(binaria_adapt, cv2.COLOR_GRAY2RGB))

    # ── Versión 5: binarización Otsu (para fondos uniformes) ──────────────────
    binaria_otsu = binarizar_otsu(gris_enfocado)
    versiones.append(cv2.cvtColor(binaria_otsu, cv2.COLOR_GRAY2RGB))

    # ── Versión 6 (solo si calidad baja): recorte + super-resolución simple ───
    if calidad == "baja":
        recortada = recortar_contenido(v1_corr)
        if recortada.shape[0] > 50:
            # Escalar x2 para texto muy pequeño
            h, w = recortada.shape[:2]
            grande = cv2.resize(recortada, (w * 2, h * 2), interpolation=cv2.INTER_CUBIC)
            gris_grande = cv2.cvtColor(grande, cv2.COLOR_BGR2GRAY)
            clahe_g = mejorar_contraste_clahe(gris_grande)
            versiones.append(cv2.cvtColor(clahe_g, cv2.COLOR_GRAY2RGB))

    return versiones, calidad


def imagen_a_pil(img_np: np.ndarray) -> Image.Image:
    """Convierte array numpy a PIL Image."""
    return Image.fromarray(img_np.astype(np.uint8))
