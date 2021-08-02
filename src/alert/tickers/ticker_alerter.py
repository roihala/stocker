import logging
from operator import itemgetter
from typing import Iterable, List

from bson import ObjectId

from src import factory
from src.alert.alerter_base import AlerterBase

logger = logging.getLogger('Alert')


class TickerAlerter(AlerterBase):
    def __init__(self, mongo_db, *args, **kwargs):
        super().__init__(mongo_db, *args, **kwargs)

        self._reader = factory.Factory.readers_factory(self.name,
                                                       **{'mongo_db': self._mongo_db, 'ticker': self._ticker})

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

    def generate_messages(self, diffs: List[dict]):
        messages = {}
        for diff in self._edit_batch(diffs):
            msg = self.generate_msg(diff)
            if not msg:
                continue

            messages[diff['_id']] = {'message': msg, 'date': diff.get('date')}

        return messages

    def generate_msg(self, diff):
        if not self.is_relevant_diff(diff):
            return ''

        diff = self.edit_diff(diff)

        keys = diff['changed_key']
        keys = [keys] if isinstance(keys, str) else keys
        new_keys = []
        for key in keys:
            new_keys.append(self.get_keys_translation()[
            key] if key in self.get_keys_translation() else key.capitalize())
        if diff['insights'].get('role_change'):
            diff['insights']['role_change'] = self.get_keys_translation()[diff['insights']['role_change']]
        diff['changed_key'] = set(new_keys)

        try:
            # Treating the new value as the most accurate piece of information
            if type(diff.get('new')) is bool:
                return self.generate_bool_msg(diff)
        except Exception as e:
            logging.warning(f"Couldn't generate custom message for {diff}")
            logging.exception(e)

        return self.generate_default_msg(diff)

    def edit_diff(self, diff) -> dict:
        return diff

    def format_message_body(self, symbol, value):
        if isinstance(value, str):
            return f'{symbol} {value}'
        else:
            return f"\n{symbol}" + f"\n{symbol}".join(value)

    def generate_default_msg(self, diff):
        old, new = diff['old'], diff['new']

        title = '*{key}* {verb}:'

        if diff.get('diff_type') == 'remove':
            verb = 'removed'
            body = self.format_message_body(self.RED_CIRCLE_EMOJI_UNICODE, old)
        elif diff.get('diff_type') == 'add':
            verb = 'added'
            if diff['insights'].get('role_change'):
                value = diff['insights']['role_change']
                title = f'\n{value} changed to {diff.get("changed_key")}:'
                marker = self.YELLOW_CIRCLE_EMOJI_UNICODE
            else:
                marker = self.GREEN_CIRCLE_EMOJI_UNICODE
            body = self.format_message_body(marker, new)
        else:
            verb = 'changed'
            body = '{red_circle_emoji} {old}\n' \
                   '{green_circle_emoji} {new}'.format(red_circle_emoji=self.RED_CIRCLE_EMOJI_UNICODE,
                                                       old=old,
                                                       green_circle_emoji=self.GREEN_CIRCLE_EMOJI_UNICODE,
                                                       new=new)
        if diff['insights'].get('sympathy'):
            tickers = diff['insights']['sympathy']
            body += f'\n{self.YELLOW_CIRCLE_EMOJI_UNICODE} Detected {diff.get("new")} in {tickers}'.replace("\'", "")

        if title == '*{key}* {verb}:':
            key = diff['changed_key']
            changed_key = key if isinstance(key, str) else "&".join(key)
            title = title.format(key=changed_key, verb=verb)

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

    def _edit_batch(self, diffs: Iterable[dict]) -> Iterable[dict]:
        for diff in diffs:
            diff['insights'] = {}
        return sorted(diffs, key=itemgetter('changed_key'))

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
        # TODO: validate all changed keys not only the first
        key = key if isinstance(key, str) else list(key)[0]

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
