# Docker Setup - Job Market

## Description

Ce projet Git est livré avec une configuration Docker Compose pour lancer l'application Job-market :
- Application FastAPI
- Worker de traitement des données
- Connexion à une base PostgreSQL distante ou locale via variables d’environnement

Il est pensé pour un nouveau contributeur qui veut cloner le repo et démarrer directement avec Docker.

---

## Prérequis

- Git
- Docker Engine 20.10+
- Docker Compose 2.0+

### Installation

#### macOS (Homebrew)
```bash
brew install docker
```

#### Ubuntu/Debian
```bash
sudo apt-get update
sudo apt-get install docker.io docker-compose-plugin
```

#### Windows
Télécharger Docker Desktop : https://www.docker.com/products/docker-desktop

---

## Démarrage rapide

### 1. Cloner le projet
```bash
git clone <url_du_repo> Job-market
cd Job-market
```

### 2. Construire et démarrer les services
```bash
docker compose up --build
```

### 3. Vérifier l’état des services
```bash
docker compose ps
```

Vous devriez voir :
```
NAME                STATUS
job-market-app      Up
job-market-worker   Up (si profil activé)
```

### 4. Accéder à l'application
- **Application** : http://localhost:8001
- **API Docs** : http://localhost:8001/docs
- **ReDoc** : http://localhost:8001/redoc

---

## Services

### Base PostgreSQL
Le projet se connecte à une base PostgreSQL via les variables `DB_POSTGRES_URL` et `DATABASE_URL`.

Exemple avec une base distante (ICI : NEONDB):
```env
DB_POSTGRES_URL=postgresql://user:password@host:5432/dbname?sslmode=require
DATABASE_URL=postgresql://user:password@host:5432/dbname?sslmode=require
```

### FastAPI Application
- **Port** : 8001
- **Mode** : reload automatique
- **Logs** : `docker compose logs -f app`

### Worker (Pipeline)
- **Profile** : worker
- **Fonction** : récupère les offres et crée les embeddings

Lancer le worker :
```bash
docker compose --profile worker up worker
```
dans le cas où le code change 
```bash
docker compose --profile worker up --build worker
```
reste complet 
```bash
docker compose down
```
---

## Commandes utiles

### Démarrer tous les services
```bash
docker compose up -d
```

### Arrêter les services
```bash
docker compose down
```

### Voir les logs
```bash
# Tous les services
docker compose logs -f

# Service spécifique
docker compose logs -f app
docker compose logs -f worker
```

### Entrer dans un container
```bash
# Application
docker compose exec app bash

# Worker
docker compose exec worker bash
```

### Relancer un service
```bash
docker compose restart app
```

### Reconstruire une image
```bash
docker compose build --no-cache
```

### Nettoyer les ressources
```bash
docker compose down
```

### Supprimer aussi les volumes
```bash
docker compose down -v
```

---

## Configuration

### Variables d’environnement

La configuration principale est définie dans `docker-compose.yml`.

Si vous souhaitez personnaliser la connexion PostgreSQL, créez un fichier `.env` à la racine et démarrez Docker Compose avec :

```bash
docker compose --env-file .env up
```

Exemple :
```env
DATABASE_URL=postgresql://user:password@host:5432/dbname?sslmode=require
DB_POSTGRES_URL=postgresql://user:password@host:5432/dbname?sslmode=require
```

### Ports

Modifier les ports dans `docker-compose.yml` si nécessaire :
```yaml
ports:
  - "8001:8001"
```

---

## Pipeline de données

### 1. Vérifier la configuration de la base
Assurez-vous d’avoir défini `DB_POSTGRES_URL` et/ou `DATABASE_URL` dans votre fichier `.env`.

### 2. Démarrer l’application
```bash
docker compose up -d app
```

### 3. Lancer le worker
```bash
docker compose --profile worker up worker

