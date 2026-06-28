import glob
import json
import unicodedata
import os
from datetime import datetime

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sentence_transformers import SentenceTransformer

load_dotenv()


# =========================================================
# CONNEXION BASE DE DONNEES
# =========================================================
# Connexion PostgreSQL via SQLAlchemy
# Utilisée pour stocker les embeddings et les offres
DB_POSTGRES_URL = os.getenv("DB_POSTGRES_URL") or os.getenv(
    "DATABASE_URL",
    "postgresql://jobmarket:jobmarket_secure_password_123@postgres:5432/jobmarket_db"
)
engine = create_engine(DB_POSTGRES_URL)


# =========================================================
# CHARGEMENT DU MODELE D'EMBEDDINGS
# =========================================================
# Le modèle est chargé une seule fois (lazy loading)
# pour éviter de ralentir le démarrage du script
_model = None

def get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


# =========================================================
# NETTOYAGE DU TEXTE
# =========================================================
# Normalisation du texte pour améliorer la qualité des embeddings
# - minuscule
# - suppression des accents
# - suppression des caractères spéciaux Unicode
def clean_text(text):
    if not text:
        return ""

    text = text.lower().strip()
    text = unicodedata.normalize("NFKD", text)
    return "".join(c for c in text if not unicodedata.combining(c))


# =========================================================
# CONVERSION DES DATES
# =========================================================
# Convertit une date ISO JSON en objet datetime Python
def parse_date(date_str):
    if not date_str:
        return None
    return datetime.fromisoformat(date_str.replace("Z", "+00:00"))


# =========================================================
# CHARGEMENT DES DONNEES
# =========================================================
# Lit le fichier JSON contenant les offres d'emploi
def load_jobs():
    out_dir = os.path.join(os.path.dirname(__file__), "out")
    if not os.path.isdir(out_dir):
        print("ERREUR: Dossier out/ introuvable: " + out_dir)
        return None

    json_files = sorted(glob.glob(os.path.join(out_dir, "*.json")))
    if not json_files:
        print("ERREUR: Aucun fichier JSON trouve dans out/")
        return None

    path = json_files[-1]
    print("Chargement du fichier JSON: " + path)

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
    processed = 0

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
            processed += len(buffer)
            print("OK: " + str(processed) + "/" + str(len(jobs)) + " offres traitees...")
            buffer = []
            texts = []

    # traitement du dernier batch restant
    if buffer:
        process_batch(buffer, texts, model)
        processed += len(buffer)

    print("OK: Pipeline termine: " + str(processed) + " offres indexees")


# =========================================================
# RECHERCHE SEMANTIQUE
# =========================================================
# Compare la requête utilisateur avec les embeddings stockés
# Utilise la distance cosinus via pgvector
def search(query):
    if not query:
        return []
    
    query = clean_text(query)
    
    try:
        vec = get_model().encode([query], normalize_embeddings=True)[0].tolist()

        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT id, title, location, competences,
                       1 - (embedding <=> CAST(:v AS vector)) AS score
                FROM jobs_embeddings
                ORDER BY embedding <=> CAST(:v AS vector)
                LIMIT 10;
            """), {"v": vec})

            return [dict(r._mapping) for r in result.fetchall()]
    except Exception as e:
        print("ERREUR recherche: " + str(e))
        return []


# =========================================================
# EXECUTION PRINCIPALE
# =========================================================
# - lance le pipeline d'ingestion
# - permet ensuite de tester la recherche en boucle
if __name__ == "__main__":
    import sys

    print("=" * 60)
    print("JOB MARKET - Recherche Semantique d Emploi")
    print("=" * 60)
    
    run_pipeline(batch_size=64)

    if sys.stdin.isatty():
        print("\nMode interactif - Tapez exit pour quitter\n")
        
        while True:
            try:
                q = input("Recherche (exit pour quitter): ").strip()
                
                if q.lower() == "exit":
                    print("Au revoir!")
                    break
                
                if not q:
                    print("Veuillez entrer une recherche\n")
                    continue

                results = search(q)

                if not results:
                    print("Aucun resultat trouve\n")
                    continue
                
                print("\nOK: " + str(len(results)) + " resultat(s) trouve(s):\n")
                
                for i, r in enumerate(results, 1):
                    print(str(i) + ". " + r["title"])
                    print("   Lieu: " + str(r.get("location", "Non specifie")))
                    
                    competences = r.get("competences")
                    if competences and isinstance(competences, list):
                        print("   Competences: " + ", ".join(competences[:5]))
                    
                    score = r.get("score", 0)
                    print("   Score: " + str(round(score, 3)) + " (" + str(round(score*100, 1)) + "%)")
                    print("")
            
            except KeyboardInterrupt:
                print("\nArret...")
                break
            except Exception as e:
                print("ERREUR: " + str(e) + "\n")
    else:
        print("Pas de terminal interactif : fin du process.")