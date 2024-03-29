import logging
from operator import itemgetter
from typing import Iterable, List

from src.alert.alerter_base import AlerterBase
from src import readers_factory

logger = logging.getLogger('Alert')


class TickerAlerter(AlerterBase):
    def __init__(self, mongo_db, *args, **kwargs):
        super().__init__(mongo_db, *args, **kwargs)

        self._reader = readers_factory.ReadersFactory.factory(self.name, **{'mongo_db': self._mongo_db, 'ticker': self._ticker})

    @staticmethod
    def get_hierarchy() -> dict:
        """
        This property is a mapping between keys and a sorted list of their logical hierarchy.
        by using this mapping we could filter diffs by locating changed values in hierarchy
        """
        return {}

    @property
    def relevant_keys(self):
        # List of keys to ignore
        return []

    @staticmethod
    def get_keys_translation() -> dict:
        return {}

    def generate_msg(self, diff):
        key = diff['changed_key']
        diff['changed_key'] = self.get_keys_translation()[key] if key in self.get_keys_translation() else key.capitalize()
        try:
            # Treating the new value as the most accurate piece of information
            if type(diff.get('new')) is bool:
                return self.generate_bool_msg(diff)
        except Exception as e:
            logging.warning(f"Couldn't generate custom message for {diff}")
            logging.exception(e)

        return self.generate_default_msg(diff)

    def generate_default_msg(self, diff):
        old, new = diff['old'], diff['new']

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
        if diff.get('insight'):
            body += f'\n{self.YELLOW_CIRCLE_EMOJI_UNICODE} Detected {diff.get("new")} in {diff.get("insight_fields")}'.replace("\'", "")

        title = title.format(key=diff['changed_key'], verb=verb)

        return '{title}\n' \
               '{body}'.format(title=title, body=body)

    def generate_bool_msg(self, diff):
        msg = ''

        if diff.get('new') is True or diff.get('diff_type') == 'add':
            msg = '{green_circle_emoji} *{key}* added'.format(green_circle_emoji=self.GREEN_CIRCLE_EMOJI_UNICODE,
                                                              key=diff.get('changed_key'))
        elif diff.get('new') is False or diff.get('diff_type') == 'remove':
            msg = '{red_circle_emoji} *{key}* removed'.format(red_circle_emoji=self.RED_CIRCLE_EMOJI_UNICODE,
                                                              key=diff.get('changed_key'))

        return msg

    def is_relevant_diff(self, diff) -> bool:
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

        try:
            if key not in self.relevant_keys or self._is_valid_diff(diff) is False:
                return False
        except Exception as e:
            logger.warning(f"Couldn't validate diff: {diff}")
            logger.exception(e)

        if key in self.get_hierarchy().keys():
            try:
                if self.get_hierarchy()[key].index(diff['new']) < self.get_hierarchy()[key].index(diff['old']):
                    return False

            except ValueError as e:
                logger.warning('Incorrect hierarchy for {ticker}.'.format(ticker=diff.get('ticker')))
                logger.exception(e)

        return True

    def _is_valid_diff(self, diff):
        if str(diff.get('old')).strip().lower() == str(diff.get('new')).strip().lower():
            return False
        return True
