import logging
from operator import itemgetter
from typing import Iterable, List

from src import factory
from src.alert.alerter_base import AlerterBase

logger = logging.getLogger('Alert')


class TickerAlerter(AlerterBase):
    def __init__(self, mongo_db, *args, **kwargs):
        super().__init__(mongo_db, *args, **kwargs)

        self._reader = factory.Factory.readers_factory(self.name, **{'mongo_db': self._mongo_db, 'ticker': self._ticker})

    @staticmethod
    def get_hierarchy() -> dict:
        """
        This property is a mapping between keys and a sorted list of their logical hierarchy.
        by using this mapping we could filter diffs by locating changed values in hierarchy
        """
        return {}

    @property
    def filter_keys(self):
        # List of keys to ignore
        return []

    def get_alert_msg(self, diffs: List[dict], as_dict=False):
        super().get_alert_msg(diffs, as_dict)

        messages = {} if as_dict else []
        for diff in self._edit_batch(diffs):
            msg = self.generate_msg(diff)
            if not msg:
                continue

            elif as_dict:
                messages[diff['_id']] = msg
            else:
                messages.append(msg)

        return messages if as_dict else '\n\n'.join([msg for msg in messages])

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
            body = '{red_circle_emoji} {old}\n' \
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

        if key in self.filter_keys + [None, ''] or self._is_valid_diff(diff) is False:
            return None

        if key in self.get_hierarchy().keys():
            try:
                if self.get_hierarchy()[key].index(diff['new']) < self.get_hierarchy()[key].index(diff['old']):
                    return None

            except ValueError as e:
                logger.warning('Incorrect hierarchy for {ticker}.'.format(ticker=diff.get('ticker')))
                logger.exception(e)
        return diff

    def _is_valid_diff(self, diff):
        if str(diff.get('old')).strip().lower() == str(diff.get('new')).strip().lower():
            return False
        return True
