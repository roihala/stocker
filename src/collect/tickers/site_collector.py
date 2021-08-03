import logging
import os
import pickle
import random
from abc import ABC, abstractmethod
from copy import deepcopy
from json import JSONDecodeError
from urllib.error import URLError

import requests
from redis import Redis
from requests import ReadTimeout
from requests.auth import HTTPProxyAuth
from retry import retry
from urllib3.exceptions import MaxRetryError, SSLError, NewConnectionError
from cachetools.func import ttl_cache
from src.collect.tickers.ticker_collector import TickerCollector
from src.find.site import InvalidTickerExcpetion

logger = logging.getLogger('Collect')
proxy = "http://zproxy.lum-superproxy.io:22225"

DAY_TTL = 60 * 60 * 24


@retry(tries=3, delay=2)
@ttl_cache(maxsize=2, ttl=DAY_TTL)
def get_ips():
    if os.getenv('ENV') == 'production':
        redis_cache = Redis(os.getenv('REDIS_IP'))
        result = redis_cache.get('PROXY_IPS')
        cached_ips = pickle.loads(result)
        return cached_ips
    else:
        res = requests.get("https://brightdata.com/api/zone/ips?zone=data_center",
                           headers={"Authorization": "Bearer 9a8bc5df8b0e14bc21f1ca755f37714d"})
        return res.json()['ips']


get_ips()


class SiteCollector(TickerCollector, ABC):
    @property
    @abstractmethod
    def site(self):
        pass

    @staticmethod
    def get_random_ip():
        ips = get_ips()
        ip = random.choice(ips)
        return ip['ip']

    @staticmethod
    def get_proxy_auth():
        username = 'lum-customer-c_050c0806-zone-data_center'
        password = '/ykw+71y9e~o'
        ip = SiteCollector.get_random_ip()
        auth = HTTPProxyAuth("%s-ip-%s" % (username, ip), password)
        return auth

    @retry((JSONDecodeError, requests.exceptions.ProxyError, ReadTimeout, MaxRetryError, SSLError, URLError,
            NewConnectionError), tries=12,
           delay=0.25)
    def fetch_data(self, data=None) -> dict:
        """
        Fetching data by using requests.get

        * Retrying up to 3 times if requests fails to parse the result as json.

        :param data: (optional) You can transfer data in order to prevent fetching again.
        (Can be used in father-son relations

        :return: A dict containing the newly fetched entry
        """
        if not data:
            url = self.site.get_ticker_url(self.ticker)
            session = requests.Session()
            session.auth = self.get_proxy_auth()

            session.proxies = {"http": proxy, "https": proxy}
            response = session.get(url, timeout=5)

            if response.status_code == 404:
                logger.warning("Non existing ticker: {ticker}: {url} -> 404 error code".format(
                    ticker=self.ticker, url=url))
                raise InvalidTickerExcpetion(self.ticker)

            if response.status_code == 429:
                logger.warning("Can't collect {ticker}: {url} -> responsne code: {code}".format(
                    ticker=self.ticker, url=url, code=response.status_code))
                raise requests.exceptions.ProxyError()

            if 500 <= response.status_code <= 599:
                logger.warning("Can't collect {ticker}: {url} -> responsne code: {code}".format(
                    ticker=self.ticker, url=url, code=response.status_code))
                raise ReadTimeout()

            if response.status_code != 200:
                logger.warning("Can't collect {ticker}: {url} -> responsne code: {code}".format(
                    ticker=self.ticker, url=url, code=response.status_code))
                raise InvalidTickerExcpetion(self.ticker, response.status_code)

            data = response.json()

            self._raw_data = deepcopy(data)

        return data
