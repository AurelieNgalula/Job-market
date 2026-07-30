"""
Fonctions utilitaires partagées pour le projet job-market.
Incluent:
- Nettoyage de texte
- Extraction de données
- OAuth2 & requêtes API
"""

import unicodedata
import requests
import time
import os
from datetime import datetime
from typing import Optional
try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    from dotenv import dotenv_values

    def load_dotenv(*args, **kwargs):
        return dotenv_values(*args, **kwargs)

load_dotenv()

# =========================================================
# CONFIGURATION OAUTH2
# =========================================================
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
TOKEN_URL = "https://entreprise.francetravail.fr/connexion/oauth2/access_token?realm=/partenaire"
SCOPES = "o2dsoffre api_offresdemploiv2"


# =========================================================
# TEXT CLEANING
# =========================================================
def clean_text(text):
    """Normalise et nettoie un texte (minuscule, accents, etc)."""
    if not text:
        return ""
    
    text = text.lower().strip()
    text = unicodedata.normalize("NFKD", text)
    return "".join(c for c in text if not unicodedata.combining(c))


# =========================================================
# DATE PARSING
# =========================================================
def parse_date(date_str):
    """Parse une date ISO 8601 avec timezone."""
    if not date_str:
        return None
    return datetime.fromisoformat(date_str.replace("Z", "+00:00"))


# =========================================================
# JOB DATA EXTRACTION
# =========================================================
def build_text(job):
    """Construit le texte pour l'embedding à partir d'une offre."""
    competences = job.get("competences", [])
    competences_text = " ".join(clean_text(c.get("libelle", "")) for c in competences)
    
    return clean_text(
        f"{job.get('intitule', '')} "
        f"{job.get('romeLibelle', '')} "
        f"{competences_text} "
        f"{job.get('description', '')}"
    )


def extract_competences(job):
    """Extrait les compétences d'une offre."""
    competences = job.get("competences", [])
    return [c.get("libelle", "").strip() for c in competences if c.get("libelle")]


def extract_location(job):
    """Extrait le lieu de travail d'une offre."""
    lieu = job.get("lieuTravail", {})
    if isinstance(lieu, dict):
        return lieu.get("libelle", "Non specifie")
    return str(lieu) if lieu else "Non specifie"


# =========================================================
# OAUTH2 & API REQUESTS
# =========================================================
def get_access_token():
    """Récupère un access_token OAuth2 (Client Credentials Flow)."""
    data = {
        "grant_type": "client_credentials",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "scope": SCOPES
    }
    
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json"
    }

    response = requests.post(TOKEN_URL, data=data, headers=headers)
    response.raise_for_status()
    token_data = response.json()
    
    access_token = token_data.get("access_token")
    expires_in = token_data.get("expires_in")
    
    print(f"Token obtenu (valide {expires_in}s)")
    return access_token


def make_headers(token: Optional[str] = None) -> dict:
    """Crée les headers d'authentification pour les requêtes API."""
    if token is None:
        token = get_access_token()
    return {
        'Authorization': f"Bearer {token}",
        'Accept': "application/json"
    }


def get_with_reauth(
    url: str,
    headers: dict,
    params: dict,
    max_attempts: int = 3,
    timeout: int = 30
) -> Optional[requests.Response]:
    """
    Effectue une requête GET avec gestion automatique du token.
    Rafraîchit le token en cas de 401.
    """
    attempt = 0
    while attempt < max_attempts:
        attempt += 1
        try:
            res = requests.get(url, headers=headers, params=params, timeout=timeout)
        except requests.RequestException as e:
            print(f"Erreur réseau (essai {attempt}/{max_attempts}): {e}")
            if attempt < max_attempts:
                time.sleep(1 * attempt)
                continue
            raise

        if res.status_code == 401:
            print(f"401 Unauthorized — rafraîchissement du token (essai {attempt}/{max_attempts})")
            try:
                new_token = get_access_token()
                headers['Authorization'] = f"Bearer {new_token}"
            except Exception as e:
                print("Échec du rafraîchissement:", e)
                time.sleep(1 * attempt)
                continue
            
            time.sleep(0.5 * attempt)
            continue

        return res

    return res
