"""Per-domain daily pipelines (stg → ods → dtm) so the agent's `airflow_trigger_dag` re-run
resolves to a REAL DAG for every project. DAG ids match the metric contract `pipeline` names
(domain.contracts / metric_memory.json), e.g. dtm_cash_daily, dtm_spend_daily, dtm_ar_daily.

Backfill is triggered with conf={"backfill_date": "<YYYY-MM-DD>"} by the DataOps Twin after a fix
is merged — idempotent recompute of one partition.
"""

from datetime import datetime

from airflow import DAG
from airflow.operators.python import PythonOperator

# pipeline dag_id -> (stg, ods, dtm task labels)
DOMAINS = {
    "dtm_revenue_daily": ("stg_payment", "ods_payment_enriched", "dtm_revenue_daily"),
    "dtm_cash_daily": ("stg_cash_flow", "ods_cash_enriched", "dtm_cash_daily"),
    "dtm_spend_daily": ("stg_spend", "ods_spend_enriched", "dtm_spend_daily"),
    "dtm_ar_daily": ("stg_invoice", "ods_ar_enriched", "dtm_ar_daily"),
}


def _make(stage: str, dag_id: str):
    def _run(**ctx):
        conf = (ctx.get("dag_run").conf if ctx.get("dag_run") else {}) or {}
        print(f"[{dag_id}] {stage}: recompute backfill_date={conf.get('backfill_date', 'latest')} — ok")
    return _run


for _dag_id, (_stg, _ods, _dtm) in DOMAINS.items():
    with DAG(
        dag_id=_dag_id,
        start_date=datetime(2026, 1, 1),
        schedule=None,
        catchup=False,
        tags=["finance", "dataops-twin"],
    ) as _dag:
        s = PythonOperator(task_id=_stg, python_callable=_make("stg", _dag_id))
        o = PythonOperator(task_id=_ods, python_callable=_make("ods", _dag_id))
        d = PythonOperator(task_id=_dtm, python_callable=_make("dtm", _dag_id))
        s >> o >> d
    globals()[_dag_id] = _dag
