import logging
from typing import List

import arrow

from src.collect.differ import Differ
from src import factory


class AlerterBase(object):
    def __init__(self, current, latest, ticker, date=None, debug=None):
        if current is None:
            raise ValueError('Alerter should get current data')

        self.ticker = ticker
        self.name = factory.Factory.resolve_name(self.__class__)
        self._current_data = current
        self._latest = latest
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
    def nested_keys(self) -> dict:
        """
        This property is a mapping between nested keys and a sorted list of layers which will be provided to differ
        in order to get changes from the last layer only
        """
        return {}

    @property
    def filter_keys(self):
        # List of keys to ignore
        return []

    def get_diffs(self) -> List[dict]:
        """
        This function returns a list of the changes that occurred in a ticker's data.

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
        if self._latest is None:
            return []

        try:

            diffs = Differ().get_diffs(self._latest, self._current_data, self.nested_keys)
            diffs = [self.__decorate_diff(diff) for diff in diffs]

            # Applying filters
            return self._edit_diffs(diffs)
        except Exception as e:
            logging.warning('Failed to get diffs between:\n{latest}\n>>>>>>\n{current}'.format(latest=self._latest,
                                                                                               current=self._current_data))
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
                logging.warning('Incorrect hierarchy for {ticker}. {error}'.format(ticker=self.ticker, error=e.args))
        return diff

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
