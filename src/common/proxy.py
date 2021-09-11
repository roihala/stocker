import os
import pickle
import random
from urllib.error import URLError

import requests
from cachetools.func import ttl_cache
from redis import Redis
from requests import ReadTimeout
from requests.auth import HTTPProxyAuth
from retry import retry
from urllib3.exceptions import MaxRetryError, NewConnectionError, SSLError

from src.common.otcm import REQUIRED_HEADERS

DAY_TTL = 60 * 60 * 24
REDIS_IP = "10.80.176.3"
PROXY = "http://zproxy.lum-superproxy.io:22225"


@retry(tries=3, delay=2)
@ttl_cache(maxsize=2, ttl=DAY_TTL)
def get_ips(is_debug):
    if not is_debug:
        redis_cache = Redis(REDIS_IP)
        result = redis_cache.get('PROXY_IPS')
        cached_ips = pickle.loads(result)
        return cached_ips
    else:
        res = requests.get("https://brightdata.com/api/zone/ips?zone=data_center",
                           headers={"Authorization": "Bearer 9a8bc5df8b0e14bc21f1ca755f37714d"})
        return res.json()['ips']


def get_random_ip(is_debug):
    ips = get_ips(is_debug)
    ip = random.choice(ips)
    return ip['ip']


def get_proxy_auth(is_debug):
    username = 'lum-customer-c_050c0806-zone-data_center'
    password = '/ykw+71y9e~o'
    ip = get_random_ip(is_debug)
    auth = HTTPProxyAuth("%s-ip-%s" % (username, ip), password)
    return auth


@retry((requests.exceptions.ProxyError, ReadTimeout, MaxRetryError, SSLError, URLError,
        NewConnectionError), tries=3, delay=0.25)
def proxy_get(url, is_debug, headers=None) -> requests.models.Response:
    if is_debug:
        return requests.get(url, headers=headers)

    session = requests.Session()
    session.auth = get_proxy_auth(is_debug)

    session.proxies = {"http": PROXY, "https": PROXY}
    response = session.get(url, timeout=5, headers=headers)

    if response.status_code == 429:
        raise requests.exceptions.ProxyError()

    if 500 <= response.status_code <= 599:
        raise ReadTimeout()

    return response
