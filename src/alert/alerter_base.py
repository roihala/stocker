import logging
from functools import reduce
from typing import List

import arrow

from src.collect.differ import Differ


class AlerterBase(object):
    FAST_FORWARD_EMOJI_UNICODE = u'\U000023E9'

    def __init__(self, mongo_db, ticker, date=None, debug=None):
        self._mongo_db = mongo_db
        self.ticker = ticker
        self.name = self.__class__.__name__.lower()
        self._date = date if date else arrow.utcnow()
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

    def get_alerts(self, latest, current):
        diffs = self.get_diffs(latest, current)
        if diffs and not self._debug:
            logging.info('diffs: {diffs}'.format(diffs=diffs))

            # Insert the new diffs to mongo
            [self._mongo_db.diffs.insert_one(diff) for diff in diffs]

        return reduce(lambda x, y: x + self.__translate_diff(y), diffs, '')

    def get_diffs(self, latest, current) -> List[dict]:
        """
        This function returns a list of the changes that occurred in certain ticker's data.

        :return: A list of dicts in the format of:
        {
            "ticker": The ticker,
            "date": The current date,
            "changed_key": The key that have changed
            "old": The "old" value,
            "new": The "new" value,
            "diff_type": The type of the diff, could be add, remove, etc...
            "source": Which collection did it come from?
        }

        """
        if not current or not latest:
            return []

        try:
            diffs = Differ().get_diffs(latest, current, self.get_nested_keys())
            diffs = [self.__decorate_diff(diff) for diff in diffs]

            # Applying filters
            return self._edit_diffs(diffs)
        except Exception as e:
            logging.warning('Failed to get diffs between:\n{latest}\n>>>>>>\n{current}'.format(latest=latest,
                                                                                               current=current))
            logging.exception(e)

    def _edit_diffs(self, diffs) -> List[dict]:
        """
        This function is for editing the list of diffs right before they are alerted
        The diffs will have the following structure:

        {
            "ticker": The ticker,
            "date": The current date,
            "changed_key": The key that have changed
            "old": The "old" value,
            "new": The "new" value,
            "diff_type": The type of the diff, could be add, remove, etc...
            "source": Which collection did it come from?
        }
        """
        edited_diffs = []

        for diff in diffs:
            diff = self._edit_diff(diff)

            if diff is not None and diff['changed_key'] not in self.filter_keys:
                edited_diffs.append(diff)

        return edited_diffs

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
        key = diff['changed_key']

        if key == '':
            return None
        elif key in self.hierarchy.keys():
            try:
                if self.hierarchy[key].index(diff['new']) < self.hierarchy[key].index(diff['old']):
                    return None
            # If the key is not in hierarchy list
            except ValueError as e:
                logging.warning('Incorrect hierarchy for {ticker}.'.format(ticker=self.ticker))
                logging.exception(e)
        return diff

    def __translate_diff(self, diff):
        return '*{key}* has changed:\n' \
               '{old} {fast_forward}{fast_forward}{fast_forward} {new}\n'.format(fast_forward=self.FAST_FORWARD_EMOJI_UNICODE,
                                                                                 ticker=diff.get('ticker'),
                                                                                 key=diff.get('changed_key'),
                                                                                 old=diff.get('old'),
                                                                                 new=diff.get('new'))

    def __decorate_diff(self, diff):
        # joining by '.' if a key is a list of keys (differ's nested changes approach)
        key = diff['changed_key'] if not isinstance(diff['changed_key'], list) else \
            '.'.join((str(part) for part in diff['changed_key']))

        diff.update({
            "ticker": self.ticker,
            "date": self._date.format(),
            "changed_key": key,
            "source": self.name
        })
        return diff
