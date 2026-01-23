from dotenv import load_dotenv
import os
import requests

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
