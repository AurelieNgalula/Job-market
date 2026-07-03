# Job-market

Ce projet Git contient une application Python qui récupère des offres d'emploi via l'API France Travail, stocke les résultats en JSON et permet une recherche sémantique via embeddings dans une base PostgreSQL.

## Tableau de bord Git

Ce dépôt est conçu comme un projet Git standard :
- Cloner le dépôt depuis GitHub
- Installer les dépendances
- Lancer les scripts localement ou via Docker
- Versionner les modifications dans des branches dédiées

Une nouvelle personne peut démarrer rapidement en clonant le repo, en configurant ses variables d'environnement, puis en utilisant Docker ou la CLI Python.

## Architecture du projet

```
Job-market/
├── backend/
│   ├── app.py              # API FastAPI + interface web
│   ├── fetch_jobs.py       # Récupération des offres France Travail
│   ├── job_indexer.py      # Pipeline d'indexation et embeddings
│   ├── utils.py            # Utilitaires OAuth2 et parsing
│   ├── requirements.txt    # Dépendances Python
│   └── templates/          # Interface HTML
├── data/                   # Données JSON utilisées pour l'indexation
├── Dockerfile
├── docker-compose.yml
├── README.md
├── DOCKER_README.md
├── .env.example
└── .gitignore
```

## Prérequis

- Git
- Docker Engine 20.10+
- Docker Compose 2.0+
- Python 3.14+ (optionnel si vous n'utilisez pas Docker)
- Identifiants France Travail : `CLIENT_ID` et `CLIENT_SECRET`

## Démarrage rapide (Git + Docker)

### 1. Cloner le dépôt

```bash
git clone <url_du_repo> Job-market
cd Job-market
```

### 2. Construire et démarrer avec Docker Compose

```bash
docker compose up --build
```

Cette commande lance :
- `app` (FastAPI)
- `worker` (optionnel, pour l’indexation)

Pour démarrer aussi le worker de traitement :

```bash
docker compose up --build --profile worker
```

### 3. Vérifier l’état des services

```bash
docker compose ps
```

### 4. Accéder à l’API

- Service FastAPI : `http://localhost:8001`
- Documentation Swagger : `http://localhost:8001/docs`

## Lancer sans Docker

### 1. Installer les dépendances

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r script/requirements.txt
```

### 2. Configurer les identifiants

Créer un fichier `.env` à la racine :

```env
CLIENT_ID=votre_client_id
CLIENT_SECRET=votre_client_secret
DATABASE_URL=postgresql://user:password@host:5432/dbname?sslmode=require
DB_POSTGRES_URL=postgresql://user:password@host:5432/dbname?sslmode=require
```

### 3. Récupérer les offres

```bash
cd backend
python3 fetch_jobs.py
```

### 4. Lancer le worker / indexation

```bash
cd backend
python3 job_indexer.py
```

## Utilisation du Dockerfile

### Construire l’image

```bash
docker build -t job-market:latest .
```

### Lancer l’application FastAPI

```bash
docker run --rm -p 8001:8001 \
  -e DATABASE_URL=postgresql://user:password@host:5432/dbname?sslmode=require \
  -v "$(pwd)/backend:/app/backend" \
  -v "$(pwd)/data:/app/data" \
  job-market:latest
```

### Lancer le worker

```bash
docker run --rm \
  -e DATABASE_URL=postgresql://user:password@host:5432/dbname?sslmode=require \
  -v "$(pwd)/backend:/app/backend" \
  -v "$(pwd)/data:/app/data" \
  job-market:latest \
  bash -c "cd backend && python3 job_indexer.py"
```

## Structure des scripts

### `backend/fetch_jobs.py`

- Envoie des requêtes vers l’API France Travail
- Gère les fenêtres temporelles et la pagination
- Sauvegarde les offres récupérées dans `data/`

### `backend/job_indexer.py`

- Charge les données JSON
- Calcule des embeddings avec `SentenceTransformer`
- Enregistre les vecteurs dans PostgreSQL via `pgvector`
- Propose une recherche sémantique interactive

## Git Workflows recommandés

- Créer une branche pour chaque fonctionnalité ou correction :
  ```bash
git checkout -b feature/ma-fonctionnalite
```
- Ajouter, committer et pousser :
  ```bash
git add .
git commit -m "Ajout de la doc Docker"
git push origin feature/ma-fonctionnalite
```
- Ouvrir une Pull Request pour revue

## Notes

- Le `docker-compose.yml` inclut un service `worker` avec le profil `worker`.
- Le service `app` expose le port `8001`.
- Les dossiers `backend` et `data` sont montés en volume pour partager les sources avec les containers.

#### 3️⃣ Recréer l'environnement virtuel

```bash
cd /Users/yaoyao/Desktop/Job-market
rm -rf .venv
/opt/homebrew/bin/python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r script/requirements.txt
```

#### 4️⃣ Vérifier l'installation

```bash
source .venv/bin/activate
python3 --version
python3 -c "import ssl; print('OpenSSL:', ssl.OPENSSL_VERSION)"
```

**Résultat attendu** :
```
Python 3.14.3
OpenSSL: OpenSSL 3.6.1 27 Jan 2026
```

### Sur Linux

```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install python3.14 python3.14-venv python3.14-dev

# Fedora
sudo dnf install python3.14 python3.14-devel

# Puis recréer le venv comme sur macOS ci-dessus
```



## Contact / Support

Pour toute question ou problème, consultez la [documentation France Travail API](https://www.francetravail.fr/partenaire/nos-api).

---

**Dernière mise à jour** : 6 mars 2026

### 📦 Dépendances installées (mise à jour 2026-03-06)

| Package | Version |
|---------|---------|
| requests | 2.32.5 |
| python-dotenv | 1.2.2 |
| pandas | 3.0.1 |
| numpy | 2.4.2 |
| urllib3 | 2.6.3 |
| certifi | 2026.2.25 |
