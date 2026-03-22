"""
Exportador de resultados a PDF profesional.
Genera un reporte con un diseño moderno, claro e intuitivo.
"""

from pathlib import Path
from typing import List
from datetime import datetime
from loguru import logger

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable, KeepTogether
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

from modules.models import ResultadoOCR, NivelConfianza

# ── Paleta de Colores Moderna ──────────────────────────────────────────────────
COLOR_PRIMARIO     = colors.HexColor("#2563EB")  # Azul vibrante
COLOR_TEXTO        = colors.HexColor("#1E293B")  # Gris muy oscuro
COLOR_TEXTO_SEC    = colors.HexColor("#64748B")  # Gris secundario
COLOR_FONDO_TABLA  = colors.HexColor("#F8FAFC")  # Fondo sutil
COLOR_BORDE        = colors.HexColor("#E2E8F0")  # Borde suave

YAPE_COLOR         = colors.HexColor("#7C3AED")  # Morado (Yape)
PLIN_COLOR         = colors.HexColor("#0891B2")  # Cyan/Azul (Plin)

VERDE_EXITO        = colors.HexColor("#10B981")
VERDE_FONDO        = colors.HexColor("#D1FAE5")
AMARILLO_ALERTA    = colors.HexColor("#F59E0B")
AMARILLO_FONDO     = colors.HexColor("#FEF3C7")
ROJO_ERROR         = colors.HexColor("#EF4444")
ROJO_FONDO         = colors.HexColor("#FEE2E2")
GRIS_BADGE         = colors.HexColor("#F1F5F9")

def _color_confianza_fondo(nivel: NivelConfianza | None):
    if nivel == NivelConfianza.ALTA: return VERDE_FONDO
    if nivel == NivelConfianza.MEDIA: return AMARILLO_FONDO
    if nivel == NivelConfianza.BAJA: return ROJO_FONDO
    return GRIS_BADGE

def _color_confianza_texto(nivel: NivelConfianza | None):
    if nivel == NivelConfianza.ALTA: return VERDE_EXITO
    if nivel == NivelConfianza.MEDIA: return AMARILLO_ALERTA
    if nivel == NivelConfianza.BAJA: return ROJO_ERROR
    return COLOR_TEXTO_SEC

def _estilos():
    """Retorna diccionario de estilos modernos y limpios."""
    base = getSampleStyleSheet()
    return {
        "titulo_principal": ParagraphStyle(
            "titulo_principal",
            parent=base["Title"],
            fontSize=28,
            textColor=COLOR_TEXTO,
            spaceAfter=8,
            alignment=TA_CENTER,
            fontName="Helvetica-Bold",
        ),
        "subtitulo_principal": ParagraphStyle(
            "subtitulo_principal",
            parent=base["Normal"],
            fontSize=14,
            textColor=COLOR_TEXTO_SEC,
            spaceAfter=20,
            alignment=TA_CENTER,
            fontName="Helvetica",
        ),
        "titulo_seccion": ParagraphStyle(
            "titulo_seccion",
            parent=base["Normal"],
            fontSize=18,
            textColor=COLOR_PRIMARIO,
            spaceBefore=20,
            spaceAfter=12,
            alignment=TA_CENTER,
            fontName="Helvetica-Bold",
        ),
        "normal": ParagraphStyle(
            "normal",
            parent=base["Normal"],
            fontSize=10,
            textColor=COLOR_TEXTO,
            fontName="Helvetica",
        ),
        "archivo_titulo": ParagraphStyle(
            "archivo_titulo",
            parent=base["Normal"],
            fontSize=12,
            textColor=COLOR_TEXTO,
            fontName="Helvetica-Bold",
            spaceBefore=14,
            spaceAfter=6,
        ),
        "metric_value": ParagraphStyle(
            "metric_value",
            parent=base["Normal"],
            fontSize=24,
            textColor=COLOR_PRIMARIO,
            fontName="Helvetica-Bold",
            alignment=TA_CENTER,
            spaceAfter=4,
        ),
        "metric_label": ParagraphStyle(
            "metric_label",
            parent=base["Normal"],
            fontSize=10,
            textColor=COLOR_TEXTO_SEC,
            fontName="Helvetica",
            alignment=TA_CENTER,
        )
    }

def _v(valor) -> str:
    if valor is None: return "—"
    if isinstance(valor, float): return f"{valor:,.2f}"
    return str(valor)

def _pct(valor: float | None) -> str:
    if valor is None: return "—"
    return f"{valor * 100:.1f}%"

def _portada(elements, estilos, total, exitosos, con_dudas, errores, suma_montos):
    """Genera una portada de alto impacto."""
    elements.append(Spacer(1, 2*cm))
    elements.append(Paragraph("Reporte de Extracción OCR", estilos["titulo_principal"]))
    elements.append(Paragraph("Comprobantes de Pago Yape & Plin", estilos["subtitulo_principal"]))
    elements.append(HRFlowable(width="100%", thickness=3, color=COLOR_PRIMARIO, spaceAfter=20))
    
    fecha_gen = datetime.now().strftime("%d de %B, %Y - %H:%M:%S")
    elements.append(Paragraph(f"Fecha de generación: <b>{fecha_gen}</b>", ParagraphStyle("center_date", parent=estilos["normal"], alignment=TA_CENTER)))
    elements.append(Spacer(1, 1.5*cm))

    # Grid de métricas clave (3 columnas)
    m1 = [Paragraph(str(total), estilos["metric_value"]), Paragraph("Comprobantes", estilos["metric_label"])]
    m2 = [Paragraph(f"S/ {suma_montos:,.2f}", estilos["metric_value"]), Paragraph("Monto Total", estilos["metric_label"])]
    m3 = [Paragraph(str(exitosos), estilos["metric_value"]), Paragraph("Exitosos", estilos["metric_label"])]
    
    t_metrics = Table([[m1, m2, m3]], colWidths=[5.5*cm, 5.5*cm, 5.5*cm])
    t_metrics.setStyle(TableStyle([
        ("ALIGN", (0,0), (-1,-1), "CENTER"),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("BACKGROUND", (0,0), (-1,-1), COLOR_FONDO_TABLA),
        ("ROUNDEDCORNERS", [8, 8, 8, 8]),
        ("TOPPADDING", (0, 0), (-1, -1), 15),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 15),
    ]))
    elements.append(t_metrics)
    elements.append(Spacer(1, 2*cm))

def _resumen_ejecutivo(elements, estilos, resultados: List[ResultadoOCR]):
    """Desglose más detallado en la portada."""
    elements.append(Paragraph("Resumen Operativo", estilos["titulo_seccion"]))
    
    n_yape = sum(1 for r in resultados if r.tipo_app and r.tipo_app.value == "YAPE")
    n_plin = sum(1 for r in resultados if r.tipo_app and r.tipo_app.value == "PLIN")
    confs = [r.confianza_global for r in resultados if r.confianza_global is not None]
    prom_conf = sum(confs) / len(confs) if confs else 0.0

    datos = [
        ["Operaciones YAPE", str(n_yape)],
        ["Operaciones PLIN", str(n_plin)],
        ["Precisión Promedio del OCR", _pct(prom_conf)],
    ]
    
    # Tabla elegante para el desglose
    t = Table(datos, colWidths=[10*cm, 6.5*cm])
    t.setStyle(TableStyle([
        ("TEXTCOLOR", (0,0), (-1,-1), COLOR_TEXTO),
        ("FONTNAME", (0,0), (0,-1), "Helvetica-Bold"),
        ("FONTNAME", (1,0), (1,-1), "Helvetica"),
        ("FONTSIZE", (0,0), (-1,-1), 11),
        ("ALIGN", (1,0), (1,-1), "RIGHT"),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("LINEBELOW", (0,0), (-1,-2), 0.5, COLOR_BORDE),
        ("TOPPADDING", (0, 0), (-1, -1), 12),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
    ]))
    elements.append(t)

def _detalle_capturas(elements, estilos, resultados: List[ResultadoOCR]):
    elements.append(PageBreak())
    elements.append(Paragraph("Detalle de Comprobantes", estilos["titulo_principal"]))
    elements.append(HRFlowable(width="100%", thickness=2, color=COLOR_PRIMARIO, spaceAfter=15))

    for i, r in enumerate(resultados, start=1):
        # Bloque unitario que no se rompe entre páginas
        bloque = []
        
        # 1. Header del Comprobante
        header_data = [
            [Paragraph(f"<b>#{i} — {r.archivo}</b>", estilos["normal"]), ""]
        ]
        t_header = Table(header_data, colWidths=[12.5*cm, 4*cm])
        t_header.setStyle(TableStyle([
            ("ALIGN", (1,0), (1,0), "RIGHT"),
            ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
            ("TOPPADDING", (0,0), (-1,-1), 0),
            ("BOTTOMPADDING", (0,0), (-1,-1), 4),
        ]))
        bloque.append(t_header)

        # 2. Información Extraída (Diseño en Grid Moderno)
        app_val = r.tipo_app.value if r.tipo_app else "Desconocida"
        if app_val == "YAPE":
            bg_color, txt_color = YAPE_COLOR, colors.white
        elif app_val == "PLIN":
            bg_color, txt_color = PLIN_COLOR, colors.white
        else:
            bg_color, txt_color = COLOR_BORDE, COLOR_TEXTO

        t_chip = Table([[app_val]], colWidths=[2.5*cm])
        t_chip.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,-1), bg_color),
            ("TEXTCOLOR", (0,0), (-1,-1), txt_color),
            ("FONTNAME", (0,0), (-1,-1), "Helvetica-Bold"),
            ("FONTSIZE", (0,0), (-1,-1), 8),
            ("ALIGN", (0,0), (-1,-1), "CENTER"),
            ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
            ("ROUNDEDCORNERS", [4, 4, 4, 4]),
            ("TOPPADDING", (0,0), (-1,-1), 2),
            ("BOTTOMPADDING", (0,0), (-1,-1), 2),
        ]))

        monto_str = f"S/ {r.monto:,.2f}" if r.monto is not None else "—"
        
        datos_grid = [
            ["Receptor:", _v(r.nombre_receptor_o_destinatario)],
            ["Monto:", monto_str],
            ["Fecha y Hora:", f"{_v(r.fecha)} {_v(r.hora)}"],
            ["Aplicación:", t_chip],
            ["N° Operación:", _v(r.numero_operacion)],
            ["Estado:", _v(r.operacion_exitosa).capitalize()],
        ]
        
        t_detalle = Table(datos_grid, colWidths=[4*cm, 12.5*cm])
        t_detalle.setStyle(TableStyle([
            ("TEXTCOLOR", (0,0), (0,-1), COLOR_TEXTO_SEC),  # Labels grises
            ("TEXTCOLOR", (1,0), (1,-1), COLOR_TEXTO),      # Valores oscuros
            ("FONTNAME", (0,0), (0,-1), "Helvetica"),
            ("FONTNAME", (1,0), (1,-1), "Helvetica-Bold"),
            ("FONTSIZE", (0,0), (-1,-1), 10),
            ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
            ("TOPPADDING", (0,0), (-1,-1), 6),
            ("BOTTOMPADDING", (0,0), (-1,-1), 6),
            ("LINEBELOW", (0,0), (-1,-2), 0.25, COLOR_BORDE),
            ("BACKGROUND", (0,0), (-1,-1), colors.white),
        ]))
        
        # Envolvemos la tabla en una tabla padre para darle borde redondeado sutil
        t_card = Table([[t_detalle]], colWidths=[16.5*cm])
        t_card.setStyle(TableStyle([
            ("BOX", (0,0), (-1,-1), 1, COLOR_BORDE),
            ("ROUNDEDCORNERS", [6, 6, 6, 6]),
            ("BACKGROUND", (0,0), (-1,-1), colors.white),
        ]))
        bloque.append(t_card)
        
        # 3. Alertas / Dudas
        if r.campos_dudosos or r.observaciones:
            bloque.append(Spacer(1, 0.2*cm))
            if r.campos_dudosos:
                txt = f"<b>Revisión Manual Sugerida:</b> Baja confianza en {', '.join(r.campos_dudosos)}"
                bloque.append(Paragraph(txt, ParagraphStyle("warn", parent=estilos["normal"], textColor=AMARILLO_ALERTA, fontSize=9)))

        bloque.append(Spacer(1, 1*cm))
        elements.append(KeepTogether(bloque))

def _pie_pagina(canvas, doc):
    canvas.saveState()
    width, height = A4
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(COLOR_TEXTO_SEC)
    
    aviso = "Generado Automáticamente | Verifique importes y nombres sugeridos visualmente."
    canvas.drawCentredString(width / 2, 1.2*cm, aviso)
    
    pag = f"Página {doc.page}"
    canvas.drawRightString(width - 2*cm, 1.2*cm, pag)
    canvas.restoreState()

def exportar_pdf(resultados: List[ResultadoOCR], ruta_salida: Path) -> Path:
    ruta_salida.parent.mkdir(parents=True, exist_ok=True)
    estilos = _estilos()

    doc = SimpleDocTemplate(
        str(ruta_salida),
        pagesize=A4,
        leftMargin=2.2*cm,
        rightMargin=2.2*cm,
        topMargin=2*cm,
        bottomMargin=2.5*cm,
        title="Reporte OCR Financiero",
        author="Sistema OCR Automático",
    )

    elements = []

    total = len(resultados)
    exitosos = sum(1 for r in resultados if r.nivel_confianza == NivelConfianza.ALTA)
    con_dudas = sum(1 for r in resultados if r.nivel_confianza in [NivelConfianza.MEDIA, NivelConfianza.BAJA])
    errores = sum(1 for r in resultados if r.error)
    montos = [r.monto for r in resultados if r.monto is not None]
    suma_montos = sum(montos)

    _portada(elements, estilos, total, exitosos, con_dudas, errores, suma_montos)
    _resumen_ejecutivo(elements, estilos, resultados)
    _detalle_capturas(elements, estilos, resultados)

    doc.build(elements, onFirstPage=_pie_pagina, onLaterPages=_pie_pagina)
    logger.info(f"PDF exportado exitosamente con diseño moderno: {ruta_salida}")
    return ruta_salida
