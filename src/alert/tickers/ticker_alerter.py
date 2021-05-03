import logging
from operator import itemgetter
from typing import Iterable

from src import factory
from src.alert.alerter_base import AlerterBase

logger = logging.getLogger('Alert')


class TickerAlerter(AlerterBase):
    def __init__(self, mongo_db, *args, **kwargs):
        super().__init__(mongo_db, *args, **kwargs)

        self._reader = factory.Factory.readers_factory(self.name, **{'mongo_db': self._mongo_db, 'ticker': self._ticker})

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

    def get_alert_msg(self, diffs: Iterable[dict]):
        msg = ''

        for diff in self._edit_batch(diffs):
            try:
                diff_msg = self.generate_msg(diff)

                if diff_msg:
                    msg = msg + '\n\n' + diff_msg if msg else diff_msg
            except Exception as e:
                logger.warning("Couldn't generate msg for diff: {diff}".format(diff=diff))
                logger.exception(e)

        return msg

    def generate_msg(self, diff, old=None, new=None):
        diff = self._edit_diff(diff)

        if not diff:
            return ''

        old = old or diff.get('old')
        new = new or diff.get('new')

        title = '*{key}* {verb}:'

        if diff.get('diff_type') == 'remove':
            verb = 'removed'
            body = '{red_circle_emoji} {old}'.format(red_circle_emoji=self.RED_CIRCLE_EMOJI_UNICODE,
                                                     old=old)
        elif diff.get('diff_type') == 'add':
            verb = 'added'
            body = '{green_circle_emoji} {new}'.format(green_circle_emoji=self.GREEN_CIRCLE_EMOJI_UNICODE,
                                                       new=new)
        else:
            verb = 'changed'
            body = '{red_circle_emoji}{old}\n' \
                   '{green_circle_emoji} {new}'.format(red_circle_emoji=self.RED_CIRCLE_EMOJI_UNICODE,
                                                       old=old,
                                                       green_circle_emoji=self.GREEN_CIRCLE_EMOJI_UNICODE,
                                                       new=new)

        title = title.format(key=diff.get('changed_key'), verb=verb)

        return '{title}\n' \
               '{body}'.format(title=title, body=body)

    def _edit_batch(self, diffs: Iterable[dict]) -> Iterable[dict]:
        return sorted(diffs, key=itemgetter('changed_key'))

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
