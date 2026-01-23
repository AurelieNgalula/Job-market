import http.client
import json 
import requests
from utils import get_access_token
import time

#utlis.py
access_token = get_access_token()

conn = http.client.HTTPSConnection("api.francetravail.io")

headers = {
    'Authorization': f"Bearer {access_token}",
    'Accept': "application/json"
}

batch_size = 150
start = 0
all_jobs = []

while True:

    end=start + batch_size - 1
    conn.request("GET", f"/partenaire/offresdemploi/v2/offres/search?typeContrat=CDI&tempsPlein=true&departement=75&range={start}-{end}", headers=headers)

    res = conn.getresponse()

    data = res.read()

    data_json = json.loads(data.decode("utf-8"))

    jobs = data_json.get("resultats", [])

    if not jobs:
        break

    all_jobs.extend(jobs)

    content_range = res.getheader("Content-Range")
    try:
        total_jobs = int(content_range.split("/")[1])

    except (IndexError, ValueError, TypeError):
        total_jobs = len(all_jobs)

    start += batch_size

    if start >= total_jobs:
        break

    time.sleep(0.5)  # Pour éviter de surcharger l'API

# Sauvegarde dans un fichier JSON
with open("out/offres_emploi.json", "w", encoding="utf-8") as f:
    json.dump(all_jobs, f, ensure_ascii=False, indent=4)
    print(f"Total des offres récupérées: {len(all_jobs)}")
    print("Les résultats ont été sauvegardés dans 'offres_emploi.json'.")
