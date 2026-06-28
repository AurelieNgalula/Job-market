import json 
import requests
from utils import get_access_token, _make_headers, _get_with_reauth
import time
import datetime
import os

# Créer les headers d'authentification
headers = _make_headers()

# bornes globales (datetime objects) pour les 24 dernières heures
GLOBAL_MAX_CREATION_DT = datetime.datetime.now(datetime.timezone.utc)
GLOBAL_MIN_CREATION_DT = GLOBAL_MAX_CREATION_DT - datetime.timedelta(hours=24)

print(f"Récupération des offres créées entre {GLOBAL_MIN_CREATION_DT.isoformat()} et {GLOBAL_MAX_CREATION_DT.isoformat()} (24 dernières heures)")
# configuration : taille de la fenêtre en jours (modifiable)
window_days = 0.05  # 12 heures, change to 1 pour travailler par jours

typeContrat = "CDI" # ou "CDI"

batch_size = 150 # nombre d'offres par page (max 150 selon la doc API)
all_jobs = []

url = "https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search"

# boucle sur les fenêtres temporelles entre GLOBAL_MIN_CREATION_DT et GLOBAL_MAX_CREATION_DT
window_start = GLOBAL_MIN_CREATION_DT
while window_start < GLOBAL_MAX_CREATION_DT:
    window_end = min(window_start + datetime.timedelta(days=window_days), GLOBAL_MAX_CREATION_DT)

    # format ISO attendue par l'API
    min_iso = window_start.strftime("%Y-%m-%dT%H:%M:%SZ")
    max_iso = window_end.strftime("%Y-%m-%dT%H:%M:%SZ")

    # pagination pour cette fenêtre
    start = 0
    while True:
        end = start + batch_size - 1
        params = {
            "typeContrat": typeContrat,
            "minCreationDate": min_iso,
            "maxCreationDate": max_iso,
            "range": f"{start}-{end}"
        }

        try:
            res = _get_with_reauth(url, headers, params, max_attempts=3, timeout=30)
        except requests.RequestException as e:
            print(f"Erreur requête pour la fenêtre {min_iso} -> {max_iso}: {e}")
            break

        if res is None:
            print(f"Aucune réponse pour la fenêtre {min_iso} -> {max_iso}")
            break

        if res.status_code == 401:
            print(f"401 persistante pour la fenêtre {min_iso} -> {max_iso} après tentatives de rafraîchissement ; on passe à la fenêtre suivante")
            break

        if res.status_code not in (200, 206):
            if res.status_code == 204:
                break  # Pas d'offres dans cette fenêtre, passer à la suivante               
            print(f"Réponse HTTP {res.status_code} pour la fenêtre {min_iso} -> {max_iso}")
            break

        try:
            data_json = res.json()
        except ValueError:
            print("Impossible de parser la réponse JSON")
            break

        jobs = data_json.get("resultats", [])

        if not jobs:
            break

        all_jobs.extend(jobs)

        content_range = res.headers.get("Content-Range")
        try:
            total_jobs = int(content_range.split("/")[1]) if content_range else len(all_jobs)
        except (IndexError, ValueError, TypeError):
            total_jobs = len(all_jobs)

        start += batch_size
        if start >= total_jobs:
            break

        time.sleep(0.5)  # Pour éviter de surcharger l'API

    # avancer à la fenêtre suivante
    window_start = window_end

# Sauvegarde dans un fichier JSON
os.makedirs("out", exist_ok=True)
date_prefix = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d")
output_path = f"out/{date_prefix}_offres_emploi.json"
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(all_jobs, f, ensure_ascii=False, indent=4)
    print(f"Total des offres récupérées: {len(all_jobs)}")
    print(f"Les résultats ont été sauvegardés dans '{output_path}'.")