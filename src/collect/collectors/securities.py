from src.collect.site_collector import SiteCollector
from src.find.site import Site, InvalidTickerExcpetion


class Securities(SiteCollector):
    @property
    def site(self):
        return Site(self.collection,
                    'https://backend.otcmarkets.com/otcapi/company/profile/full/{ticker}?symbol={ticker}',
                    True)

    @property
    def nested_keys(self):
        return {'transferAgents': [list, dict, 'name'],
                'notes': [list]}

    def fetch_data(self, data=None):
        try:
            data = super().fetch_data(data)
            return data['securities'][0]
        except KeyError:
            raise InvalidTickerExcpetion("Can't get the securities sector from the profile")
