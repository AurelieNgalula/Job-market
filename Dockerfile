FROM python:3.14-slim

WORKDIR /app

# Installer les dependances systeme necessaires
RUN apt-get update && apt-get install -y \
    build-essential \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copier les fichiers de requirements
COPY script/requirements.txt .

# Installer les dependances Python
RUN pip install --no-cache-dir -r requirements.txt

# Copier le projet
COPY . .

# Definir les permissions
RUN mkdir -p /app/script/out && chmod -R 755 /app/script

EXPOSE 8001

CMD ["bash", "-c", "cd script && uvicorn app:app --host 0.0.0.0 --port 8001"]
