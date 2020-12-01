from src.collect.site_collector import SiteCollector
from src.find.site import Site, InvalidTickerExcpetion


class Prices(SiteCollector):
    FILTER_KEYS = ['percentChange', 'tickCode', 'tickName', 'volumeFormatted', 'lastTradeTime', 'quoteTime',
                   'quoteDateTime', 'insideTime', 'bidPrice', 'bidSize', 'askPrice', 'askSize', 'dailyHigh', 'dailyLow',
                   'annualHigh', 'annualLow', 'previousClose', 'betaCoefficient', 'exchangeCode', 'exchangeName',
                   'delay', 'isADR', 'realtime', 'pinkLinkRealtime', 'thirtyDaysAvgVol', 'showRealtimeAd', 'marketCap',
                   'sharesOutstanding', 'adr']

    @property
    def site(self):
        return Site(self.collection,
                    'https://backend.otcmarkets.com/otcapi/stock/trade/inside/{ticker}?symbol={ticker}',
                    True)

    def _edit_diff(self, diff):
        return None
