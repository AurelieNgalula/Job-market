# 📁 Architecture du Projet

## Structure réorganisée

```
job-market/
├── backend/                    # 🔧 Code Python (backend)
│   ├── app.py                  # 🌐 FastAPI - Endpoints de recherche
│   ├── job_indexer.py          # ⚙️  Pipeline d'indexation (embeddings → DB)
│   ├── fetch_jobs.py           # 🔄 Récupération API France Travail
│   ├── utils.py                # 🛠️  Fonctions partagées
│   └── requirements.txt        # 📦 Dépendances Python
│
├── data/                       # 📊 Données (offres d'emploi JSON)
│   └── YYYYMMDD_offres_emploi.json
│
├── docker-compose.yml          # 🐳 Orchestration Docker
├── Dockerfile                  # 🐳 Image Docker
├── .env.example                # ⚙️  Variables d'environnement
└── README.md
```

## Responsabilités de chaque fichier

### `backend/app.py` 🌐
**Serveur FastAPI avec endpoints de recherche**
- `GET /` : Interface web (HTML + JavaScript)
- `GET /search?q=query` : Recherche simple (retourne JSON)
- `GET /search-stream?query=q` : Recherche en streaming (SSE)
- `GET /health` : Health check

### `backend/job_indexer.py` ⚙️
**Pipeline d'indexation des offres d'emploi**
- Charge les offres depuis `data/*.json`
- Génère les embeddings avec SentenceTransformer
- Insère/met à jour les données en PostgreSQL
- Gère les batches pour optimiser les performances

Lancer avec:
```bash
python3 job_indexer.py
```

### `backend/fetch_jobs.py` 🔄
**Récupération des offres via API France Travail**
- Authentification OAuth2
- Pagination des résultats
- Sauvegarde en JSON dans `data/`

Lancer avec:
```bash
python3 fetch_jobs.py
```

### `backend/helpers.py` 🛠️
**Fonctions utilitaires partagées**
- `clean_text()` : Normalisation de texte
- `parse_date()` : Parsing ISO 8601
- `build_text()` : Construction du texte pour embeddings
- `extract_competences()` : Extraction compétences
- `extract_location()` : Extraction lieu de travail
- OAuth2 & requêtes API

---

## Flux de travail

### 1️⃣ Développement local

```bash
# Terminal 1 - Récupère les offres
cd backend
python3 fetch_jobs.py
# → Crée data/YYYYMMDD_offres_emploi.json

# Terminal 2 - Indexe les données
cd backend
python3 job_indexer.py
# → Génère embeddings, insère dans PostgreSQL

# Terminal 3 - Lance le serveur
cd backend
pip install -r requirements.txt
uvicorn app:app --reload
# → Disponible sur http://localhost:8001
```

### 2️⃣ Avec Docker Compose

```bash
# Lance le serveur FastAPI
docker compose up app

# Lance le worker (fetch + indexer) avec le profil worker
docker compose --profile worker up worker
```

---

## Avantages de cette arborescence

| Aspect | Bénéfice |
|--------|----------|
| **Séparation des concerns** | Chaque script a une responsabilité unique |
| **Testabilité** | Facile à tester chaque composant isolément |
| **Maintenabilité** | Code clairement organisé et facile à naviguer |
| **Scalabilité** | Simple d'ajouter de nouveaux endpoints ou services |
| **Réutilisabilité** | `helpers.py` évite la duplication |
| **Déploiement** | Structure prête pour production |

---

## Points clés

✅ **Plus de duplication** : Les fonctions communes sont dans `helpers.py`
✅ **Données centralisées** : Tous les JSON dans `data/`
✅ **API claire** : `app.py` = endpoints FastAPI seulement
✅ **Pipeline indépendant** : `fetch_jobs.py` et `job_indexer.py` peuvent tourner seuls
✅ **Configuration facile** : `.env` pour les secrets
