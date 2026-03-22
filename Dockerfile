# Usamos la imagen base de Python oficial con Debian (importante para librerías de sistema)
FROM python:3.10-slim

# Instalar dependencias del sistema operativo requeridas por OpenCV (libGL)
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Configurar directorio de trabajo
WORKDIR /app

# Copiar el archivo de requerimientos e instalarlos
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el código del backend al directorio de trabajo
# Nota: Si el Dockerfile está en la raíz, copiamos el contenido de 'backend'
COPY backend/ .

# Exponer el puerto configurado por la variable de entorno $PORT (clásico en Render)
EXPOSE 8000

# Comando para iniciar la aplicación FastAPI
# Como copiamos el contenido de backend/ a ., el archivo main.py está en la raíz del contenedor
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
