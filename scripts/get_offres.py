"""
Collecte des offres France Travail.

Récupère les offres créées dans les dernières 24h
et les sauvegarde dans data/YYYYMMDD_offres_emploi.json
"""

import json
import os
import time
import datetime
import requests

from utils import make_headers, get_with_reauth


def collect_offres():

    # ==========================================================
    # CONFIGURATION
    # ==========================================================
    global_max_creation_dt = datetime.datetime.now(datetime.timezone.utc)
    global_min_creation_dt = global_max_creation_dt - datetime.timedelta(hours=24)

    print(
        f"Récupération des offres créées entre "
        f"{global_min_creation_dt.isoformat()} et "
        f"{global_max_creation_dt.isoformat()}"
    )

    window_hours = 1          
    batch_size = 150
    type_contrat = "CDI"

    url = "https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search"

    headers = make_headers()

    all_jobs = []

    # ==========================================================
    # RÉCUPÉRATION DES DONNÉES
    # ==========================================================
    window_start = global_min_creation_dt

    while window_start < global_max_creation_dt:

        window_end = min(
            window_start + datetime.timedelta(hours=window_hours),
            global_max_creation_dt,
        )

        min_iso = window_start.strftime("%Y-%m-%dT%H:%M:%SZ")
        max_iso = window_end.strftime("%Y-%m-%dT%H:%M:%SZ")

        print(f"Fenêtre : {min_iso} -> {max_iso}")

        start = 0

        while True:

            end = start + batch_size - 1

            params = {
                "typeContrat": type_contrat,
                "minCreationDate": min_iso,
                "maxCreationDate": max_iso,
                "range": f"{start}-{end}",
            }

            try:
                response = get_with_reauth(
                    url=url,
                    headers=headers,
                    params=params,
                    max_attempts=3,
                    timeout=30,
                )

            except requests.RequestException as e:
                print(f"Erreur : {e}")
                break

            if response is None:
                print("Aucune réponse.")
                break

            if response.status_code == 401:
                print("Erreur 401.")
                break

            if response.status_code == 204:
                break

            if response.status_code not in (200, 206):
                print(f"Erreur HTTP {response.status_code}")
                break

            try:
                data = response.json()
            except ValueError:
                print("JSON invalide.")
                break

            jobs = data.get("resultats", [])

            if not jobs:
                break

            all_jobs.extend(jobs)

            content_range = response.headers.get("Content-Range")

            try:
                total_jobs = (
                    int(content_range.split("/")[1])
                    if content_range
                    else len(all_jobs)
                )
            except Exception:
                total_jobs = len(all_jobs)

            start += batch_size

            if start >= total_jobs:
                break

            time.sleep(0.5)

        window_start = window_end

    # ==========================================================
    # SAUVEGARDE
    # ==========================================================

    data_dir= os.environ.get("DATA_DIR", os.path.join(os.path.dirname(__file__), "..", "data"))
    incoming_dir = os.path.join(data_dir, "incoming")

    os.makedirs(incoming_dir, exist_ok=True)

    date_prefix = datetime.datetime.now(
        datetime.timezone.utc
    ).strftime("%Y%m%d%H%M%S")

    output_path = os.path.join(
        incoming_dir,
        f"{date_prefix}_offres_emploi.json",
    )

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_jobs, f, ensure_ascii=False, indent=4)

    print("=" * 60)
    print(f"Nombre total d'offres : {len(all_jobs)}")
    print(f"Fichier créé : {output_path}")
    print("=" * 60)

    return output_path


if __name__ == "__main__":
    collect_offres()