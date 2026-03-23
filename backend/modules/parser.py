"""
Parser semántico de comprobantes YAPE / PLIN.
==============================================
Extrae y valida cada campo usando reglas, contexto y puntuación de candidatos.
PRINCIPIO: null > campo inventado.
"""

import re
import hashlib
from typing import Optional, Tuple, List, Dict, Any
from datetime import datetime
from dateutil import parser as dateutil_parser
from loguru import logger

from modules.models import (
    TipoApp, EstadoOperacion, NivelConfianza,
    ResultadoOCR, ConfianzaPorCampo,
)


# ──────────────────────────────────────────────────────────────────────────────
# Constantes y patrones
# ──────────────────────────────────────────────────────────────────────────────

UMBRAL_CONFIANZA_CAMPO = 0.0    # Aceptar todos los campos sin filtrar por confianza

PALABRAS_YAPE = [
    r"\byape\b", r"[i¡!]?yapeast\w*", r"\byapeo\b", r"\bpor yape\b",
    r"\bvía yape\b", r"\byapear\b", r"\bcon yape\b",
]
PALABRAS_PLIN = [
    r"\bplin\b", r"\bplineaste\b", r"\bpago plin\b",
    r"\btransferido por plin\b", r"\bvía plin\b",
]

PALABRAS_EXITOSA = [
    r"operaci[oó]n\s+exitosa", r"pago\s+realizado", r"enviado\s+correctamente",
    r"transferencia\s+realizada", r"completado", r"exitoso",
    r"confirmado", r"transfer\s+exitosa", r"transacci[oó]n\s+exitosa",
    r"se\s+envi[oó]", r"pagaste", r"yapeast[e]", r"plineast[e]",
]
PALABRAS_FALLIDA = [
    r"fallida", r"rechazada", r"error", r"no\s+procesada",
    r"operaci[oó]n\s+no", r"transacci[oó]n\s+no",
]

CONTEXTO_MONTO = [
    r"monto", r"enviaste", r"recibiste", r"pago", r"transferencia",
    r"transacci[oó]n", r"operaci[oó]n", r"importe", r"total",
    r"pagaste", r"te enviaron", r"te pag[oó]",
    r"yapeaste", r"plineaste", r"yape", r"plin",
    r"s/", r"soles", r"pen",
]

CONTEXTO_OPERACION = [
    r"operaci[oó]n", r"c[oó]digo", r"constancia", r"transacci[oó]n",
    r"id", r"nro", r"n[uú]mero", r"referencia",
]

BANCOS = [
    "BCP", "BBVA", "Interbank", "Scotiabank", "Banbif",
    "Banco de la Nación", "Mibanco", "Caja Piura",
    "Caja Huancayo", "Caja Arequipa",
]

TEXTOS_INTERFAZ = {
    # Palabras que NO son nombres de personas
    "enviar", "recibir", "pagar", "monto", "fecha", "hora", "operación",
    "código", "número", "estado", "descripción", "motivo", "concepto",
    "transferencia", "confirmación", "ok", "cancelar", "volver", "inicio",
    "continuar", "aceptar", "compartir", "yape", "plin", "billetera",
    "cuenta", "transacción", "banco", "constancia", "pago",
}


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _flags():
    return re.IGNORECASE | re.UNICODE


def _buscar(patron: str, texto: str) -> Optional[re.Match]:
    try:
        return re.search(patron, texto, _flags())
    except Exception:
        return None


def _normalizar_texto(texto: str) -> str:
    """Limpia caracteres basura pero preserva letras con tilde y simbolos utiles como N° ."""
    texto = re.sub(r"[^\w\s\./,:S/\-$#°º]", " ", texto, flags=re.UNICODE)
    texto = re.sub(r"\s{2,}", " ", texto)
    return texto.strip()


def _lineas(texto: str) -> List[str]:
    return [l.strip() for l in texto.splitlines() if l.strip()]


def _contexto_cercano(texto: str, patron_valor: str, palabras_contexto: List[str],
                       ventana: int = 60) -> float:
    """
    Puntúa un candidato según qué tan cerca está de palabras de contexto.
    Retorna un score adicional de 0.0 a 0.3.
    """
    matches = list(re.finditer(patron_valor, texto, _flags()))
    if not matches:
        return 0.0

    mejor = 0.0
    for match in matches:
        inicio = max(0, match.start() - ventana)
        fin = min(len(texto), match.end() + ventana)
        ventana_texto = texto[inicio:fin].lower()
        for ctx in palabras_contexto:
            if re.search(ctx, ventana_texto, _flags()):
                mejor = max(mejor, 0.3)
                break

    return mejor


# ──────────────────────────────────────────────────────────────────────────────
# Extractores individuales
# ──────────────────────────────────────────────────────────────────────────────

def extraer_tipo_app(texto: str) -> Tuple[Optional[str], float]:
    texto_l = texto.lower()

    score_yape = sum(1 for p in PALABRAS_YAPE if re.search(p, texto_l, _flags()))
    score_plin = sum(1 for p in PALABRAS_PLIN if re.search(p, texto_l, _flags()))

    if score_yape == 0 and score_plin == 0:
        return None, 0.0

    if score_yape > score_plin:
        confianza = min(0.5 + score_yape * 0.2, 1.0)
        return TipoApp.YAPE, confianza
    elif score_plin > score_yape:
        confianza = min(0.5 + score_plin * 0.2, 1.0)
        return TipoApp.PLIN, confianza
    else:
        return TipoApp.DESCONOCIDO, 0.4


def extraer_operacion_exitosa(texto: str) -> Tuple[Optional[str], float]:
    texto_l = texto.lower()

    matches_exito = sum(1 for p in PALABRAS_EXITOSA if re.search(p, texto_l, _flags()))
    matches_falla = sum(1 for p in PALABRAS_FALLIDA if re.search(p, texto_l, _flags()))

    if matches_exito > 0 and matches_falla == 0:
        return "sí", min(0.6 + matches_exito * 0.1, 1.0)
    elif matches_falla > 0:
        return "no", min(0.6 + matches_falla * 0.1, 1.0)
    else:
        return "dudoso", 0.4


def extraer_monto(texto: str) -> Tuple[Optional[float], float]:
    """
    Extrae el monto principal usando múltiples patrones y contexto semántico.
    Retorna (monto, confianza) o (None, 0.0).
    """
    # Patrones ordenados por especificidad (Maneja orden normal y orden inverso cuando el OCR rompe líneas)
    patrones = [
        (r"(?:S/|S1|5/|\$/)\.?\s*[\r\n]*\s*(\d{1,6}(?:[.,]\d{1,2})?)", True), # Normal: S/ 150.50 o S/ \n 150
        (r"\b(\d{1,6}(?:[.,]\d{1,2})?)\s*[\r\n]+\s*(?:S/|S1|5/|\$/)", True), # Inverso (frecuente en fallos OCR): 25 \n S/
        (r"\b(\d{1,6}[.,]\d{2})\b", True),                   # 150.50 / 150,50
        (r"\b(?:\$|S)\s*/\s*(\d{1,6})\b", True),             # S / 150
        (r"\b(\d{1,6}(?:\.\d{1,2})?)\b", False),             # bare number: 64 or 64.50
    ]

    candidatos = []  # [(valor, confianza)]

    for patron_info in patrones:
        patron, es_especifico = patron_info
        for match in re.finditer(patron, texto, _flags()):
            raw = match.group(1).replace(",", ".")
            try:
                valor = float(raw)
                if valor <= 0 or valor > 500000:
                    continue
                # Skip year-like numbers (2015-2030)
                if not es_especifico and 2015 <= valor <= 2030:
                    continue
                # Skip if it looks like part of a date pattern (e.g. "20 mar")
                if not es_especifico:
                    pos = match.start()
                    after_text = texto[match.end():match.end()+15].strip().lower()
                    # Skip if followed by month-like word
                    if re.match(r"(ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic|de\s)", after_text):
                        if valor <= 31:
                            continue
                # Puntuar por contexto
                score_base = 0.7 if es_especifico else 0.4
                bonus_ctx = _contexto_cercano(texto, re.escape(match.group(0)), CONTEXTO_MONTO)
                # Penalizar montos muy redondos sin contexto (ej. 1000.00 sospechoso)
                if valor == int(valor) and valor >= 1000 and bonus_ctx < 0.1:
                    score_base = 0.5 if es_especifico else 0.3
                candidatos.append((valor, min(score_base + bonus_ctx, 1.0)))
            except ValueError:
                continue

    if not candidatos:
        return None, 0.0

    # Elegir el candidato con mayor confianza
    candidatos.sort(key=lambda x: x[1], reverse=True)
    mejor_valor, mejor_conf = candidatos[0]

    # Always return the best candidate regardless of confidence
    return mejor_valor, mejor_conf


def extraer_fecha(texto: str) -> Tuple[Optional[str], float]:
    """
    Detecta múltiples formatos de fecha y normaliza a YYYY-MM-DD.
    """
    patrones = [
        (r"\b(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})\b", "dmy"),
        (r"\b(\d{4})[/\-](\d{1,2})[/\-](\d{1,2})\b", "ymd"),
        (r"\b(\d{1,2})\s*de\s*(\w+)\s*(?:de\s*)?(\d{4})\b", "texto"),
        (r"\b(\d{1,2})\s*(\w{3,})\.?\s*(\d{4})\b", "texto"),
    ]

    MESES = {
        "ene": 1, "enero": 1, "feb": 2, "febrero": 2, "ehb": 2,
        "mar": 3, "marzo": 3, "nar": 3, "narzo": 3, "abr": 4, "abril": 4, "abri": 4,
        "may": 5, "mayo": 5, "jun": 6, "junio": 6,
        "jul": 7, "julio": 7, "ago": 8, "agosto": 8, "ag0": 8,
        "sep": 9, "septiembre": 9, "set": 9, "oct": 10, "octubre": 10, "0ct": 10,
        "nov": 11, "noviembre": 11, "dic": 12, "diciembre": 12,
    }

    candidatos = []

    # Pre-procesamiento de fechas con separadores punteados (05.12.2026 -> 05/12/2026)
    texto_fecha = re.sub(r"(\d{1,2})\.(\d{1,2})\.(\d{2,4})", r"\1/\2/\3", texto)

    for patron, fmt in patrones:
        for match in re.finditer(patron, texto_fecha, _flags()):
            try:
                if fmt == "dmy":
                    dia, mes, anio = int(match.group(1)), int(match.group(2)), int(match.group(3))
                elif fmt == "ymd":
                    anio, mes, dia = int(match.group(1)), int(match.group(2)), int(match.group(3))
                elif fmt == "texto":
                    dia = int(match.group(1))
                    mes_str = match.group(2).lower().rstrip('.')[:5]
                    # Buscar coincidencia exacta o los primeros 3 caracteres
                    mes = MESES.get(mes_str) or MESES.get(mes_str[:3])
                    if mes is None:
                        continue
                    anio = int(match.group(3))
                else:
                    continue
                
                # Arreglar años de 2 dígitos (ej. 26 -> 2026)
                if anio < 100:
                    anio += 2000

                fecha = datetime(anio, mes, dia)
                # Sanidad: no fechas futuras lejanas ni muy antiguas
                ahora = datetime.now()
                if fecha.year < 2015 or fecha > ahora:
                    continue
                candidatos.append((fecha.strftime("%Y-%m-%d"), 0.90))
            except (ValueError, TypeError):
                continue

    # Intentar dateutil como último recurso
    if not candidatos:
        try:
            fecha = dateutil_parser.parse(texto, fuzzy=True, dayfirst=True)
            if 2015 <= fecha.year <= datetime.now().year + 1:
                candidatos.append((fecha.strftime("%Y-%m-%d"), 0.65))
        except Exception:
            pass

    if not candidatos:
        return None, 0.0

    candidatos.sort(key=lambda x: x[1], reverse=True)
    mejor_fecha, mejor_conf = candidatos[0]
    if mejor_conf < UMBRAL_CONFIANZA_CAMPO:
        return None, mejor_conf
    return mejor_fecha, mejor_conf


def extraer_hora(texto: str) -> Tuple[Optional[str], float]:
    """
    Detecta horas en formatos 24h o 12h y normaliza a HH:mm:ss.
    """
    patrones_24h = [
        r"\b(\d{1,2}):(\d{2}):(\d{2})\b",
        r"\b(\d{1,2})[:.](\d{2})h?\b",
    ]
    patrones_12h = [
        r"\b(\d{1,2}):(\d{2})(?::(\d{2}))?\s*([ap]\.?\s*m\.?)\b",
    ]

    candidatos = []

    for patron in patrones_24h:
        for match in re.finditer(patron, texto, _flags()):
            try:
                h = int(match.group(1))
                m = int(match.group(2))
                s = int(match.group(3)) if match.lastindex >= 3 and match.group(3) else 0
                if 0 <= h <= 23 and 0 <= m <= 59 and 0 <= s <= 59:
                    tiene_segundos = match.lastindex >= 3 and match.group(3) is not None
                    candidatos.append((f"{h:02d}:{m:02d}:{s:02d}", 0.90 if tiene_segundos else 0.80))
            except (ValueError, TypeError):
                continue

    for patron in patrones_12h:
        for match in re.finditer(patron, texto, _flags()):
            try:
                h = int(match.group(1))
                m = int(match.group(2))
                s = int(match.group(3)) if match.group(3) else 0
                ampm = match.group(4).lower().replace(".", "")
                if ampm == "pm" and h != 12:
                    h += 12
                elif ampm == "am" and h == 12:
                    h = 0
                if 0 <= h <= 23 and 0 <= m <= 59:
                    candidatos.append((f"{h:02d}:{m:02d}:{s:02d}", 0.85))
            except (ValueError, TypeError):
                continue

    if not candidatos:
        return None, 0.0
    candidatos.sort(key=lambda x: x[1], reverse=True)
    h, c = candidatos[0]
    return (h, c) if c >= UMBRAL_CONFIANZA_CAMPO else (None, c)


def extraer_numero_operacion(texto: str) -> Tuple[Optional[str], float]:
    """
    Extrae el código/número de operación usando contexto semántico.
    Limpia errores clásicos de OCR (ej. O por 0, I por 1).
    """
    # Secuencias alfanuméricas de 6-20 caracteres tolerantes a ruido en la etiqueta
    patrones = [
        r"(?:operaci.?n|c.?digo|constancia|id|nro|n[uú]mero|referencia)[:\s#N°º]*([A-Z0-9\-OIlS]{6,20})",
        r"(?:transacci.?n|cod)[:\s]*([A-Z0-9\-OIlS]{6,20})",
        r"N[°ºde\s]*([0-9OIlS]{6,20})",   # formato "N° 987654321" o "Nde 12345O7"
        r"\b([0-9]{8,20})\b",        # número largo sin contexto (menor confianza, estricto a números)
    ]

    candidatos = []
    
    # Mapeo de errores OCR comunes para códigos de operación numéricos
    def _limpiar_ocr_typos(valor: str) -> str:
        # Solo aplicamos esto si el valor parece ser mayormente numérico
        letras = sum(c.isalpha() for c in valor)
        if letras <= 3:  # Probable error OCR
            reemplazos = {"O": "0", "I": "1", "l": "1", "S": "5", "B": "8", "Z": "2"}
            for err, corr in reemplazos.items():
                valor = valor.replace(err, corr).replace(err.lower(), corr)
        return valor

    for i, patron in enumerate(patrones):
        for match in re.finditer(patron, texto, _flags()):
            valor = match.group(1).strip()
            # Rechazar palabras comunes que se captan como código
            if valor.lower() in ["exitosa", "fallida", "contacto", "yape", "plin", "operaci0n"]:
                continue
            # Rechazar fechas
            if re.match(r"\d{1,2}[/\-]\d{1,2}[/\-]\d{4}", valor):
                continue
            
            # Limpiar OCR typos del código candidato antes de evaluarlo final
            valor_limpio = _limpiar_ocr_typos(valor)
            
            # Solo rechazar número 9 dígitos como teléfono si NO tiene contexto semántico
            if i >= 3 and re.match(r"^\d{9}$", valor_limpio):
                continue
                
            # Confianza según nivel de contexto del patrón
            if i == 0:
                conf = 0.88
            elif i == 1:
                conf = 0.85
            elif i == 2:
                conf = 0.82
            else:
                conf = 0.60
            candidatos.append((valor_limpio, conf))

    if not candidatos:
        return None, 0.0

    candidatos.sort(key=lambda x: x[1], reverse=True)
    v, c = candidatos[0]
    return (v, c) if c >= UMBRAL_CONFIANZA_CAMPO else (None, c)


def extraer_celular(texto: str) -> Tuple[Optional[str], float]:
    """
    Extrae número de celular peruano (9 dígitos empezando en 9).
    """
    matches = re.findall(r"\b(9\d{8})\b", texto)
    if not matches:
        return None, 0.0
    # El más frecuente probablemente sea el relevante
    return matches[0], 0.85


def extraer_banco(texto: str) -> Tuple[Optional[str], float]:
    """Detecta banco o billetera mencionado en el texto."""
    for banco in BANCOS:
        if re.search(re.escape(banco), texto, _flags()):
            return banco, 0.90
    # Patrones genéricos
    for patron in [r"\bBCP\b", r"\bBBVA\b", r"\bInterbank\b", r"\bScotiabank\b"]:
        if re.search(patron, texto, _flags()):
            return patron.replace(r"\b", ""), 0.88
    return None, 0.0


def extraer_nombres(texto: str) -> Tuple[Optional[str], float, Optional[str], float]:
    """
    Extrae emisor y receptor del texto.
    Heurística mejorada para YAPE y PLIN con patrones específicos.
    Retorna: (emisor, conf_emisor, receptor, conf_receptor)
    """
    lineas = _lineas(texto)
    emisor = None
    conf_e = 0.0
    receptor = None
    conf_r = 0.0

    def _es_nombre_valido(nombre: str) -> bool:
        """Verifica que un candidato sea realmente un nombre de persona."""
        if not nombre or len(nombre) < 2 or len(nombre) > 80:
            return False
        nombre_l = nombre.lower().strip()
        # Filtrar palabras de interfaz
        if nombre_l in TEXTOS_INTERFAZ:
            return False
        # Filtrar posibles montos basura cortos como S/ solos
        if nombre.upper() in ["S/", "S1", "5/", "$/", "S/."]:
            return False
        # Filtrar si parece un monto (S/100, 100.00, etc.)
        if re.match(r"^S/\s*\d", nombre, _flags()):
            return False
        if re.match(r"^\d+([.,]\d+)?$", nombre):
            return False
        # Filtrar basura técnica del OCR
        if re.search(r"operaci.?n", nombre_l) or re.search(r"celular", nombre_l):
            return False
        # Filtrar si parece una fecha/hora agrupada (ej. 20marzo2026, 17:15h)
        if re.match(r"^\d{1,2}\s*(?:de\s*)?[a-zA-Z]{3,}\s*(?:de\s*)?\d{4}.*$", nombre) or re.match(r"\d{1,2}[:.]\d{2}", nombre):
            return False
        # Filtrar etiquetas de UI comunes en comprobantes
        etiquetas = [
            "operaci", "exitosa", "fallida", "contacto", "importe",
            "enviado", "comisi", "entidad", "destino", "origen",
            "cuenta", "corriente", "ahorro", "tipo", "nro", "n°",
            "numero", "celular", "datos", "transacci", "plin", "yape",
            "banco", "billetera", "fecha", "hora", "estado", "monto",
        ]
        for etiq in etiquetas:
            if nombre_l == etiq or nombre_l.startswith(etiq):
                return False
        # Requiere al menos una letra (rechaza ":9019", "---", etc)
        if not re.search(r"[a-zA-Z]", nombre):
            return False
        return True

    def _limpiar_nombre(nombre: str) -> str:
        """Limpia un nombre extraído."""
        nombre = nombre.strip()
        # Quitar puntuación final
        nombre = re.sub(r"[.!?¡¿,;:]+$", "", nombre).strip()
        # Quitar prefijo S/ si quedó pegado
        nombre = re.sub(r"^S/\s*\d+[.,]?\d*\s*", "", nombre).strip()
        return nombre

    # Candidatos a receptor (para consolidar)
    candidatos = []

    # ── Patrones genéricos para receptor (antes de Yape/Plin específicos) ───
    for i, l in enumerate(lineas):
        l_l = l.lower()
        if "destino" in l_l or "enviado a" in l_l or "para:" in l_l or "contacto" in l_l:
            cand = l.split(":")[-1].strip()
            if not cand and i + 1 < len(lineas):
                cand = lineas[i+1].strip()
            # A veces Plin dice "Entidad de destino Plin"
            if "plin" in cand.lower() or "yape" in cand.lower():
                continue
            cand = _limpiar_nombre(cand)
            if _es_nombre_valido(cand):
                candidatos.append((cand, 0.85))

        # Para Yape/Plin sin etiquetas previas, un nombre válido a veces aparece antes de la fecha
        if re.search(r"^\d{1,2}\s*[a-zA-Z]{3}", l_l) or re.search(r"^\d{1,2}[/\-\s]", l) or "202" in l:
            idx = max(0, i-1)
            cand = lineas[idx].strip()
            if cand and cand.lower() not in TEXTOS_INTERFAZ and _es_nombre_valido(cand):
                # Podría ser el nombre del receptor, o emisor si es "Yapeaste"
                cand = _limpiar_nombre(cand)
                candidatos.append((cand, 0.70))
    # ── 1. Patrones YAPE específicos ─────────────────────────────────
    # "Yapiste a NAME" o "iYapeaste S/100\nNAME" o "¡Yapiste a NAME!"
    for i, linea in enumerate(lineas):
        linea_l = linea.lower()

        # "Yapiste a [NAME]" en la misma línea
        m = re.search(r"(?:yapiste|yapeaste|yapeast)\s+(?:a\s+)?(?:S/\s*\d+[.,]?\d*\s*)?(.+)", linea, _flags())
        if m:
            nombre_candidato = _limpiar_nombre(m.group(1))
            if _es_nombre_valido(nombre_candidato):
                receptor = nombre_candidato
                conf_r = 0.85
            # Si después de S/XXX viene el nombre en la SIGUIENTE línea
            elif i + 1 < len(lineas):
                siguiente = _limpiar_nombre(lineas[i + 1])
                if _es_nombre_valido(siguiente):
                    receptor = siguiente
                    conf_r = 0.85

        # "iYapeaste S/XXX" sin nombre → nombre en siguiente línea
        if re.search(r"(?:yapiste|yapeaste|yapeast)\s+S/", linea, _flags()):
            if receptor is None and i + 1 < len(lineas):
                siguiente = _limpiar_nombre(lineas[i + 1])
                if _es_nombre_valido(siguiente):
                    receptor = siguiente
                    conf_r = 0.85

    # ── 2. Patrones PLIN específicos ─────────────────────────────────
    # "Contacto\nNAME" — receptor
    for i, linea in enumerate(lineas):
        if re.match(r"^contacto$", linea.strip(), _flags()):
            # Juntar las siguientes líneas como nombre
            partes_nombre = []
            for j in range(i + 1, min(i + 10, len(lineas))):
                parte = lineas[j].strip()
                # Si es un número (como el celular "0309" que el OCR intercala por error), lo ignoramos pero continuamos
                if re.match(r"^[:.\-\d\s]+$", parte):
                    continue
                if _es_nombre_valido(parte):
                    partes_nombre.append(parte)
                else:
                    break
            if partes_nombre:
                receptor = " ".join(partes_nombre).title()
                conf_r = 0.85

    # ── 3. Patrones genéricos (receptor) ─────────────────────────────
    if receptor is None:
        patrones_receptor = [
            r"(?:para|receptor|destinatario|recibido por)[:\s]+(.+)",
            r"(?:transferiste a|enviaste a|pagaste a)[:\s]+(.+)",
            r"(?:emisor|pagador|remitente|enviado por)[:\s]+(.+)",  # Si por error el OCR lee algo así, lo asumiremos receptor igual
            r"(?:nombre del (?:emisor|remitente|pagador))[:\s]+(.+)",
        ]
        for patron in patrones_receptor:
            m = re.search(patron, texto, _flags())
            if m:
                nombre = _limpiar_nombre(m.group(1))
                if _es_nombre_valido(nombre):
                    receptor = nombre
                    conf_r = 0.75
                    break

    # ── 4. Fallback: buscar nombres propios si no se encontró nada ───
    if receptor is None:
        nombres_propios = []
        for linea in lineas:
            palabras = linea.split()
            if 2 <= len(palabras) <= 5:
                if all(p[0].isupper() and len(p) > 2 for p in palabras if p.isalpha()):
                    candidato = linea.strip()
                    if _es_nombre_valido(candidato):
                        nombres_propios.append(candidato)

        if nombres_propios:
            # Si hay varios, simplemente los unimos porque el usuario afirma que siempre es un solo nombre
            receptor = " ".join(nombres_propios)
            conf_r = 0.55

    return (
        None,  # Emisor siempre nulo
        0.0,
        receptor if conf_r >= UMBRAL_CONFIANZA_CAMPO else None,
        conf_r,
    )


def extraer_descripcion(texto: str) -> Tuple[Optional[str], float]:
    """Extrae descripción/motivo/concepto."""
    patrones = [
        r"(?:descripci[oó]n|motivo|concepto|mensaje|nota|referencia)[:\s]+(.+)",
        r"(?:por)[:\s]+\"?(.{3,60})\"?",
    ]
    for patron in patrones:
        m = re.search(patron, texto, _flags())
        if m:
            valor = m.group(1).strip()
            if valor and len(valor) > 2:
                return valor[:200], 0.80
    return None, 0.0


# ──────────────────────────────────────────────────────────────────────────────
# Función principal de parsing
# ──────────────────────────────────────────────────────────────────────────────

def parsear_comprobante(
    texto: str,
    nombre_archivo: str,
    confianza_ocr: float,
    motor_ocr: str,
    hash_img: str,
    calidad_imagen: str,
    tiempo_seg: float,
) -> ResultadoOCR:
    """
    Orquesta la extracción semántica de todos los campos.
    Aplica umbrales de confianza antes de aceptar cada valor.
    """
    from pathlib import Path

    if not texto or not texto.strip():
        return ResultadoOCR(
            archivo=nombre_archivo,
            extension_archivo=Path(nombre_archivo).suffix,
            hash_imagen=hash_img,
            error="No se pudo extraer texto del archivo.",
            observaciones=["OCR devolvió texto vacío."],
            confianza_global=0.0,
            nivel_confianza=NivelConfianza.BAJA,
        )

    texto_norm = _normalizar_texto(texto)

    # Log raw text for debugging
    logger.debug(f"RAW OCR TEXT for {nombre_archivo}:\n{texto_norm[:500]}")

    # Extraer todos los campos
    tipo_app, conf_tipo = extraer_tipo_app(texto_norm)
    op_exitosa, conf_op = extraer_operacion_exitosa(texto_norm)
    monto, conf_monto = extraer_monto(texto_norm)
    fecha, conf_fecha = extraer_fecha(texto_norm)
    hora, conf_hora = extraer_hora(texto_norm)
    emisor, conf_emisor, receptor, conf_receptor = extraer_nombres(texto_norm)
    celular, conf_cel = extraer_celular(texto_norm)
    banco, conf_banco = extraer_banco(texto_norm)
    num_op, conf_num_op = extraer_numero_operacion(texto_norm)
    descripcion, conf_desc = extraer_descripcion(texto_norm)

    logger.debug(f"EXTRACTED for {nombre_archivo}: tipo={tipo_app} monto={monto} fecha={fecha} hora={hora} emisor={emisor} receptor={receptor} celular={celular} banco={banco} num_op={num_op}")

    # ── Construir confianza por campo ─────────────────────────────────────────
    conf_campos = ConfianzaPorCampo(
        monto=round(conf_monto, 3) if monto is not None else None,
        moneda=0.95 if monto is not None else None,
        fecha=round(conf_fecha, 3) if fecha is not None else None,
        hora=round(conf_hora, 3) if hora is not None else None,
        nombre_emisor_o_pagador=round(conf_emisor, 3) if emisor is not None else None,
        nombre_receptor_o_destinatario=round(conf_receptor, 3) if receptor is not None else None,
        numero_celular_relacionado=round(conf_cel, 3) if celular is not None else None,
        banco_o_billetera=round(conf_banco, 3) if banco is not None else None,
        numero_operacion=round(conf_num_op, 3) if num_op is not None else None,
        descripcion=round(conf_desc, 3) if descripcion is not None else None,
        estado_operacion=round(conf_op, 3) if op_exitosa is not None else None,
        tipo_app=round(conf_tipo, 3) if tipo_app is not None else None,
    )

    # ── Campos dudosos ────────────────────────────────────────────────────────
    UMBRAL_DUDA = 0.75
    campos_dudosos = []
    mapa_conf = {
        "monto": conf_monto if monto else 0,
        "fecha": conf_fecha if fecha else 0,
        "hora": conf_hora if hora else 0,
        "nombre_emisor_o_pagador": conf_emisor if emisor else 0,
        "nombre_receptor_o_destinatario": conf_receptor if receptor else 0,
        "numero_operacion": conf_num_op if num_op else 0,
        "tipo_app": conf_tipo if tipo_app else 0,
    }
    for campo, conf in mapa_conf.items():
        if 0 < conf < UMBRAL_DUDA:
            campos_dudosos.append(campo)

    # ── Confianza global ──────────────────────────────────────────────────────
    # Mezcla: confianza OCR + confianza promedio de campos extraídos
    confs_extraidas = [c for c in mapa_conf.values() if c > 0]
    conf_semantica = float(sum(confs_extraidas) / len(confs_extraidas)) if confs_extraidas else 0.0
    confianza_global = round((confianza_ocr * 0.4 + conf_semantica * 0.6), 3)

    if confianza_global >= 0.90:
        nivel = NivelConfianza.ALTA
    elif confianza_global >= 0.75:
        nivel = NivelConfianza.MEDIA
    else:
        nivel = NivelConfianza.BAJA

    # ── Observaciones automáticas ─────────────────────────────────────────────
    observaciones = []

    return ResultadoOCR(
        archivo=nombre_archivo,
        extension_archivo=Path(nombre_archivo).suffix,
        hash_imagen=hash_img,
        tipo_app=tipo_app,
        operacion_exitosa=op_exitosa,
        estado_operacion=op_exitosa,
        monto=monto,
        moneda="PEN",
        fecha=fecha,
        hora=hora,
        nombre_emisor_o_pagador=emisor,
        nombre_receptor_o_destinatario=receptor,
        numero_celular_relacionado=celular,
        banco_o_billetera=banco,
        numero_operacion=num_op,
        descripcion=descripcion,
        texto_completo_detectado=texto[:3000],  # Limitar tamaño
        calidad_imagen_estimada=calidad_imagen,
        motor_ocr_primario=motor_ocr,
        confianza_global=confianza_global,
        nivel_confianza=nivel,
        confianza_por_campo=conf_campos,
        campos_dudosos=campos_dudosos,
        observaciones=observaciones,
        tiempo_procesamiento_seg=tiempo_seg,
    )
