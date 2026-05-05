import json
import unicodedata
import os
from datetime import datetime

from fastapi import FastAPI
from fastapi.responses import StreamingResponse, HTMLResponse

from sqlalchemy import create_engine, text
from sentence_transformers import SentenceTransformer

# =========================================================
# APP FASTAPI
# =========================================================
app = FastAPI()

# =========================================================
# DATABASE
# =========================================================
DB_POSTGRES_URL = "postgresql://neondb_owner:npg_VjS3d6XqHshB@ep-silent-forest-alx32mzu-pooler.c-3.eu-central-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
engine = create_engine(DB_POSTGRES_URL)

# =========================================================
# MODEL (lazy loading)
# =========================================================
_model = None

def get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model

# =========================================================
# TEXT CLEANING
# =========================================================
def clean_text(text):
    if not text:
        return ""

    text = text.lower().strip()
    text = unicodedata.normalize("NFKD", text)
    return "".join(c for c in text if not unicodedata.combining(c))

# =========================================================
# DATE PARSING
# =========================================================
def parse_date(date_str):
    if not date_str:
        return None
    return datetime.fromisoformat(date_str.replace("Z", "+00:00"))

# =========================================================
# CHARGEMENT DES DONNEES
# =========================================================
# Lit le fichier JSON contenant les offres d'emploi
def load_jobs():
    path = os.path.join(os.path.dirname(__file__), "out", "offres_emploi.json")
    
    if not os.path.exists(path):
        print("ERREUR: Fichier non trouve: " + path)
        return None

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if not data:
                print("ERREUR: Fichier JSON vide")
                return None
            print("OK: Charge " + str(len(data)) + " offres d emploi")
            return data
    except Exception as e:
        print("ERREUR lors de la lecture: " + str(e))
        return None


# =========================================================
# BUILD TEXT (embedding input)
# =========================================================
def build_text(job):
    competences = job.get("competences", [])

    # Extraction et nettoyage des compétences
    competences_text = " ".join(clean_text(c.get("libelle", "")) for c in competences)

    # Fusion des champs importants de l'offre
    # Les compétences ont un poids élevé (repetées 3 fois)
    return clean_text(
        f"{job.get('intitule', '')} "
        f"{job.get('romeLibelle', '')} "
        f"{competences_text} "
        f"{job.get('lieuTravail', {}).get('libelle', '')} "
        f"{job.get('description', '')}"
    )


# =========================================================
# EXTRACTION DES COMPETENCES
# =========================================================
def extract_competences(job):
    competences = job.get("competences", [])
    return [c.get("libelle", "").strip() for c in competences if c.get("libelle")]


# =========================================================
# EXTRACTION DU LIEU
# =========================================================
def extract_location(job):
    lieu = job.get("lieuTravail", {})
    if isinstance(lieu, dict):
        return lieu.get("libelle", "Non specifie")
    return str(lieu) if lieu else "Non specifie"


# =========================================================
# INITIALISATION BASE DE DONNEES
# =========================================================
# Crée la table si elle n'existe pas
# Stocke les embeddings vectoriels + date de mise à jour
def init_db():
    with engine.connect() as conn:
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

        conn.commit()


# =========================================================
# UPSERT EN BATCH
# =========================================================
# Insère ou met à jour les lignes en base
# Condition importante :
# - mise à jour uniquement si la nouvelle date est plus récente
def upsert_batch(rows):
    with engine.begin() as conn:
        conn.execute(text("""
        INSERT INTO jobs_embeddings (
            id,
            title,
            text,
            location,
            competences,
            date_actualisation,
            embedding
        )
        VALUES (
            :id,
            :title,
            :text,
            :location,
            :competences,
            :date_actualisation,
            :embedding
        )
        ON CONFLICT (id) DO UPDATE SET
            title = EXCLUDED.title,
            text = EXCLUDED.text,
            location = EXCLUDED.location,
            competences = EXCLUDED.competences,
            date_actualisation = EXCLUDED.date_actualisation,
            embedding = EXCLUDED.embedding
        WHERE EXCLUDED.date_actualisation > jobs_embeddings.date_actualisation;
        """), rows)


# =========================================================
# TRAITEMENT D'UN BATCH
# =========================================================
# - génère les embeddings en une seule fois (optimisation)
# - ajoute les vecteurs au buffer
# - envoie en base
def process_batch(buffer, texts, model):
    embeddings = model.encode(texts, normalize_embeddings=True)

    for i in range(len(buffer)):
        buffer[i]["embedding"] = embeddings[i].tolist()

    upsert_batch(buffer)


# =========================================================
# PIPELINE PRINCIPAL
# =========================================================
# - charge les données
# - traite par batch pour optimiser performance
# - calcule embeddings
# - insère en base
def run_pipeline(batch_size=64):

    print("Initialisation du pipeline...")
    init_db()

    jobs = load_jobs()
    if not jobs:
        print("Aucune donnee a traiter")
        return

    model = get_model()
    print("Modele charge - Traitement par batch de " + str(batch_size) + "...")

    buffer = []
    texts = []

    for job in jobs:
        text = build_text(job)
        location = extract_location(job)
        competences = extract_competences(job)

        # stockage des données à insérer
        buffer.append({
            "id": job["id"],
            "title": job.get("intitule"),
            "text": text,
            "location": location,
            "competences": competences,
            "date_actualisation": parse_date(job.get("dateActualisation"))
        })

        texts.append(text)

        # traitement par batch pour éviter surcharge mémoire / CPU
        if len(buffer) >= batch_size:
            process_batch(buffer, texts, model)
            buffer = []
            texts = []

    # traitement du dernier batch restant
    if buffer:
        process_batch(buffer, texts, model)

    print("Pipeline completed")


# =========================================================
# SEARCH STREAMING (core function)
# =========================================================
def search_stream(query, limit=10):
    query = clean_text(query)
    vec = get_model().encode([query], normalize_embeddings=True)[0].tolist()

    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT id, title, location, competences,
                   1 - (embedding <=> CAST(:v AS vector)) AS score
            FROM jobs_embeddings
            ORDER BY embedding <=> CAST(:v AS vector)
            LIMIT :limit;
        """), {"v": vec, "limit": limit})

        for row in result:
            yield {
                "id": row.id,
                "title": row.title,
                "location": row.location,
                "competences": list(row.competences) if row.competences else [],
                "score": float(row.score)
            }

# =========================================================
# STREAMING ENDPOINT (SSE)
# =========================================================
@app.get("/search-stream")
def stream_search(query: str, limit: int = 10):

    def event_generator():
        for result in search_stream(query, limit):
            yield f"data: {json.dumps(result)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream"
    )

# =========================================================
# OPTIONAL: NORMAL ENDPOINT (non-stream fallback)
# =========================================================
@app.get("/search")
def search_api(q: str = None, query: str = None, limit: int = 10):
    # Support both 'q' and 'query' parameters
    search_query = q or query
    if not search_query:
        return []
    return list(search_stream(search_query, limit))


# =========================================================
# WEB UI
# =========================================================
@app.get("/", response_class=HTMLResponse)
def ui():
    return """
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Recherche d'emploi - Semantic Search</title>
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                padding: 20px;
            }
            .container {
                background: white;
                border-radius: 12px;
                box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
                max-width: 800px;
                width: 100%;
                padding: 40px;
            }
            h1 {
                color: #333;
                margin-bottom: 10px;
                font-size: 28px;
            }
            .subtitle {
                color: #666;
                margin-bottom: 30px;
                font-size: 14px;
            }
            .search-box {
                display: flex;
                gap: 10px;
                margin-bottom: 30px;
            }
            input {
                flex: 1;
                padding: 12px 16px;
                border: 2px solid #e0e0e0;
                border-radius: 8px;
                font-size: 14px;
                transition: border-color 0.3s;
            }
            input:focus {
                outline: none;
                border-color: #667eea;
            }
            button {
                padding: 12px 24px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 14px;
                font-weight: 600;
                cursor: pointer;
                transition: transform 0.2s;
            }
            button:hover {
                transform: translateY(-2px);
            }
            button:active {
                transform: translateY(0);
            }
            .results {
                min-height: 200px;
            }
            .result-item {
                background: #f8f9fa;
                border-left: 4px solid #667eea;
                padding: 16px;
                margin-bottom: 12px;
                border-radius: 4px;
                transition: transform 0.2s, box-shadow 0.2s;
            }
            .result-item:hover {
                transform: translateX(4px);
                box-shadow: 0 4px 12px rgba(102, 126, 234, 0.15);
            }
            .result-title {
                font-weight: 600;
                color: #333;
                margin-bottom: 8px;
            }
            .result-score {
                font-size: 12px;
                color: #999;
            }
            .score-bar {
                width: 100%;
                height: 4px;
                background: #e0e0e0;
                border-radius: 2px;
                margin-top: 8px;
                overflow: hidden;
            }
            .score-fill {
                height: 100%;
                background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
                transition: width 0.3s;
            }
            .loading {
                text-align: center;
                color: #999;
                padding: 20px;
                font-size: 14px;
            }
            .error {
                background: #fee;
                color: #c33;
                padding: 16px;
                border-radius: 8px;
                margin-bottom: 20px;
                border-left: 4px solid #c33;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🔍 Recherche d'emploi</h1>
            <p class="subtitle">Recherche sémantique - Trouver les offres qui vous correspondent</p>

            <div class="search-box">
                <input 
                    id="query" 
                    type="text" 
                    placeholder="Ex: développeur python, data scientist..." 
                    onkeypress="if(event.key==='Enter') search()"
                >
                <button onclick="search()">Chercher</button>
            </div>

            <div id="results" class="results"></div>
        </div>

        <script>
            async function search() {
                const query = document.getElementById("query").value.trim();
                if (!query) return;

                const resultsDiv = document.getElementById("results");
                resultsDiv.innerHTML = '<div class="loading">⏳ Recherche en cours...</div>';

                try {
                    const response = await fetch(`/search?q=${encodeURIComponent(query)}`);
                    const data = await response.json();

                    if (!data || data.length === 0) {
                        resultsDiv.innerHTML = '<div class="loading">Aucun résultat trouvé</div>';
                        return;
                    }

                    resultsDiv.innerHTML = data.map(item => `
                        <div class="result-item">
                            <div class="result-title">${escapeHtml(item.title)}</div>
                            <div class="result-score">
                                Lieu: ${escapeHtml(item.location || "Non specifie")}
                            </div>
                            <div class="result-score">
                                Competences: ${item.competences && item.competences.length > 0 ? item.competences.slice(0, 5).join(", ") : "Non specifiees"}
                            </div>
                            <div class="result-score">Similarite: ${(item.score * 100).toFixed(1)}%</div>
                            <div class="score-bar">
                                <div class="score-fill" style="width: ${item.score * 100}%"></div>
                            </div>
                        </div>
                    `).join('');
                } catch (error) {
                    resultsDiv.innerHTML = `<div class="error">❌ Erreur: ${error.message}</div>`;
                }
            }

            function escapeHtml(text) {
                const map = {
                    '&': '&amp;',
                    '<': '&lt;',
                    '>': '&gt;',
                    '"': '&quot;',
                    "'": '&#039;'
                };
                return text.replace(/[&<>"']/g, m => map[m]);
            }

            // Focus sur l'input au chargement
            document.getElementById("query").focus();
        </script>
    </body>
    </html>
    """