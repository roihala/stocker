import logging
from datetime import datetime, timedelta

import pandas
import pymongo
import telegram
from apscheduler.triggers.date import DateTrigger

from src import factory

import difflib
import textwrap
from PIL import Image, ImageDraw
from io import BytesIO

logger = logging.getLogger('Alert')


class AlerterBase(object):
    ALERT_EMOJI_UNICODE = u'\U0001F6A8'
    FAST_FORWARD_EMOJI_UNICODE = u'\U000023E9'
    CHECK_MARK_EMOJI_UNICODE = u'\U00002705'
    LONG_STRING_LENGTH = 300

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
            return '{alert_emoji} Detected change on *{ticker}*:\n{alert}'.format(alert_emoji=self.ALERT_EMOJI_UNICODE,
                                                                                ticker=diff.get('ticker'),
                                                                                alert=self.__translate_diff(diff))
        else:
            return ''

    def get_alert_diff_img(self, diff):
        if type(diff.get('new')) is str:
            if len(diff.get('new')) >= self.LONG_STRING_LENGTH:
                return self.__create_diff_img(diff.get('old'), diff.get('new'))

        return None

    def __telegram_alert(self, ticker, diff):
        # User-friendly message
        msg = '{alert_emoji} Detected change on *{ticker}*:\n{alert}'.format(alert_emoji=self.ALERT_EMOJI_UNICODE,
                                                                           ticker=ticker,
                                                                           alert=self.__translate_diff(diff))

        nondelayed_users = []
        delayed_users = []

        for user in self._telegram_users:
            if user.get('delay') is True:
                delayed_users.append(user)
            else:
                nondelayed_users.append(user)

        img = None

        print("Creating image")
        if type(diff.get('new')) is str:
            if len(diff.get('new')) >= self.LONG_STRING_LENGTH:
                img = self.__create_diff_img(diff.get('old'), diff.get('new'))
                logger.info("Image created")

        self.__send_telegram_alert(nondelayed_users, msg, img)
        self.__send_delayed(delayed_users, msg, img)

    def __send_delayed(self, delayed_users, msg, img=None):
        trigger = DateTrigger(run_date=datetime.utcnow() + timedelta(minutes=10))

        self._scheduler.add_job(self.__send_telegram_alert,
                                args=[delayed_users, msg, img],
                                trigger=trigger)

    def __send_telegram_alert(self, users_group, msg, img=None):
        for user in users_group:
            try:
                self._telegram_bot.sendMessage(chat_id=user.get("chat_id"), text=msg,
                                               parse_mode=telegram.ParseMode.MARKDOWN)
                if img:
                    self._telegram_bot.send_photo(chat_id=user.get("chat_id"), photo=img)

            except Exception as e:
                logger.exception(e)

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
        title = '{key} has {verb}:'
        subtitle = ''

        old = diff.get('old')
        if type(old) is int:
            old = '{:,}'.format(old)

        new = diff.get('new')
        if type(new) is int:
            new = '{:,}'.format(new)

        if diff.get('diff_type') == 'remove':
            verb = 'been removed'
            body = old
        elif diff.get('diff_type') == 'add':
            verb = 'been added'
            body = new
        else:
            verb = 'changed'
            body = '{old} {fast_forward}{fast_forward}{fast_forward} {new}'.format(
                fast_forward=self.FAST_FORWARD_EMOJI_UNICODE,
                old=old,
                new=new)

        title = title.format(key=diff.get('changed_key'), verb=verb)

        if diff.get('diff_appendix') == 'otciq':
            subtitle = 'Detected First OTCIQ approach {check_mark}'.format(check_mark=self.CHECK_MARK_EMOJI_UNICODE)

        title = title if not subtitle else title + '\n' + subtitle

        return '{title}\n' \
               '{body}'.format(title=title, body=body)

    def __create_diff_img(self, old, new):
        old_lines = old.split('.')
        new_lines = new.split('.')

        differ = difflib.Differ()
        generator_res = differ.compare(old_lines, new_lines)
        img = Image.new("RGB", (600, 600))
        line_height = 10
        drawer = ImageDraw.Draw(img)
        for line in generator_res:
            if len(line) == 0:
                continue
            # Because split is removing it.
            line += '.'
            splitted_lines = textwrap.wrap(line, width=90)
            if line.startswith("+"):
                for splitted_line in splitted_lines:
                    drawer.text((10, line_height), splitted_line, fill=(0, 255, 0))
                    line_height += 10
            elif line.startswith("-"):
                for splitted_line in splitted_lines:
                    drawer.text((10, line_height), splitted_line, fill=(255, 0, 0))
                    line_height += 10
            elif line.startswith("?"):
                continue
            else:
                for splitted_line in splitted_lines:
                    drawer.text((10, line_height), splitted_line)
                    line_height += 10

        bio = BytesIO()
        bio.name = 'image.jpeg'
        img.save(bio, 'JPEG')
        bio.seek(0)
        return bio

    def _get_sorted_diffs(self, ticker):
        return pandas.DataFrame(
            self._mongo_db.diffs.find({"ticker": ticker}, {"_id": False}).sort('date', pymongo.ASCENDING))
