# OCR · YAPE & PLIN

Sistema OCR de alta precisión para extracción estructurada de datos de comprobantes de pago YAPE y PLIN.

---

## Características

- **Motor OCR híbrido**: PaddleOCR (principal) + Tesseract (respaldo)
- **Pipeline de 5 capas**: original → preprocesada → regiones → motor alternativo → reconciliación
- **Detección automática** YAPE vs PLIN
- **Extracción conservadora**: campo vacío antes que campo inventado
- **Confianza por campo** y confianza global (alta / media / baja)
- **Exportación a Excel** (.xlsx) con 3 hojas: Resumen, Texto OCR, Auditoría
- **Exportación a PDF** profesional con portada y detalle por captura
- **Exportación a JSON** estructurado
- **Detección de duplicados** por hash MD5 + hash perceptual
- **Interfaz web** drag & drop con filtros y tabla de resultados
- **Procesamiento en lote** de hasta 50 imágenes

---

## Estructura del proyecto

```
ocr_yape_plin/
├── backend/
│   ├── main.py                     # FastAPI app principal
│   ├── modules/
│   │   ├── models.py               # Modelos Pydantic (schemas)
│   │   ├── preprocesador.py        # Pipeline de imagen (OpenCV)
│   │   ├── ocr_engine.py           # PaddleOCR + Tesseract + ensemble
│   │   ├── parser.py               # Extracción semántica por campo
│   │   ├── procesador.py           # Orquestador principal
│   │   ├── exportador_excel.py     # Generador de .xlsx
│   │   ├── exportador_pdf.py       # Generador de .pdf
│   │   └── detector_duplicados.py  # Hash MD5 + perceptual
│   └── routers/
│       ├── ocr_router.py           # Endpoint POST /api/ocr/procesar
│       └── export_router.py        # Endpoints /api/export/{excel|pdf|json}
├── frontend/
│   └── index.html                  # Interfaz web completa
├── tests/
│   └── test_parser.py              # Tests unitarios del parser
├── logs/                           # Logs diarios (auto-creado)
├── uploads/                        # Archivos temporales (auto-creado)
├── exports/                        # Archivos exportados (auto-creado)
├── requirements.txt
├── install.sh
└── README.md
```

---

## Instalación

### Opción A: Script automático (Linux/macOS)

```bash
cd ocr_yape_plin
chmod +x install.sh
./install.sh
```

### Opción B: Manual paso a paso

#### 1. Requisitos del sistema

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install -y python3 python3-pip python3-venv
sudo apt-get install -y tesseract-ocr tesseract-ocr-spa
sudo apt-get install -y libgl1-mesa-glx libglib2.0-0  # para OpenCV
```

**macOS:**
```bash
brew install python tesseract tesseract-lang
```

**Windows:**
- Instalar Python 3.10+ desde https://python.org
- Instalar Tesseract desde https://github.com/UB-Mannheim/tesseract/wiki
- Agregar Tesseract al PATH del sistema

#### 2. Entorno virtual

```bash
python3 -m venv venv
source venv/bin/activate      # Linux/macOS
# venv\Scripts\activate       # Windows
pip install --upgrade pip
```

#### 3. Dependencias Python

```bash
pip install -r requirements.txt
```

> **Nota sobre PaddleOCR:** La primera ejecución descargará automáticamente los modelos de detección y reconocimiento (~200MB). Se necesita conexión a internet en el primer uso.

---

## Ejecución

```bash
# Activar entorno virtual (si no está activo)
source venv/bin/activate

# Ir al backend
cd backend

# Iniciar servidor
python main.py
```

El servidor estará disponible en: **http://localhost:8000**

La interfaz web se abre automáticamente en esa URL.

### Modo desarrollo (recarga automática)

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

---

## Uso de la API

### Procesar imágenes

```bash
curl -X POST http://localhost:8000/api/ocr/procesar \
  -F "archivos=@captura_yape.png" \
  -F "archivos=@captura_plin.jpg"
```

### Exportar a Excel

```bash
curl -X POST http://localhost:8000/api/export/excel \
  -H "Content-Type: application/json" \
  -d '{"resultados": [...]}' \
  --output reporte.xlsx
```

### Exportar a PDF

```bash
curl -X POST http://localhost:8000/api/export/pdf \
  -H "Content-Type: application/json" \
  -d '{"resultados": [...]}' \
  --output reporte.pdf
```

### Verificar motores OCR disponibles

```bash
curl http://localhost:8000/api/ocr/health
```

---

## Ejemplo de salida JSON

```json
{
  "archivo": "captura_001.png",
  "extension_archivo": ".png",
  "hash_imagen": "a3f9c2b1d4e5f6a7",
  "posible_duplicado": false,
  "tipo_app": "YAPE",
  "operacion_exitosa": "sí",
  "estado_operacion": "sí",
  "monto": 25.50,
  "moneda": "PEN",
  "fecha": "2026-03-21",
  "hora": "14:32:08",
  "nombre_emisor_o_pagador": "Juan Perez",
  "nombre_receptor_o_destinatario": "Maria Lopez",
  "numero_celular_relacionado": "987654321",
  "banco_o_billetera": "BCP",
  "numero_operacion": "987654321",
  "descripcion": "Pago de pedido",
  "texto_completo_detectado": "YAPE\n¡Yapiste a Maria Lopez!\nS/ 25.50\n...",
  "calidad_imagen_estimada": "alta",
  "motor_ocr_primario": "PaddleOCR",
  "confianza_global": 0.921,
  "nivel_confianza": "alta",
  "confianza_por_campo": {
    "monto": 0.980,
    "moneda": 0.950,
    "fecha": 0.900,
    "hora": 0.900,
    "nombre_emisor_o_pagador": null,
    "nombre_receptor_o_destinatario": 0.750,
    "numero_celular_relacionado": 0.850,
    "banco_o_billetera": 0.900,
    "numero_operacion": 0.850,
    "descripcion": null,
    "estado_operacion": 0.800,
    "tipo_app": 0.900
  },
  "campos_dudosos": ["nombre_receptor_o_destinatario"],
  "observaciones": [
    "Campos con baja confianza: nombre_receptor_o_destinatario."
  ],
  "tiempo_procesamiento_seg": 2.14
}
```

---

## Umbrales de confianza

| Nivel  | Rango        | Color en UI | Acción recomendada       |
|--------|-------------|-------------|--------------------------|
| Alta   | ≥ 90%        | 🟢 Verde    | Aceptar directamente     |
| Media  | 75% – 89%    | 🟡 Amarillo | Revisar campos dudosos   |
| Baja   | < 75%        | 🔴 Rojo     | Verificación manual      |

---

## Tests

```bash
# Desde la raíz del proyecto
source venv/bin/activate
pytest tests/ -v
```

---

## Mejoras futuras recomendadas

### Precisión OCR
1. **Fine-tuning de PaddleOCR** con capturas reales peruanas de YAPE/PLIN
2. **Claude Vision API** como validador de campos dudosos (sin inventar, solo confirmar o rechazar)
3. **Detección de regiones con YOLO** para localizar bloques de monto, fecha, etc. antes del OCR
4. **Super-resolución** (Real-ESRGAN) para imágenes de muy baja calidad

### Funcionalidad
5. **Soporte PDF** con imágenes embebidas (PyMuPDF)
6. **API key y autenticación** para uso en producción
7. **Base de datos** (SQLite/PostgreSQL) para historial de procesamiento
8. **Webhook** para notificar cuando termina un lote grande
9. **Cola de tareas** (Celery + Redis) para lotes muy grandes
10. **Dashboard analytics** con gráficos de montos por período

### Infraestructura
11. **Dockerización** completa con docker-compose
12. **CI/CD** con GitHub Actions
13. **Monitoreo** con Prometheus + Grafana
14. **GPU support** para acelerar PaddleOCR en producción

---

## Limitaciones conocidas

- El sistema **no modifica ni recrea** comprobantes. Solo extrae información.
- Capturas muy borrosas o con texto de menos de 8px pueden tener baja precisión.
- Nombres de personas son el campo más difícil de extraer con alta confianza.
- PaddleOCR requiere ~500MB de RAM en uso.
- La primera ejecución puede tardar 30-60s descargando modelos.

---

## Licencia

Uso interno. No distribuir sin autorización.
