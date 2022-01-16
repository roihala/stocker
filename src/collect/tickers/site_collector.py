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
from src.common.otcm import REQUIRED_HEADERS
from src.common.proxy import get_proxy_auth, PROXY
from src.find.site import InvalidTickerExcpetion

logger = logging.getLogger('Collect')


class SiteCollector(TickerCollector, ABC):
    @property
    @abstractmethod
    def site(self):
        pass

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

            if self._debug:
                response = requests.get(url, headers=REQUIRED_HEADERS)
                if response.status_code == 200:
                    return response.json()
                else:
                    logger.error("Non existing ticker: {ticker}: {url} -> 404 error code".format(
                        ticker=self.ticker, url=url))
                    raise InvalidTickerExcpetion(self.ticker)
                
            # session = requests.Session()
            # session.auth = get_proxy_auth(self._debug)
            #
            # session.proxies = {"http": PROXY, "https": PROXY}
            # response = session.get(url, timeout=5, headers=REQUIRED_HEADERS)

            response = requests.get(url, headers=REQUIRED_HEADERS)

            if response.status_code == 404:
                logger.error("Non existing ticker: {ticker}: {url} -> 404 error code".format(
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
