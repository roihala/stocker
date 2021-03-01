import logging
import requests
from abc import ABC, abstractmethod
from copy import deepcopy
from json import JSONDecodeError
from retry import retry

from src.collect.collector_base import CollectorBase
from src.find.site import InvalidTickerExcpetion

logger = logging.getLogger('Collect')

username = "yonisoli"
password = "5ff06d-6ecc98-91006b-86dd29-388b2c"

PROXY_RACK_DNS = "megaproxy.rotating.proxyrack.net:222"
proxy_url = "http://{}:{}@{}".format(username, password, PROXY_RACK_DNS)
proxy = {"http": proxy_url,
         'https': proxy_url}


class SiteCollector(CollectorBase, ABC):
    @property
    @abstractmethod
    def site(self):
        pass

    @retry(JSONDecodeError, tries=10, delay=1)
    def fetch_data(self, data=None) -> dict:
        """
        Fetching data by using requests.get

        * Retrying up to 3 times if requests fails to parse the result as json.

        :param data: (optional) You can transfer data in order to prevent fetching again.
        (Can be used in father-son relations

        :return: A dict containing the newly fetched entry
        """
        if not data:
            response = requests.get(self.site.get_ticker_url(self.ticker), proxies=proxy)

            if response.status_code != 200:
                logger.warning('Bad status code: {code}'.format(code=response.status_code))
                raise InvalidTickerExcpetion(self.ticker)

            data = response.json()

            self._raw_data = deepcopy(data)

        return data
