# Application Recherche Semantique d Emploi

## Description

Application FastAPI pour la recherche semantique d'offres d emploi avec embeddings vectoriels et pgvector.

### Fonctionnalites:
- Recherche semantique intelligente d offres d emploi
- Affichage du lieu de travail
- Affichage des competences requises
- Score de similarite (0-100%)
- Interface web intuitive
- API REST pour integrations

---

## Prerequis

### 1. Python 3.11+
```bash
python3 --version
```

### 2. Virtual Environment Active
```bash
source .venv/bin/activate
```

### 3. Dependances Installes
```bash
pip install -r backend/requirements.txt
```

### 4. Donnees d Emploi
Le fichier `backend/data/YYYYMMDD_offres_emploi.json` doit exister. Si absent, executer d abord:
```bash
python3 script/recommand.py
```

### 5. Base de Donnees
- PostgreSQL avec extension pgvector
- Connection URL configuree dans `app.py`
- Table `jobs_embeddings` auto-creee au premier lancement

---

## Lancer l Application

### Option 1: Depuis le repertoire backend (Recommande)
```bash
cd /backend
source ../../.venv/bin/activate
uvicorn app:app --reload --host 127.0.0.1 --port 8001
```

### Option 2: Commande complete depuis racine
```bash
source .venv/bin/activate
cd backend
uvicorn app:app --reload --host 127.0.0.1 --port 8001
```

### Option 3: One-liner
```bash
source .venv/bin/activate && cd backend && uvicorn app:app --reload --host 127.0.0.1 --port 8001
```

---

## Acces l Application

Une fois demarree, l application est disponible sur:

### Interface Web
- **URL**: http://127.0.0.1:8001
- **Description**: Interface utilisateur avec recherche et resultats

### API REST
  - `q` ou `query`: terme de recherche
- **Recherche**: http://localhost:8001/search?query=python
- **Parametres**: 
  - `query`: terme de recherche
  - `location`: lieu de travail
  - `limit`: nombre de resultats (defaut: 10)

### Documentation API
- **Swagger UI**: http://localhost.0.0.1:8001/docs
- **ReDoc**: http://127.0.0.1:8001/redoc

---

## Utilisation

### Recherche Simple
1. Ouvrir http://localhost:8001
2. Taper votre recherche (ex: "python", "data scientist", "infirmier")
3. Cliquer "Chercher"
4. Les resultats affichent:
   - Titre du poste
   - Date d'actualisation
   - Lieu de travail
   - Competences requises
   - Score de similarite (%)

### Exemples de Recherche
- "developpeur python paris"
- "data scientist"
- "infirmier ile-de-france"
- "manager projet agile"

### API via curl
```bash
curl "http://localhost:8001/search?query=python&limit=5"
```

### API via Python
```python
import requests

response = requests.get("http://localhost:8001/search", params={
    "query": "python",
    "limit": 5
})
results = response.json()
print(results)
```

---

## Structure des Resultats

Chaque resultat contient:
```json
{
  "id": "offre_123",
  "title": "Developpeur Python Senior",
  "location": "Paris, Ile-de-France",
  "competences": ["python", "django", "sql", "docker"],
  "date_actualisation":"2026-01-15T02:31:45"
  "score": 0.845
}
```

---

## Parametres de Lancement

### Options Uvicorn
- `--reload`: Redemarre automatiquement en cas de modification (dev)
- `--host 127.0.0.1`: Ecoute uniquement localement
- `--port 8001`: Port d ecoute
- `--workers 4`: Nombre de workers (prod)

### Commande Production
```bash
cd script
uvicorn app:app --host 0.0.0.0 --port 8001 --workers 4
```

---

## Arreter l Application

Appuyer sur `Ctrl+C` dans le terminal pour arreter le serveur.

---

## Troubleshooting

### Erreur: "Could not import module app"
- Verifier que vous etes dans le repertoire `script/`
- Commande correcte: `cd script && uvicorn app:app`

### Erreur: "Address already in use"
- Le port 8001 est deja utilise
- Solution: changer le port avec `--port 8002`

### Erreur: "Table jobs_embeddings does not exist"
- Executer d abord: `python3 script/recommand.py`
- Cela cree la table et charge les donnees

### Erreur: "No data found"
- Verifier que `script/out/offres_emploi.json` existe
- Sinon, executer: `python3 script/offers_fetcher.py`

---

## Performance

- Temps de reponse: < 200ms
- Capacite: +16000 offres d emploi
- Embeddings: Modele all-MiniLM-L6-v2 (384 dimensions)
- Base de donnees: PostgreSQL + pgvector


## Configuration

### Variables d Environnement
Verifier la CONNECTION string PostgreSQL dans `app.py`:
```python
DB_POSTGRES_URL = "postgresql://user:password@host/db?sslmode=require"
```

### Modele d Embeddings
Modele utilise: `all-MiniLM-L6-v2` (sentence-transformers)
- Dimensions: 384
- Temps de chargement: ~2-5 secondes
- Taille: ~90 MB

---

## Support

Pour plus d informations, consulter:
- FastAPI: https://fastapi.tiangolo.com
- Uvicorn: https://www.uvicorn.org
- SQLAlchemy: https://www.sqlalchemy.org
- pgvector: https://github.com/pgvector/pgvector

---

## Licence

Projet Job-market (2026)
