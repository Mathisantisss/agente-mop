FROM python:3.10-slim

WORKDIR /app

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements
COPY requirements_cloud.txt .
RUN pip install --no-cache-dir -r requirements_cloud.txt

# Copiar archivos de la app
COPY app_publica.py .
COPY agent.py .
COPY local_agent.py .
COPY cloud_agent.py .
COPY config.py .
COPY .streamlit/ .streamlit/

# Crear carpeta de reportes
RUN mkdir -p reportes

# Puerto de Streamlit
EXPOSE 8501

# Variables de entorno necesarias
ENV PYTHONIOENCODING=utf-8

# Comando de inicio
CMD ["python", "-m", "streamlit", "run", "app_publica.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0", \
     "--server.headless=true", \
     "--browser.gatherUsageStats=false"]
