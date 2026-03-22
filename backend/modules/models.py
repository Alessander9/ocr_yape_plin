"""
Modelos de datos del sistema OCR.
Definen la estructura de entrada y salida de cada procesamiento.
"""

from __future__ import annotations
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum


class TipoApp(str, Enum):
    YAPE = "YAPE"
    PLIN = "PLIN"
    DESCONOCIDO = "DESCONOCIDO"


class NivelConfianza(str, Enum):
    ALTA = "alta"       # >= 0.90
    MEDIA = "media"     # 0.75 - 0.89
    BAJA = "baja"       # < 0.75


class EstadoOperacion(str, Enum):
    EXITOSA = "EXITOSA"
    FALLIDA = "FALLIDA"
    DUDOSO = "DUDOSO"
    DESCONOCIDO = "DESCONOCIDO"


class ConfianzaPorCampo(BaseModel):
    monto: Optional[float] = None
    moneda: Optional[float] = None
    fecha: Optional[float] = None
    hora: Optional[float] = None
    nombre_emisor_o_pagador: Optional[float] = None
    nombre_receptor_o_destinatario: Optional[float] = None
    numero_celular_relacionado: Optional[float] = None
    banco_o_billetera: Optional[float] = None
    numero_operacion: Optional[float] = None
    descripcion: Optional[float] = None
    estado_operacion: Optional[float] = None
    tipo_app: Optional[float] = None


class ResultadoOCR(BaseModel):
    """Resultado completo del procesamiento OCR de un archivo."""

    # ── Identificación ────────────────────────────────────────────────────────
    archivo: str
    extension_archivo: str
    hash_imagen: Optional[str] = None
    posible_duplicado: bool = False

    # ── Clasificación ─────────────────────────────────────────────────────────
    tipo_app: Optional[TipoApp] = None
    operacion_exitosa: Optional[str] = None   # "sí" / "no" / "dudoso"
    estado_operacion: Optional[str] = None

    # ── Datos económicos ──────────────────────────────────────────────────────
    monto: Optional[float] = None
    moneda: Optional[str] = "PEN"

    # ── Fecha y hora ──────────────────────────────────────────────────────────
    fecha: Optional[str] = None               # YYYY-MM-DD
    hora: Optional[str] = None                # HH:mm:ss

    # ── Personas ──────────────────────────────────────────────────────────────
    nombre_emisor_o_pagador: Optional[str] = None
    nombre_receptor_o_destinatario: Optional[str] = None
    numero_celular_relacionado: Optional[str] = None

    # ── Transacción ───────────────────────────────────────────────────────────
    banco_o_billetera: Optional[str] = None
    numero_operacion: Optional[str] = None
    descripcion: Optional[str] = None

    # ── Texto y calidad ───────────────────────────────────────────────────────
    texto_completo_detectado: Optional[str] = None
    calidad_imagen_estimada: Optional[str] = None  # "alta" / "media" / "baja"
    motor_ocr_primario: Optional[str] = None

    # ── Confianza ─────────────────────────────────────────────────────────────
    confianza_global: Optional[float] = None
    nivel_confianza: Optional[NivelConfianza] = None
    confianza_por_campo: Optional[ConfianzaPorCampo] = None

    # ── Auditoría ─────────────────────────────────────────────────────────────
    campos_dudosos: List[str] = Field(default_factory=list)
    observaciones: List[str] = Field(default_factory=list)
    tiempo_procesamiento_seg: Optional[float] = None
    error: Optional[str] = None

    # ── Datos crudos para auditoría ───────────────────────────────────────────
    candidatos_alternativos: Optional[Dict[str, Any]] = None


class ResumenLote(BaseModel):
    """Resumen de un lote de archivos procesados."""
    total_archivos: int
    exitosos: int
    con_dudas: int
    errores: int
    capturas_yape: int
    capturas_plin: int
    capturas_desconocidas: int
    suma_montos: float
    promedio_confianza: float
    posibles_duplicados: int
    resultados: List[ResultadoOCR]
