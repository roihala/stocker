import json_flatten

from src.alert.site_collector import SiteCollector
from src.find.site import Site


class Profile(SiteCollector):
    SEPERATOR = '&'

    @property
    def site(self):
        return Site(self.collection,
                    'https://backend.otcmarkets.com/otcapi/company/profile/full/{ticker}?symbol={ticker}',
                    True)

    def fetch_data(self):
        data = super().fetch_data()
        # Once again, bad code makes bad workarounds
        return dict(Profile.flatten(data))

    def _filter_diff(self, diff) -> bool:
        return True

    @staticmethod
    def flatten(d, prefix=None):
        # This function was taken from the implementation of json_flatten package
        if not d:
            return []

        rows = []
        seperator_prefix = prefix and (prefix + Profile.SEPERATOR) or ""
        if isinstance(d, dict):
            for key, value in d.items():
                rows.extend(Profile.flatten(value, prefix=seperator_prefix + key))
        elif isinstance(d, (list, tuple)):
            for i, item in enumerate(d):
                rows.extend(Profile.flatten(item, prefix=seperator_prefix + str(i)))
        else:
            rows.append((prefix, str(d)))
        return rows
