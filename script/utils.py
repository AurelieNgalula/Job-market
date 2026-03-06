from dotenv import load_dotenv
import os
import requests
import time
from typing import Optional

# recuperer les infor dans le fichier .env
load_dotenv()

CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")

TOKEN_URL = "https://entreprise.francetravail.fr/connexion/oauth2/access_token?realm=/partenaire"

# Scopes requis pour offres d'emploi
SCOPES = "o2dsoffre api_offresdemploiv2"


def get_access_token():
    """
    Récupère un access_token en utilisant le Client Credentials Flow OAuth2.
    """
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


def _make_headers(token: Optional[str] = None) -> dict:
    """
    Crée les headers d'authentification pour les requêtes API.
    
    Args:
        token (Optional[str]): Token OAuth2. Si None, le récupère automatiquement.
    
    Returns:
        dict: Headers avec Authorization et Accept.
    """
    if token is None:
        token = get_access_token()
    return {
        'Authorization': f"Bearer {token}",
        'Accept': "application/json"
    }


def _get_with_reauth(
    url: str,
    headers: dict,
    params: dict,
    max_attempts: int = 3,
    timeout: int = 30
) -> Optional[requests.Response]:
    """
    Effectue une requête GET avec gestion automatique du rafraîchissement du token en cas de 401.
    
    Args:
        url (str): URL de l'API.
        headers (dict): Headers de la requête (sera modifié si le token est rafraîchi).
        params (dict): Paramètres de la requête.
        max_attempts (int): Nombre maximal de tentatives (défaut: 3).
        timeout (int): Timeout en secondes (défaut: 30).
    
    Returns:
        Optional[requests.Response]: Objet Response ou None en cas d'erreur persistante.
    """
    attempt = 0
    while attempt < max_attempts:
        attempt += 1
        try:
            res = requests.get(url, headers=headers, params=params, timeout=timeout)
        except requests.RequestException as e:
            print(f"Erreur réseau lors de la requête (essai {attempt}/{max_attempts}): {e}")
            if attempt < max_attempts:
                time.sleep(1 * attempt)
                continue
            raise

        if res.status_code == 401:
            print(f"401 Unauthorized — tentative de rafraîchissement du token (essai {attempt}/{max_attempts})")
            try:
                new_token = get_access_token()
                headers['Authorization'] = f"Bearer {new_token}"
            except Exception as e:
                print("Échec du rafraîchissement du token:", e)
                # attendre avant la prochaine tentative
                time.sleep(1 * attempt)
                continue
            # backoff avant le retry
            time.sleep(0.5 * attempt)
            continue

        return res

    # si on sort de la boucle, retourner la dernière réponse (probablement 401)
    return res
