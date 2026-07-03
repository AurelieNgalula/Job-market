"""
FastAPI Application - Recherche sémantique d'offres d'emploi.
Endpoints:
- GET / : Interface web
- GET /search : Recherche simple (retourne JSON)
- GET /search-stream : Recherche en streaming (SSE)
"""

import json
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, HTMLResponse
from sqlalchemy import create_engine, text
from sentence_transformers import SentenceTransformer

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

# =========================================================
# DATABASE
# =========================================================
DB_POSTGRES_URL = (
    os.getenv("DB_POSTGRES_URL")
    or os.getenv("DATABASE_URL")
    or "postgresql://jobmarket:jobmarket_secure_password_123@postgres:5432/jobmarket_db"
)
engine = create_engine(DB_POSTGRES_URL)

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
            CREATE TABLE IF NOT EXISTS jobs_embeddings (
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
        FROM jobs_embeddings

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
# HEALTH CHECK
# =========================================================
@app.get("/health")
def health():
    """Health check endpoint."""
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
