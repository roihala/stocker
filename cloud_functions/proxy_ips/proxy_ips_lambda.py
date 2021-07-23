import os
import pickle

import requests
from redis import Redis
import logging


def get_proxy_ips():
    res = requests.get("https://brightdata.com/api/zone/ips?zone=data_center",
                       headers={"Authorization": "Bearer 9a8bc5df8b0e14bc21f1ca755f37714d"}, timeout=60)
    print("Success!")
    result = res.json()['ips']
    return result


def update_proxy_ips():
    try:
        redis_cache = Redis(host=os.getenv('REDIS_IP', 'localhost'))
        ips = get_proxy_ips()
        pickled = pickle.dumps(ips)

        TIME_TO_EXPIRE_TWO_DAYS = 60 * 60 * 24 * 2
        KEY = "PROXY_IPS"
        result = redis_cache.set(KEY, pickled, ex=TIME_TO_EXPIRE_TWO_DAYS)
        print(result)
    except Exception as e:
        logging.exception(e)


def run(event, context):
    update_proxy_ips()
