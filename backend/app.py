"""
FastAPI Application - Recherche sémantique d'offres d'emploi.
Endpoints:
- GET / : Interface web
- GET /search : Recherche simple (retourne JSON)
- GET /search-stream : Recherche en streaming (SSE)
- GET /health : Vérifie que l'app fonctionne
- GET /stats : Statistiques de l'application (monitoring)
"""

import json
import os
import sys
from pathlib import Path
import time
from datetime import datetime
try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    from dotenv import dotenv_values

    def load_dotenv(*args, **kwargs):
        return dotenv_values(*args, **kwargs)

from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, HTMLResponse
from sqlalchemy import create_engine, text
from sentence_transformers import SentenceTransformer
from prometheus_fastapi_instrumentator import Instrumentator


# =========================================================
# MONITORING - Compteurs en mémoire
# =========================================================
stats = {
    "demarrage": datetime.now().isoformat(),  # Quand l'app a démarré
    "total_requetes": 0,                       # Nombre total de requêtes
    "requetes_par_endpoint": {},               # Compteur par page
    "total_recherches": 0,                     # Nombre de recherches effectuées
    "temps_reponse_moyen_ms": 0,               # Temps de réponse moyen
    "derniere_requete": None,                  # Date de la dernière requête
    "erreurs": 0,                              # Nombre d'erreurs
    "_temps_total": 0,                         # (interne) pour calculer la moyenne
}

BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from utils import clean_text

load_dotenv()

# =========================================================
# APP FASTAPI
# =========================================================
app = FastAPI(title="Job Market")
TEMPLATES_DIR = Path(__file__).parent / "templates"

# Exposition des métriques Prometheus sur /metrics
Instrumentator().instrument(app).expose(app)

# =========================================================
# MIDDLEWARE DE MONITORING
# =========================================================
# Un middleware s'exécute AVANT et APRÈS chaque requête
@app.middleware("http")
async def monitoring_middleware(request: Request, call_next):
    """
    Ce middleware :
    1. Note l'heure de début
    2. Laisse la requête s'exécuter
    3. Calcule le temps écoulé
    4. Met à jour les statistiques
    """
    debut = time.time()  # l'heure de début
    
    try:
        response = await call_next(request)  # exécute la requête
        
        # calcule le temps en millisecondes
        duree_ms = (time.time() - debut) * 1000
        
        # met à jour les compteurs
        stats["total_requetes"] += 1
        stats["derniere_requete"] = datetime.now().isoformat()
        
        # comptage par endpoint
        endpoint = request.url.path
        stats["requetes_par_endpoint"][endpoint] = stats["requetes_par_endpoint"].get(endpoint, 0) + 1
        
        # calcule le temps moyen
        stats["_temps_total"] += duree_ms
        stats["temps_reponse_moyen_ms"] = round(stats["_temps_total"] / stats["total_requetes"], 2)
        
        return response
        
    except Exception as e:
        stats["erreurs"] += 1
        raise e

# =========================================================
# DATABASE
# =========================================================
DB_POSTGRES_URL = (
    os.getenv("DB_POSTGRES_URL")
    or os.getenv("DATABASE_URL")
)

if not DB_POSTGRES_URL:
    raise ValueError("DB_POSTGRES_URL is not set in environment variables.")    

engine = create_engine(DB_POSTGRES_URL, pool_pre_ping=True)
# pool_pre_ping=True tester une connexion avant de l'utiliser, pour éviter les erreurs de connexion expirée.

# =========================================================
# MODEL (lazy loading)
# =========================================================
_model = None

def get_model():
    """Charge le modèle d'embeddings."""
    global _model
    if _model is None:
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def ensure_table_exists():
    """Crée la table de recherche si elle n'existe pas."""
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS base_embedding (
                id TEXT PRIMARY KEY,
                title TEXT,
                text TEXT,
                location TEXT,
                competences TEXT[],
                date_actualisation TIMESTAMP,
                embedding VECTOR(384)
            );
        """))


# =========================================================
# SEARCH STREAMING (core function)
# =========================================================
def search_stream(query, location=None, limit=10):
    """Effectue une recherche sémantique et retourne les résultats."""
    query = clean_text(query)
    vec = get_model().encode([query], normalize_embeddings=True)[0].tolist()

    sql = """
        SELECT id, title, location, competences, date_actualisation,
               1 - (embedding <=> CAST(:v AS vector)) AS score
        FROM base_embedding

    """

    params = {"v": vec, 
            "limit": limit
            }

    if location :
        sql += """ 
                where lower(location) like lower(:location)
            """
        params["location"] = f"%{location}%"
    
    sql += """
        ORDER BY embedding <=> CAST(:v AS vector) 
        LIMIT :limit;
        """

    with engine.connect() as conn:
        result = conn.execute(text(sql), params)

        for row in result:
            date_value = getattr(row, "date_actualisation", None)
            date_str = date_value.isoformat() if hasattr(date_value, "isoformat") else date_value

            yield {
                "id": row.id,
                "title": row.title,
                "location": row.location,
                "competences": list(row.competences) if row.competences else [],
                "date_actualisation": date_str,
                "score": float(row.score)
            }


# =========================================================
# ENDPOINTS
# =========================================================
@app.get("/", response_class=HTMLResponse)
def ui(request: Request):
    """Interface web pour la recherche."""
    template_path = TEMPLATES_DIR / "index.html"
    return HTMLResponse(template_path.read_text(encoding="utf-8"))


@app.get("/search")
def search_api( query: str = None, location: str = None, limit: int = 10):
    """Endpoint de recherche simple (retourne JSON)."""
    ensure_table_exists()
    if not query:
        return []
    return list(search_stream(query, location, limit))


@app.get("/search-stream")
def stream_search(query: str, location: str = None, limit: int = 10):
    """Endpoint de recherche en streaming (SSE)."""
    def event_generator():
        for result in search_stream(query, location, limit):
            yield f"data: {json.dumps(result)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream"
    )


# =========================================================
# ENDPOINTS DE MONITORING 
# =========================================================
@app.get("/health")
def health_check():
    """
    HEALTH CHECK - Vérifie que l'application fonctionne.
    
    Retourne:
    - status: "ok" si tout va bien, "error" sinon
    - database: "connectée" si PostgreSQL répond
    - uptime: depuis combien de temps l'app tourne
    
    Utile pour: vérifier rapidement que l'app est en vie.
    """
    # On vérifie la connexion à la base de données
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_status = "connectée"
    except Exception as e:
        db_status = f"erreur: {str(e)}"
    
    # On calcule depuis combien de temps l'app tourne
    demarrage = datetime.fromisoformat(stats["demarrage"])
    uptime = datetime.now() - demarrage
    uptime_str = str(uptime).split('.')[0]  # Format: "1:23:45"
    
    return {
        "status": "ok" if db_status == "connectée" else "error",
        "message": "L'application Job Market fonctionne!",
        "database": db_status,
        "uptime": uptime_str,
        "timestamp": datetime.now().isoformat()
    }


@app.get("/stats")
def get_stats():
    """
    STATISTIQUES - Montre ce qui se passe dans l'application.
    
    Retourne des métriques simples:
    - Combien de requêtes ont été faites
    - Quelles pages sont les plus visitées
    - Le temps de réponse moyen
    - Combien d'erreurs il y a eu
    
    Utile pour: comprendre l'usage de l'app.
    """
    demarrage = datetime.fromisoformat(stats["demarrage"])
    uptime = datetime.now() - demarrage
    
    return {
        "resume": {
            "total_requetes": stats["total_requetes"],
            "total_recherches": stats["total_recherches"],
            "erreurs": stats["erreurs"],
            "temps_reponse_moyen_ms": stats["temps_reponse_moyen_ms"]
        },
        "endpoints_populaires": stats["requetes_par_endpoint"],
        "info_app": {
            "demarrage": stats["demarrage"],
            "uptime": str(uptime).split('.')[0],
            "derniere_requete": stats["derniere_requete"]
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)