FROM python:3.11-slim

WORKDIR /app

# System deps requeridos por asyncpg y psycopg2
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Instalar dependencias Python primero (mejor cache de Docker)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código
COPY . .

# Crear directorio de logs (montado como volumen en producción)
RUN mkdir -p /var/log/igniten

# Punto de entrada: scheduler (no web server)
CMD ["python", "main.py"]
