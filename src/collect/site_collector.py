import logging
import requests
from abc import ABC, abstractmethod
from copy import deepcopy
from json import JSONDecodeError
from retry import retry

from src.collect.collector_base import CollectorBase
from src.find.site import InvalidTickerExcpetion

logger = logging.getLogger('Collect')


class SiteCollector(CollectorBase, ABC):
    @property
    @abstractmethod
    def site(self):
        pass

    @retry(JSONDecodeError, tries=3, delay=1)
    def fetch_data(self, data=None) -> dict:
        """
        Fetching data by using requests.get

        * Retrying up to 3 times if requests fails to parse the result as json.

        :param data: (optional) You can transfer data in order to prevent fetching again.
        (Can be used in father-son relations

        :return: A dict containing the newly fetched entry
        """
        if not data:
            response = requests.get(self.site.get_ticker_url(self.ticker))

            if response.ok is not True:
                raise InvalidTickerExcpetion(self.ticker)

            data = response.json()

            self._raw_data = deepcopy(data)

        return data
