import logging

import pandas
import pymongo
import requests

from src.collect.collectors.profile import Profile
from src.collect.collectors.securities import Securities
from src.find.site import Site

logger = logging.getLogger('Alert')


class AlerterBase(object):
    ALERT_EMOJI_UNICODE = u'\U0001F6A8'
    FAST_FORWARD_EMOJI_UNICODE = u'\U000023E9'
    CHECK_MARK_EMOJI_UNICODE = u'\U00002705'
    DOLLAR_SIGN_EMOJI_UNICODE = u'\U0001F4B2'
    FACTORY_EMOJI_UNICODE = u'\U0001F3ED'
    MEDAL_EMOJI_UNICODE = u'\U0001F947'

    def __init__(self, mongo_db, telegram_bot, debug=None):
        self.name = self.__class__.__name__.lower()
        self._mongo_db = mongo_db
        self._telegram_bot = telegram_bot
        self._debug = debug

    @property
    def hierarchy(self) -> dict:
        """
        This property is a mapping between keys and a sorted list of their logical hierarchy.
        by using this mapping we could filter diffs by locating changed values in hierarchy
        """
        return {}

    @property
    def filter_keys(self):
        # List of keys to ignore
        return []

    @staticmethod
    def get_nested_keys() -> dict:
        """
        This property is a mapping between nested keys and a sorted list of layers which will be provided to differ
        in order to get changes from the last layer only
        """
        return {}

    def get_collector(self, ticker):
        collector_args = {'mongo_db': self._mongo_db, 'ticker': ticker}

        return factory.Factory.collectors_factory(self.name, **collector_args)

    def get_alert_msg(self, diff):
        diff = self._edit_diff(diff)
        if diff:
            return '{alert_emoji} Detected change on {ticker}:\n{alert}'.format(alert_emoji=self.ALERT_EMOJI_UNICODE,
                                                                                ticker=diff.get('ticker'),
                                                                                alert=self.__translate_diff(diff))
        else:
            return ''

    def _edit_diff(self, diff) -> dict:
        """
        This function is for editing or deleting an existing diff.
        It will be called with every diff that has been found while maintaining the diff structure of:

        {
            "ticker": The ticker,
            "date": The current date,
            "changed_key": The key that have changed
            "old": The "old" value,
            "new": The "new" value,
            "diff_type": The type of the diff, could be add, remove, etc...
            "source": Which collection did it come from?
        }

        :return: The edited diff, None to delete the diff
        """
        key = diff.get('changed_key')

        if key is None or key == '' or key in self.filter_keys:
            return None

        elif key in self.hierarchy.keys():
            try:
                if self.hierarchy[key].index(diff['new']) < self.hierarchy[key].index(diff['old']):
                    return None

            except ValueError as e:
                logger.warning('Incorrect hierarchy for {ticker}.'.format(ticker=diff.get('ticker')))
                logger.exception(e)
        return diff

    def __translate_diff(self, diff):
        key = diff.get('changed_key')
        ticker = diff.get('ticker')

        title = '*{key}* has {verb}:'
        subtitle = ''

        if diff.get('diff_type') == 'remove':
            verb = 'been removed'
            body = diff.get('old')
        elif diff.get('diff_type') == 'add':
            verb = 'been added'
            body = diff.get('new')
        else:
            verb = 'changed'
            body = '{old} {fast_forward}{fast_forward}{fast_forward} {new}'.format(
                fast_forward=self.FAST_FORWARD_EMOJI_UNICODE,
                old=diff.get('old'),
                new=diff.get('new'))

        title = title.format(key=key, verb=verb)

        if diff.get('diff_appendix') == 'otciq':
            subtitle = 'Detected First OTCIQ approach {check_mark}'.format(check_mark=self.CHECK_MARK_EMOJI_UNICODE)

        title = title if not subtitle else title + '\n' + subtitle

        ticker_profile = Profile(self._mongo_db, ticker).get_latest()
        ticker_securities = Securities(self._mongo_db, ticker).get_latest()

        industry = ticker_profile.get('primarySicCode')
        industry = industry[industry.index(" - ")+3:]

        properties = """{factory} Industry: {industry}
{medal} Tier: {tier}
{dollar} Last price: {last_price}""".format(factory=self.FACTORY_EMOJI_UNICODE,
                                       industry=industry,
                                       medal=self.MEDAL_EMOJI_UNICODE,
                                       tier=ticker_securities.get('tierDisplayName'),
                                       dollar=self.DOLLAR_SIGN_EMOJI_UNICODE,
                                       last_price=AlerterBase.get_last_price(ticker))

        return '{title}\n' \
               '{body}\n\n' \
               '{properties}'.format(title=title, body=body, properties=properties)

    @staticmethod
    def get_last_price(ticker):
        url = Site('prices',
                   'https://backend.otcmarkets.com/otcapi/stock/trade/inside/{ticker}?symbol={ticker}',
                   is_otc=True).get_ticker_url(ticker)
        response = requests.get(url)
        return response.json().get('previousClose')

    def _get_sorted_diffs(self, ticker):
        return pandas.DataFrame(
            self._mongo_db.diffs.find({"ticker": ticker}, {"_id": False}).sort('date', pymongo.ASCENDING))
