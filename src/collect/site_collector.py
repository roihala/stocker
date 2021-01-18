import logging
from abc import ABC, abstractmethod
from copy import deepcopy

import requests

from src.collect.collector_base import CollectorBase
from src.find.site import InvalidTickerExcpetion

logger = logging.getLogger('Collect')


class SiteCollector(CollectorBase, ABC):
    @property
    @abstractmethod
    def site(self):
        pass

    def fetch_data(self, data=None) -> dict:
        if not data:
            response = requests.get(self.site.get_ticker_url(self.ticker))

            if response.ok is not True:
                raise InvalidTickerExcpetion(self.ticker)

            data = response.json()

            self.raw_data = deepcopy(data)

        return data
