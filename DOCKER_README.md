# Docker Setup - Job Market

## Description

Ce projet Git est livré avec une configuration Docker Compose pour lancer l'application Job-market :
- PostgreSQL 15 avec extension `pgvector`
- Application FastAPI
- Worker de traitement des données

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
NAME                        STATUS
job-market-postgres         Up (healthy)
job-market-app              Up
```

### 4. Accéder à l'application
- **Application** : http://localhost:8001
- **API Docs** : http://localhost:8001/docs
- **ReDoc** : http://localhost:8001/redoc

---

## Services

### PostgreSQL
- **Port** : 5432
- **Utilisateur** : jobmarket
- **Mot de passe** : jobmarket_secure_password_123
- **Base de données** : jobmarket_db
- **Extension** : pgvector

Se connecter à la base :
```bash
docker compose exec postgres psql -U jobmarket -d jobmarket_db
```

### FastAPI Application
- **Port** : 8001
- **Mode** : reload automatique
- **Logs** : `docker compose logs -f app`

### Worker (Pipeline)
- **Profile** : worker
- **Fonction** : traite les données et crée les embeddings

Lancer le worker :
```bash
docker compose --profile worker up worker
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
docker compose logs -f postgres
```

### Entrer dans un container
```bash
# Application
docker compose exec app bash

# PostgreSQL
docker compose exec postgres bash
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
DATABASE_URL=postgresql://jobmarket:jobmarket_secure_password_123@postgres:5432/jobmarket_db
```

### Ports

Modifier les ports dans `docker-compose.yml` si nécessaire :
```yaml
ports:
  - "8001:8001"
```

---

## Pipeline de données

### 1. Lancer PostgreSQL
```bash
docker compose up -d postgres
```

### 2. Attendre que PostgreSQL soit prêt
```bash
docker compose ps
```

### 3. Lancer le worker
```bash
docker compose --profile worker up worker
```

---

## Projet Git

- Cloner le repo : `git clone <url_du_repo> Job-market`
- Créer une branche pour chaque fonctionnalité :
```bash
git checkout -b feature/ma-fonctionnalite
```
- Committer :
```bash
git add .
git commit -m "Description du changement"
```
- Pousser :
```bash
git push origin feature/ma-fonctionnalite
```
- Ouvrir une Pull Request pour revue

- Lire `script/out/offres_emploi.json`
- Creer les embeddings
- Remplir la table `jobs_embeddings`

### 4. Demarrer l app
```bash
docker-compose up -d app
```

### 5. Tester l app
```bash
curl http://localhost:8001/search?q=python
```

---

## Production

Pour un deploiement production:

### 1. Modifier docker-compose.yml
```yaml
app:
  command: bash -c "cd script && uvicorn app:app --host 0.0.0.0 --port 8001 --workers 4"
```

### 2. Utiliser un .env securise
```bash
docker-compose --env-file .env.prod up -d
```

### 3. Configurer un reverse proxy (nginx)
```bash
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### 4. Configuration SSL/TLS
- Utiliser Traefik ou nginx
- Certificats Let's Encrypt

---

## Troubleshooting

### Erreur: "Address already in use"
```bash
# Changer le port dans docker-compose.yml
ports:
  - "8002:8001"  # Utiliser 8002 a la place de 8001
```

### Erreur: "Cannot connect to PostgreSQL"
```bash
# Verifier que postgres est pret
docker-compose logs postgres

# Relancer postgres
docker-compose restart postgres
```

### Erreur: "Module not found"
```bash
# Reconstruire l image
docker-compose build --no-cache
docker-compose up
```

### Donnees perdues apres down
Les donnees PostgreSQL sont stockees dans `postgres_data` volume. Pour les conserver:
```bash
docker-compose down  # Ne pas utiliser -v
```

### Voir la consommation de ressources
```bash
docker stats job-market-postgres job-market-app
```

---

## Fichiers

```
.
├── docker-compose.yml      # Configuration des services
├── Dockerfile              # Image Docker de l app
├── .dockerignore           # Fichiers a ignorer
├── .env.example            # Template variables d env
├── script/
│   ├── app.py              # FastAPI app
│   ├── recommand.py        # Pipeline worker
│   ├── requirements.txt    # Dependances Python
│   └── out/                # Donnees JSON
└── docker-README.md        # Ce fichier
```

---

## Performance

- **PostgreSQL**: Optimise pour pgvector
- **FastAPI**: Mode production avec workers
- **RAM requis**: ~2GB minimum
- **Stockage**: ~500MB pour donnees + volumes

---

## Support

Pour plus d aide:
- Docker Compose: https://docs.docker.com/compose/
- PostgreSQL: https://www.postgresql.org/docs/
- pgvector: https://github.com/pgvector/pgvector
- FastAPI: https://fastapi.tiangolo.com/

---

## License

Job-market (2026)
