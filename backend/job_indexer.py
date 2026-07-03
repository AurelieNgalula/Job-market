"""
Pipeline d'indexation : récupération des offres JSON, génération des embeddings,
insertion en base de données PostgreSQL avec pgvector.
"""

import json
import glob
import os
from datetime import datetime
from sqlalchemy import create_engine, text
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv

from utils import clean_text, parse_date, build_text, extract_competences, extract_location

load_dotenv()

# =========================================================
# DATABASE
# =========================================================
DB_POSTGRES_URL = (
    os.getenv("DB_POSTGRES_URL")
    or os.getenv("DATABASE_URL")
    or "postgresql://jobmarket:jobmarket_secure_password_123@postgres:5432/jobmarket_db"
)
engine = create_engine(DB_POSTGRES_URL, pool_pre_ping=True)

# =========================================================
# MODEL (lazy loading)
# =========================================================
_model = None

def get_model():
    """Charge le modèle d'embeddings (lazy loading)."""
    global _model
    if _model is None:
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


# =========================================================
# CHARGEMENT DES DONNEES
# =========================================================
def load_jobs():
    """Lit le fichier JSON le plus récent du dossier data/."""
    data_dir = os.path.join(os.path.dirname(__file__), "..", "data")
    
    if not os.path.isdir(data_dir):
        print(f"ERREUR: Dossier data/ introuvable: {data_dir}")
        return None

    json_files = sorted(glob.glob(os.path.join(data_dir, "*.json")))
    if not json_files:
        print("ERREUR: Aucun fichier JSON trouvé dans data/")
        return None

    path = json_files[-1]
    print(f"Chargement du fichier JSON: {path}")

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if not data:
                print("ERREUR: Fichier JSON vide")
                return None
            print(f"OK: Chargé {len(data)} offres d'emploi")
            return data
    except Exception as e:
        print(f"ERREUR lors de la lecture: {str(e)}")
        return None


# =========================================================
# INITIALISATION BASE DE DONNEES
# =========================================================
def init_db():
    """Crée la table jobs_embeddings si elle n'existe pas."""
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
        print("Base de données initialisée ✓")


# =========================================================
# UPSERT EN BATCH
# =========================================================
def upsert_batch(rows):
    """Insère ou met à jour les offres en base (mise à jour si date plus récente)."""
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
def process_batch(buffer, texts, model):
    """Génère les embeddings et insère en base."""
    embeddings = model.encode(texts, normalize_embeddings=True)

    for i in range(len(buffer)):
        buffer[i]["embedding"] = embeddings[i].tolist()

    upsert_batch(buffer)


# =========================================================
# PIPELINE PRINCIPAL
# =========================================================
def run_pipeline(batch_size=64):
    """
    Exécute le pipeline d'indexation complet :
    1. Initialise la base
    2. Charge les offres JSON
    3. Génère les embeddings par batch
    4. Insère en base PostgreSQL
    """
    print("Initialisation du pipeline...")
    init_db()

    jobs = load_jobs()
    if not jobs:
        print("Aucune donnée à traiter")
        return

    model = get_model()
    print(f"Modèle chargé - Traitement par batch de {batch_size}...")

    buffer = []
    texts = []

    for i, job in enumerate(jobs):
        text = build_text(job)
        location = extract_location(job)
        competences = extract_competences(job)

        buffer.append({
            "id": job["id"],
            "title": job.get("intitule"),
            "text": text,
            "location": location,
            "competences": competences,
            "date_actualisation": parse_date(job.get("dateActualisation"))
        })

        texts.append(text)

        # Traitement par batch
        if len(buffer) >= batch_size:
            process_batch(buffer, texts, model)
            buffer = []
            texts = []
            print(f"  Traité {i + 1}/{len(jobs)} offres...")

    # Traitement du dernier batch
    if buffer:
        process_batch(buffer, texts, model)
        print(f"  Traité {len(jobs)}/{len(jobs)} offres...")

    print("✓ Pipeline complété")


if __name__ == "__main__":
    run_pipeline()
