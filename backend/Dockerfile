# Usamos la imagen base de Python oficial con Debian (importante para librerías de sistema)
FROM python:3.10-slim

# Instalar dependencias del sistema operativo requeridas por OpenCV (libGL)
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Configurar directorio de trabajo
WORKDIR /app

# Copiar el archivo de requerimientos e instalarlos
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar todo el código del backend
COPY . .

# Exponer el puerto configurado por la variable de entorno $PORT (clásico en Render)
EXPOSE 8000

# Comando para iniciar la aplicación FastAPI
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
