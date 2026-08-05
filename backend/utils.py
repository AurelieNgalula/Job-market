"""
Fonctions utilitaires partagées pour le projet job-market.
Incluent:
- Nettoyage de texte
- Chargement du modèle
- Initialisation de la table PGVector
"""

import os
import unicodedata
from sqlalchemy import create_engine, text
from sentence_transformers import SentenceTransformer
import re
try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    from dotenv import dotenv_values

    def load_dotenv(*args, **kwargs):
        return dotenv_values(*args, **kwargs)

load_dotenv()

DB_POSTGRES_URL = (
    os.getenv("DB_POSTGRES_URL")
    or os.getenv("DATABASE_URL")
)

if not DB_POSTGRES_URL:
    raise ValueError("DB_POSTGRES_URL is not set in environment variables.")

engine = create_engine(DB_POSTGRES_URL, pool_pre_ping=True)

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
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;")) # activer l'extension vector si elle n'existe pas
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
# TEXT CLEANING
# =========================================================

def clean_text(text):
    """Normalise et nettoie un texte (minuscule, accents, etc)."""
    if not text:
        return ""
    
    text = text.lower().strip()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()

