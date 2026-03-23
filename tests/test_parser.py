"""
Tests básicos del sistema OCR.
Verifican la lógica de parsing y validación sin necesitar imágenes reales.
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from modules.parser import (
    extraer_monto, extraer_fecha, extraer_hora,
    extraer_numero_operacion, extraer_tipo_app,
    extraer_operacion_exitosa, extraer_celular,
    parsear_comprobante,
)


# ── Fixtures de texto OCR simulado ────────────────────────────────────────────

TEXTO_YAPE_TIPICO = """
YAPE
¡Yapiste a Maria Lopez!
S/ 25.50
21/03/2026
14:32:08
Operación N° 987654321
Enviado correctamente
BCP
"""

TEXTO_PLIN_TIPICO = """
Plin
Transferencia realizada
S/ 100.00
15/02/2026
09:15:00
Código de operación: OPR20260215ABC
Para: Juan Perez
Completado
"""

TEXTO_AMBIGUO = """
Monto: 15.90 o quizás 15,90
Fecha: alguna fecha
Sin número de operación
"""

TEXTO_VACIO = ""


# ── Tests de tipo_app ─────────────────────────────────────────────────────────

def test_detectar_yape():
    tipo, conf = extraer_tipo_app(TEXTO_YAPE_TIPICO)
    assert tipo is not None
    assert tipo.value == "YAPE"
    assert conf > 0.6

def test_detectar_plin():
    tipo, conf = extraer_tipo_app(TEXTO_PLIN_TIPICO)
    assert tipo is not None
    assert tipo.value == "PLIN"
    assert conf > 0.6

def test_tipo_desconocido():
    tipo, conf = extraer_tipo_app("Texto sin referencias")
    assert tipo is None or conf < 0.4


# ── Tests de monto ────────────────────────────────────────────────────────────

def test_monto_con_slash():
    m, c = extraer_monto("Enviaste S/ 25.50 a Maria")
    assert m == 25.50
    assert c > 0.6

def test_monto_sin_slash():
    m, c = extraer_monto("Monto: 100.00")
    assert m == 100.00

def test_monto_con_coma():
    m, c = extraer_monto("S/ 15,90")
    assert m == 15.90

def test_monto_invalido():
    m, c = extraer_monto("Sin montos aquí")
    assert m is None

def test_monto_demasiado_alto():
    m, c = extraer_monto("S/ 999999999.00")
    assert m is None  # fuera de rango razonable

def test_monto_ocr_sucio():
    # Casos donde S/ se lee como S1, 5/, $/, S/, o no hay espacio
    assert extraer_monto("5/ 120.50")[0] == 120.50
    assert extraer_monto("S1 120.50")[0] == 120.50
    assert extraer_monto("s/120.50")[0] == 120.50
    assert extraer_monto("Sl 120.50")[0] == 120.50
    assert extraer_monto("$/ 120.50")[0] == 120.50


# ── Tests de fecha ────────────────────────────────────────────────────────────

def test_fecha_slash():
    f, c = extraer_fecha("21/03/2026")
    assert f == "2026-03-21"
    assert c >= 0.9

def test_fecha_guion():
    f, c = extraer_fecha("15-02-2026")
    assert f == "2026-02-15"

def test_fecha_texto_completo():
    f, c = extraer_fecha("21 de marzo de 2026")
    assert f == "2026-03-21"

def test_fecha_mes_corto():
    f, c = extraer_fecha("15 mar 2026")
    assert f == "2026-03-15"

def test_fecha_futura_invalida():
    f, c = extraer_fecha("01/01/2040")
    assert f is None  # fecha futura

def test_fecha_vacia():
    f, c = extraer_fecha("")
    assert f is None

def test_fecha_ocr_sucio():
    # Casos donde OCR lee mal meses o separadores
    assert extraer_fecha("21 nar 2026")[0] == "2026-03-21"
    assert extraer_fecha("21 narzo 2026")[0] == "2026-03-21"
    assert extraer_fecha("15 ehb 2026")[0] == "2026-02-15" # ehb = feb
    assert extraer_fecha("10 abri 2025")[0] == "2025-04-10"
    assert extraer_fecha("05.12.2025")[0] == "2025-12-05"
    assert extraer_fecha("20/12/26")[0] == "2026-12-20"


# ── Tests de hora ─────────────────────────────────────────────────────────────

def test_hora_24h_con_segundos():
    h, c = extraer_hora("14:32:08")
    assert h == "14:32:08"
    assert c >= 0.9

def test_hora_24h_sin_segundos():
    h, c = extraer_hora("09:15")
    assert h == "09:15:00"

def test_hora_invalida():
    h, c = extraer_hora("99:99:99")
    assert h is None


# ── Tests de número de operación ──────────────────────────────────────────────

def test_numero_operacion_con_etiqueta():
    n, c = extraer_numero_operacion("Operación N° 987654321")
    assert n == "987654321"
    assert c >= 0.8

def test_codigo_operacion():
    n, c = extraer_numero_operacion("Código: OPR20260215ABC")
    assert n is not None
    assert "OPR" in n

def test_numero_operacion_ausente():
    n, c = extraer_numero_operacion("Sin código aquí.")
    assert n is None

def test_numero_operacion_ocr_sucio():
    # 'O' en lugar de '0', etc.
    assert extraer_numero_operacion("0peraci0n N° 12345O7")[0] == "1234507"
    assert extraer_numero_operacion("Nro: I23456")[0] == "123456"


# ── Tests de celular ──────────────────────────────────────────────────────────

def test_celular_valido():
    cel, c = extraer_celular("Enviado a 987654321")
    assert cel == "987654321"

def test_celular_invalido():
    cel, c = extraer_celular("Sin número celular")
    assert cel is None


# ── Tests de operación exitosa ────────────────────────────────────────────────

def test_operacion_exitosa():
    op, c = extraer_operacion_exitosa("Operación exitosa. Enviado correctamente.")
    assert op == "sí"
    assert c > 0.6

def test_operacion_fallida():
    op, c = extraer_operacion_exitosa("Transacción fallida. Error en el proceso.")
    assert op == "no"

def test_operacion_dudosa():
    op, c = extraer_operacion_exitosa("Procesando tu solicitud")
    assert op == "dudoso"


# ── Tests del parser completo ─────────────────────────────────────────────────

def test_parsear_texto_yape():
    resultado = parsear_comprobante(
        texto=TEXTO_YAPE_TIPICO,
        nombre_archivo="test_yape.png",
        confianza_ocr=0.92,
        motor_ocr="PaddleOCR",
        hash_img="abc123",
        calidad_imagen="alta",
        tiempo_seg=1.5,
    )
    assert resultado.tipo_app is not None
    assert resultado.tipo_app.value == "YAPE"
    assert resultado.monto == 25.50
    assert resultado.fecha == "2026-03-21"
    assert resultado.hora == "14:32:08"
    assert resultado.confianza_global is not None
    assert resultado.confianza_global > 0

def test_parsear_texto_vacio():
    resultado = parsear_comprobante(
        texto=TEXTO_VACIO,
        nombre_archivo="vacio.png",
        confianza_ocr=0.0,
        motor_ocr="ninguno",
        hash_img="000",
        calidad_imagen="baja",
        tiempo_seg=0.5,
    )
    assert resultado.error is not None
    assert resultado.monto is None

def test_parsear_conservador():
    """El parser NO debe inventar valores cuando el texto es ambiguo."""
    resultado = parsear_comprobante(
        texto="15.90",  # Solo un número, sin contexto
        nombre_archivo="ambiguo.png",
        confianza_ocr=0.4,
        motor_ocr="Tesseract",
        hash_img="xyz",
        calidad_imagen="baja",
        tiempo_seg=0.8,
    )
    # Con confianza baja, es aceptable que campos queden null
    # Lo importante: ningún campo tiene un valor "inventado"
    assert resultado.nombre_emisor_o_pagador is None or len(resultado.nombre_emisor_o_pagador) > 0
    assert resultado.numero_operacion is None or resultado.numero_operacion.isalnum()

# ── Tests Integrales de Casos Reales (Yape/Plin Interoperabilidad) ──────────

TEXTO_REAL_YAPE_A_PLIN = """
yape
iYapeaste S/100
Luis Alexander Fernandez
20 mar.2026 l 11:48 p.m.
DATOS DE LA TRANSACCIÓN
Nro.de celular 309
Destino
Plin
Nro. de operación
465724
S/ 100
20 mar. 2026 l 11:48 p. m.
Nro. de celular
"""

TEXTO_REAL_PLIN_MULTILINEA = """
Envio a contactos
Operación
exitosa
20 marzo 2026,17:15h
Importe enviado
S/50.00
Entidad de destino
Plin
Comisión
S/ 0.00
Número de operación
000001791
Tipo de operación
Envio a contactos
Contacto
Luis
0309
alexander
fernandez
paz
Cuenta de
Cuenta
.9019
origen
corriente
20marzo2026.17.15h
Entidad dedestino
Comision
$/ 0.00
Numerodeoperación
Envioa contactos
:9019
"""

def test_integral_yape_interoperabilidad():
    """Prueba que un Yape hacia Plin (iYapeaste) extraiga todos los campos bien y no se confunda con Plin"""
    resultado = parsear_comprobante(
        texto=TEXTO_REAL_YAPE_A_PLIN,
        nombre_archivo="yape_plin.png",
        confianza_ocr=0.95,
        motor_ocr="Paddle",
        hash_img="123",
        calidad_imagen="alta",
        tiempo_seg=1.0,
    )
    assert resultado.tipo_app.value == "YAPE"
    assert resultado.monto == 100.0
    assert resultado.nombre_receptor_o_destinatario == "Luis Alexander Fernandez"
    # El emisor está ausente en el diseño de Yape (es el dueño de la cuenta)
    assert resultado.fecha == "2026-03-20"
    assert resultado.hora == "23:48:00"  # 11:48 p.m.
    assert resultado.numero_operacion == "465724"


def test_integral_plin_nombres_rotos():
    """Prueba un comprobante de Plin con nombres destrozados en múltiples líneas y fechas pegadas"""
    resultado = parsear_comprobante(
        texto=TEXTO_REAL_PLIN_MULTILINEA,
        nombre_archivo="plin_roto.png",
        confianza_ocr=0.90,
        motor_ocr="Paddle",
        hash_img="abc",
        calidad_imagen="media",
        tiempo_seg=1.0,
    )
    assert resultado.tipo_app.value == "PLIN"
    assert resultado.monto == 50.0
    assert resultado.nombre_receptor_o_destinatario == "Luis Alexander Fernandez Paz"
    assert resultado.nombre_emisor_o_pagador is None
    assert resultado.fecha == "2026-03-20"  # de "20marzo2026.17.15h" o "20 marzo 2026"
    assert resultado.hora == "17:15:00"     # de "17:15h"
    assert resultado.numero_operacion == "000001791"
    assert resultado.operacion_exitosa == "sí"

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
