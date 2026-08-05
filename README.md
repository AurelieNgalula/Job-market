# Job Market

Ce projet collecte des offres d’emploi depuis l’API France Travail, stocke les résultats au format JSON, indexe les offres dans PostgreSQL avec des embeddings et expose une API de recherche sémantique via FastAPI.

## Fonctionnement global

Le flux principal est le suivant :

1. La collecte des offres est réalisée par un script Python depuis l’API France Travail.
2. Les résultats sont sauvegardés dans le dossier data/incoming.
3. Un DAG Airflow exécute ensuite l’indexation des offres dans une base PostgreSQL avec pgvector.
4. Une application FastAPI permet de rechercher les offres par mots-clés, localisation et similarité sémantique.
5. L’API expose des endpoints techniques et de supervision : /health, /stats et /metrics.
6. Prometheus scrape régulièrement l’endpoint /metrics pour collecter les métriques applicatives.
7. Grafana consomme Prometheus comme datasource et affiche les tableaux de bord de suivi (requêtes, latence, endpoints).

## Structure du dépôt

```text
Job-market/
├── backend/
│   ├── app.py                  # API FastAPI + interface web
│   ├── requirements.txt
│   └── templates/
├── dags/
│   └── france_travail.py       # DAG Airflow
├── data/
│   ├── archive/
│   └── incoming/
├── logs/   
├── monitoring/
│   ├── prometheus/
│   │   └── prometheus.yml      # Configuration de scraping Prometheus
│   └── grafana/
│       ├── dashboards/
│       │   └── fastapi-dashboard.json
│       └── provisioning/
│           ├── dashboards/
│           │   └── default.yml
│           └── datasources/
│               └── prometheus.yml
├── scripts/
│   ├── indexation_offres.py    # Pipeline d'indexation
│   ├── get_offres.py           # Collecte des offres
│   └── utils.py
├── docker-compose.yaml
├── Dockerfile
├── requirements.txt
└── README.md
```

## Prérequis

- Python 3.11+
- Docker et Docker Compose
- Une base PostgreSQL accessible avec l’extension vector
- Des identifiants France Travail : CLIENT_ID et CLIENT_SECRET

## Variables d’environnement

Créer un fichier .env à la racine du projet avec les variables suivantes :

```env 
CLIENT_ID=votre_client_id
CLIENT_SECRET=votre_client_secret

# Base PostgreSQL utilisée pour l'indexation et la recherche
DB_POSTGRES_URL=postgresql://user:password@host:5432/jobmarket_db (base distante Neon)

# Optionnel pour Airflow
profil standard : 
AIRFLOW_DB_USER=airflow
AIRFLOW_DB_PASSWORD=airflow
AIRFLOW_DB_NAME=airflow
```

## Démarrage avec Docker

### 1. Construire et lancer les services

```bash
docker compose up --build -d
```

### 2. Vérifier les services

```bash
docker compose ps
```

### 3. Accéder aux interfaces

- Application FastAPI : http://localhost:8001
- Documentation Swagger : http://localhost:8001/docs
- Airflow UI : http://localhost:8080
- Prometheus UI : http://localhost:9090
- Grafana UI : http://localhost:3000 (identifiant: admin, mot de passe: admin, puis cliquer sur skip sur la page login, puis aller dans dashboards et choisir le projet job market)

## Lancement local sans Docker

### 1. Installer les dépendances

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install -r backend/requirements.txt
```

### 2. Collecter les offres

```bash
python3 scripts/get_offres.py
```

### 3. Indexer les offres dans PostgreSQL

```bash
python3 scripts/indexation_offres.py
```

### 4. Lancer l’API FastAPI

```bash
cd backend
uvicorn app:app --host 0.0.0.0 --port 8001
```

## API disponible

L’application FastAPI expose les endpoints suivants :

- GET / : interface web de recherche
- GET /search?query=...&location=...&limit=10 : recherche JSON
- GET /search-stream?query=... : recherche en streaming SSE
- GET /health : vérification de l’état du service
- GET /stats: retourne les métriques de suivi du monitoring

## Airflow

Le DAG défini dans dags/france_travail.py exécute deux tâches :

- collecte_offres : récupération des offres sur les dernières 24 heures
- indexation_offres : génération des embeddings et insertion dans PostgreSQL

Il est planifié tous les jours à 22:00 (Europe/Paris).

## Notes importantes

- Les fichiers JSON collectés sont stockés dans data/incoming puis déplacés vers data/archive après indexation.
- La recherche sémantique repose sur le modèle sentence-transformers all-MiniLM-L6-v2.
- Le backend FastAPI initialise automatiquement la table `base_embedding` au démarrage si la base PostgreSQL est accessible.
- La base PostgreSQL doit contenir l’extension vector pour les opérations pgvector.

## Dépendances principales

- FastAPI
- Uvicorn
- SQLAlchemy
- sentence-transformers
- pgvector
- Apache Airflow
- requests
- python-dotenv
