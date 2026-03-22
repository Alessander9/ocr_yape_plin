import os
import sys
from pathlib import Path

# Add backend to sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from modules.models import ResultadoOCR, NivelConfianza
from modules.exportador_pdf import exportar_pdf

resultados = [
    ResultadoOCR(
        archivo="yape_comprobante_1.png",
        extension_archivo=".png",
        hash_imagen="123",
        tipo_app="YAPE",
        operacion_exitosa="si",
        monto=150.50,
        moneda="PEN",
        fecha="2026-03-20",
        hora="15:30:00",
        nombre_emisor_o_pagador=None,
        nombre_receptor_o_destinatario="Juan Perez Garcia",
        numero_celular_relacionado="987654321",
        banco_o_billetera="BCP",
        numero_operacion="123456789",
        descripcion="Pago Almuerzo",
        confianza_global=0.95,
        nivel_confianza=NivelConfianza.ALTA,
        campos_dudosos=[],
        observaciones=[]
    ),
    ResultadoOCR(
        archivo="plin_comprobante_roto.jpg",
        extension_archivo=".jpg",
        hash_imagen="456",
        tipo_app="PLIN",
        operacion_exitosa="dudoso",
        monto=50.00,
        moneda="PEN",
        fecha="2026-03-21",
        hora="10:15:00",
        nombre_emisor_o_pagador=None,
        nombre_receptor_o_destinatario="Maria Mendoza",
        numero_celular_relacionado="999888777",
        banco_o_billetera="Interbank",
        numero_operacion="987654321",
        descripcion="Deuda",
        confianza_global=0.60,
        nivel_confianza=NivelConfianza.BAJA,
        campos_dudosos=["operacion_exitosa"],
        observaciones=["La imagen es borrosa"]
    )
]

salida = Path("test_reporte.pdf")
exportar_pdf(resultados, salida)
print(f"PDF generado en: {salida.absolute()}")
