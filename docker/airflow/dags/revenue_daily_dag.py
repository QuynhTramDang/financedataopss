"""DAG demo mô phỏng pipeline 3 tầng stg → ods → dtm (để M1 đọc trạng thái task thật).

Toggle lỗi ở tầng ODS (đúng nơi bug refund mapping) để mô phỏng task fail:
    Airflow → Admin → Variables → FAIL_ODS = 1   (hoặc `airflow variables set FAIL_ODS 1`)
"""

from datetime import datetime

from airflow import DAG
from airflow.models import Variable
from airflow.operators.python import PythonOperator


def _stg():
    print("stg_payment: làm sạch payment_txn — ok")


def _ods():
    if Variable.get("FAIL_ODS", default_var="0") == "1":
        raise ValueError("ODS refund mapping bug: PARTIAL_REFUND chưa map (demo fail)")
    print("ods_payment_enriched: join + map refund — ok")


def _dtm():
    print("dtm_revenue_daily: aggregate net_revenue — ok")


with DAG(
    dag_id="revenue_daily",
    start_date=datetime(2026, 1, 1),
    schedule=None,
    catchup=False,
    tags=["finance"],
) as dag:
    stg = PythonOperator(task_id="stg_payment", python_callable=_stg)
    ods = PythonOperator(task_id="ods_payment_enriched", python_callable=_ods)
    dtm = PythonOperator(task_id="dtm_revenue_daily", python_callable=_dtm)
    stg >> ods >> dtm
