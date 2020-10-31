import json
import urllib
from abc import ABC, abstractmethod
from urllib.error import HTTPError

from src.alert.collector_base import CollectorBase
from src.find.site import InvalidTickerExcpetion


class SiteCollector(CollectorBase, ABC):
    @property
    @abstractmethod
    def site(self):
        pass

    def fetch_data(self) -> dict:
        try:
            site = urllib.request.urlopen(self.site.get_ticker_url(self.ticker))

            response = json.loads(site.read().decode())

        except HTTPError:
            raise InvalidTickerExcpetion('Invalid ticker: {ticker}', self.ticker)

        return response
