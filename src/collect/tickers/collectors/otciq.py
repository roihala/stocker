from json import JSONDecodeError
from urllib.error import URLError

import requests
from requests import ReadTimeout
from retry import retry
from urllib3.exceptions import MaxRetryError, SSLError, NewConnectionError

from src.collect.tickers.site_collector import SiteCollector
from src.find.site import Site


class Otciq(SiteCollector):
    @property
    def site(self):
        return Site('otciq', 'http://backend.otcmarkets.com/otcapi/company/hasIqAccount/{ticker}', is_otc=True)

    @retry((JSONDecodeError, requests.exceptions.ProxyError, ReadTimeout, MaxRetryError, SSLError, URLError,
            NewConnectionError), tries=12,
           delay=0.25)
    def fetch_data(self, data=None):
        is_iq = super().fetch_data()
        return {'hasIqAccount': is_iq}
