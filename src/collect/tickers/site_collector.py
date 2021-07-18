import logging
import requests
from abc import ABC, abstractmethod
from copy import deepcopy
from json import JSONDecodeError

from requests import ReadTimeout
from retry import retry
from urllib3.exceptions import MaxRetryError

from runnable import Runnable
from src.collect.tickers.ticker_collector import TickerCollector
from src.find.site import InvalidTickerExcpetion

logger = logging.getLogger('Collect')

class SiteCollector(TickerCollector, ABC):
    @property
    @abstractmethod
    def site(self):
        pass


    @retry((JSONDecodeError, requests.exceptions.ProxyError, ReadTimeout, MaxRetryError), tries=12, delay=0.25)
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
            response = requests.get(url, timeout=2, proxies=Runnable.proxy)

            if response.status_code == 404:
                logger.warning("Non existing ticker: {ticker}: {url} -> 404 error code".format(
                    ticker=self.ticker, url=url))
                raise InvalidTickerExcpetion(self.ticker)

            if response.status_code != 200:
                logger.warning("Can't collect {ticker}: {url} -> responsne code: {code}".format(
                    ticker=self.ticker, url=url, code=response.status_code))
                raise InvalidTickerExcpetion(self.ticker)

            data = response.json()

            self._raw_data = deepcopy(data)

        return data
