from airflow import DAG
from airflow.models import Variable
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.decorators import task

from datetime import datetime
from datetime import timedelta

import requests
import logging
import json


def get_Redshift_connection():
    # autocommit is False by default
    hook = PostgresHook(postgres_conn_id='redshift_dev_db')
    return hook.get_conn().cursor()

@task
def etl(schema, table):
    api_key = Variable.get("open_weather_api_key") # or api_key = "open_weather_api_key"
    lat_mon_list = [
        {"name" : "도쿄", "lat" : 35.6894 , "lon" : 139.6917},
        {"name" : "오사카", "lat" : 34.6937 , "lon" : 135.5022},
        {"name" : "삿포로", "lat" : 43.0621 , "lon" : 141.3544},
        {"name" : "후쿠오카", "lat" : 33.5903 , "lon" : 130.4017},
        {"name" : "교토", "lat" : 35.0116 , "lon" : 135.7680},
        {"name" : "오키나와", "lat" : 26.2124 , "lon" : 127.6809}
    ]
    
    ret = []
    for city in lat_mon_list:
        # 각각의 위도 경도
        lat = city["lat"]
        lon = city["mon"]

        # https://openweathermap.org/forecast5
        url = f"https://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&appid={api_key}"
        response = requests.get(url)
        data = json.loads(response.text)
        
        for d in data["list"]:
            day = datetime.fromtimestamp(d["dt"]).strftime('%Y-%m-%d %H')
            weather = d["weater"]["description"]
            ret.append("({},{})".format(day, weather))

    cur = get_Redshift_connection()
    drop_recreate_sql = f"""DROP TABLE IF EXISTS {schema}.{table};
CREATE TABLE {schema}.{table} (
    date date,
    weater str,
    created_date timestamp default GETDATE()
);
"""
    insert_sql = f"""INSERT INTO {schema}.{table} VALUES """ + ",".join(ret)
    logging.info(drop_recreate_sql)
    logging.info(insert_sql)
    try:
        cur.execute(drop_recreate_sql)
        cur.execute(insert_sql)
        cur.execute("Commit;")
    except Exception as e:
        cur.execute("Rollback;")
        raise

with DAG(
    dag_id = 'jp_weather',
    start_date = datetime(2024,7,1), # 날짜가 미래인 경우 실행이 안됨
    schedule = '0 * * * *',  # 적당히 조절
    max_active_runs = 1,
    catchup = False,
    default_args = {
        'retries': 1,
        'retry_delay': timedelta(minutes=3),
    }
) as dag:

    etl("dev", "weather_forecast")