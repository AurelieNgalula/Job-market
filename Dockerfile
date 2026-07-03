FROM python:3.11-slim

WORKDIR /app

# Installer les dépendances système nécessaires
RUN apt-get update && apt-get install -y \
    build-essential \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copier les fichiers de requirements selon la nouvelle arborescence
COPY backend/requirements.txt ./backend/requirements.txt

# Installer les dépendances Python
RUN pip install --no-cache-dir -r backend/requirements.txt

# Définir les permissions
RUN mkdir -p /app/data && chmod -R 755 /app/backend /app/data

EXPOSE 8001

CMD ["bash", "-c", "cd /app/backend && uvicorn app:app --host 0.0.0.0 --port 8001"]
