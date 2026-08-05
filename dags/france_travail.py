import sys
from pathlib import Path

import pendulum

from airflow import DAG
from airflow.operators.python import PythonOperator

# Ajout du dossier scripts au chemin d'import pour les DAGs Airflow
SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.append(str(SCRIPTS_DIR))

from get_offres import collect_offres
from indexation_offres import run_pipeline

# Fuseau horaire France
local_tz = "Europe/Paris"

# Paramètres par défaut
default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "retries": 2,
    "retry_delay": 300,  # 5 minutes
}

with DAG(
    dag_id="france_travail_pipeline",
    description="Collecte des offres France Travail puis indexation dans PostgreSQL",
    default_args=default_args,
    start_date=pendulum.datetime(2026, 1, 1, tz=local_tz),
    schedule="0 22 * * *",          # Tous les jours à 22h00
    catchup=False,
    max_active_runs=1,
    tags=["france-travail", "embeddings"],
) as dag:

    # =====================================================
    # Tâche 1 : Collecte des offres
    # =====================================================
    collecte_offres = PythonOperator(
        task_id="collecte_offres",
        python_callable=collect_offres,
    )

    # =====================================================
    # Tâche 2 : Génération des embeddings + insertion BDD
    # =====================================================
    indexation_offres = PythonOperator(
        task_id="indexation_offres",
        python_callable=run_pipeline,
        op_kwargs={
            "batch_size": 32,
        },
    )
    

    # =====================================================
    # Ordre d'exécution
    # =====================================================
    collecte_offres >> indexation_offres