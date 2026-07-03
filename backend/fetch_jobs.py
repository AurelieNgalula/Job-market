"""
Script de récupération des offres d'emploi via l'API France Travail.
Sauvegarde les résultats dans data/YYYYMMDD_offres_emploi.json
"""

import json
import requests
import time
import datetime
import os

from utils import make_headers, get_with_reauth

# =========================================================
# CONFIGURATION
# =========================================================
GLOBAL_MAX_CREATION_DT = datetime.datetime.now(datetime.timezone.utc)
GLOBAL_MIN_CREATION_DT = GLOBAL_MAX_CREATION_DT - datetime.timedelta(hours=24)

print(f"Récupération des offres créées entre {GLOBAL_MIN_CREATION_DT.isoformat()} et {GLOBAL_MAX_CREATION_DT.isoformat()} (24 dernières heures)")

window_days = 0.05  # 12 heures
typeContrat = "CDI"
batch_size = 150
all_jobs = []

url = "https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search"

# =========================================================
# RÉCUPÉRATION PAR FENÊTRES TEMPORELLES
# =========================================================
headers = make_headers()

window_start = GLOBAL_MIN_CREATION_DT
while window_start < GLOBAL_MAX_CREATION_DT:
    window_end = min(window_start + datetime.timedelta(days=window_days), GLOBAL_MAX_CREATION_DT)

    min_iso = window_start.strftime("%Y-%m-%dT%H:%M:%SZ")
    max_iso = window_end.strftime("%Y-%m-%dT%H:%M:%SZ")

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
            res = get_with_reauth(url, headers, params, max_attempts=3, timeout=30)
        except requests.RequestException as e:
            print(f"Erreur requête pour la fenêtre {min_iso} -> {max_iso}: {e}")
            break

        if res is None:
            print(f"Aucune réponse pour la fenêtre {min_iso} -> {max_iso}")
            break

        if res.status_code == 401:
            print(f"401 persistante pour la fenêtre {min_iso} -> {max_iso}")
            break

        if res.status_code not in (200, 206):
            if res.status_code == 204:
                break  # Pas d'offres dans cette fenêtre
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

        time.sleep(0.5)

    window_start = window_end

# =========================================================
# SAUVEGARDE
# =========================================================
os.makedirs("../data", exist_ok=True)
date_prefix = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d")
output_path = f"../data/{date_prefix}_offres_emploi.json"

with open(output_path, "w", encoding="utf-8") as f:
    json.dump(all_jobs, f, ensure_ascii=False, indent=4)
    print(f"Total des offres récupérées: {len(all_jobs)}")
    print(f"✓ Résultats sauvegardés dans '{output_path}'")
