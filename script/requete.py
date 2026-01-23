import http.client
import json 
import os
import requests
from utils import get_access_token

#utlis.py
access_token = get_access_token()

conn = http.client.HTTPSConnection("api.francetravail.io")

headers = {
    'Authorization': f"Bearer {access_token}",
    'Accept': "application/json"
}

conn.request("GET", "/partenaire/offresdemploi/v2/offres/search?typeContrat=CDI&tempsPlein=true&departement=75", headers=headers)

res = conn.getresponse()
data = res.read()

# Décodage des données JSON
data_json = json.loads(data.decode("utf-8"))

# Sauvegarde dans un fichier JSON
with open("out/offres_emploi.json", "w", encoding="utf-8") as f:
    json.dump(data_json, f, ensure_ascii=False, indent=4)

print("Les résultats ont été sauvegardés dans 'offres_emploi.json'.")