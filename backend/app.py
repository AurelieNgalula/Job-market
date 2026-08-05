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
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, HTMLResponse
from sqlalchemy import text
from prometheus_fastapi_instrumentator import Instrumentator
from prometheus_client import Counter, Gauge

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    from dotenv import dotenv_values

    def load_dotenv(*args, **kwargs):
        return dotenv_values(*args, **kwargs)

from utils import clean_text, get_model, ensure_table_exists, engine

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

# =========================================================
# METRIQUES PROMETHEUS (alignées avec /stats)
# =========================================================
PROM_REQUESTS_TOTAL = Counter(
    "jobmarket_requests_total",
    "Nombre total de requetes traitees par l'application"
)

PROM_REQUESTS_BY_ENDPOINT_TOTAL = Counter(
    "jobmarket_requests_by_endpoint_total",
    "Nombre de requetes par endpoint",
    ["endpoint"]
)

PROM_SEARCHES_TOTAL = Counter(
    "jobmarket_searches_total",
    "Nombre total de recherches effectuees"
)

PROM_ERRORS_TOTAL = Counter(
    "jobmarket_errors_total",
    "Nombre total d'erreurs applicatives"
)

PROM_RESPONSE_TIME_TOTAL_MS = Counter(
    "jobmarket_response_time_total_ms",
    "Somme des temps de reponse en millisecondes"
)

PROM_RESPONSE_TIME_BY_ENDPOINT_TOTAL_MS = Counter(
    "jobmarket_response_time_by_endpoint_total_ms",
    "Somme des temps de reponse en millisecondes par endpoint",
    ["endpoint"]
)

PROM_RESPONSE_TIME_AVG_MS = Gauge(
    "jobmarket_response_time_avg_ms",
    "Temps de reponse moyen en millisecondes"
)

PROM_LAST_REQUEST_TIMESTAMP = Gauge(
    "jobmarket_last_request_timestamp_seconds",
    "Timestamp unix de la derniere requete"
)

PROM_STARTUP_TIMESTAMP = Gauge(
    "jobmarket_startup_timestamp_seconds",
    "Timestamp unix du demarrage de l'application"
)

BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


# =========================================================
# APP FASTAPI
# =========================================================
app = FastAPI(title="Job Market")
TEMPLATES_DIR = Path(__file__).parent / "templates"

PROM_STARTUP_TIMESTAMP.set(datetime.now().timestamp())

# Exposition des métriques Prometheus sur /metrics
Instrumentator(should_group_status_codes=False, should_ignore_untemplated=True).instrument(app).expose(app)

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
    endpoint = request.url.path

    try:
        response = await call_next(request)  # exécute la requête

        return response

    except Exception:
        stats["erreurs"] += 1
        PROM_ERRORS_TOTAL.inc()
        raise

    finally:
        # On compte toutes les requetes (y compris celles en erreur)
        duree_ms = (time.time() - debut) * 1000

        stats["total_requetes"] += 1
        stats["derniere_requete"] = datetime.now().isoformat()
        stats["requetes_par_endpoint"][endpoint] = stats["requetes_par_endpoint"].get(endpoint, 0) + 1
        stats["_temps_total"] += duree_ms
        stats["temps_reponse_moyen_ms"] = round(stats["_temps_total"] / stats["total_requetes"], 2)

        PROM_REQUESTS_TOTAL.inc()
        PROM_REQUESTS_BY_ENDPOINT_TOTAL.labels(endpoint=endpoint).inc()
        PROM_RESPONSE_TIME_TOTAL_MS.inc(duree_ms)
        PROM_RESPONSE_TIME_BY_ENDPOINT_TOTAL_MS.labels(endpoint=endpoint).inc(duree_ms)
        PROM_RESPONSE_TIME_AVG_MS.set(stats["temps_reponse_moyen_ms"])
        PROM_LAST_REQUEST_TIMESTAMP.set(time.time())

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


@app.on_event("startup")
def startup():
    """Initialisation à chaud de l'application."""
    ensure_table_exists()


@app.get("/search")
def search_api(query: str = None, location: str = None, limit: int = 10):
    """Endpoint de recherche simple (retourne JSON)."""
    if not query:
        return []
    stats["total_recherches"] += 1
    PROM_SEARCHES_TOTAL.inc()
    return list(search_stream(query, location, limit))


@app.get("/search-stream")
def stream_search(query: str, location: str = None, limit: int = 10):
    """Endpoint de recherche en streaming (SSE)."""
    stats["total_recherches"] += 1
    PROM_SEARCHES_TOTAL.inc()

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