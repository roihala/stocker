import logging
from datetime import datetime, timedelta

import pandas
import pymongo
import telegram
from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger

from scheduler_utils import disable_apscheduler_logs
from src import factory

logger = logging.getLogger('Alert')


class AlerterBase(object):
    ALERT_EMOJI_UNICODE = u'\U0001F6A8'
    FAST_FORWARD_EMOJI_UNICODE = u'\U000023E9'
    CHECK_MARK_EMOJI_UNICODE = u'\U00002705'

    def __init__(self, mongo_db, telegram_bot, debug=None):
        self.name = self.__class__.__name__.lower()
        self._mongo_db = mongo_db
        self._telegram_bot = telegram_bot
        self._debug = debug
        self._telegram_users = self._mongo_db.telegram_users.find()

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

    def alert(self, diff):
        diff = self._edit_diff(diff)
        if diff:
            self.__telegram_alert(diff.get('ticker'), diff)
            return True
        return False

    def __telegram_alert(self, ticker, diff):
        # User-friendly message
        msg = '{alert_emoji} Detected change on {ticker}:\n{alert}'.format(alert_emoji=self.ALERT_EMOJI_UNICODE,
                                                                           ticker=ticker,
                                                                           alert=self.__translate_diff(diff))
        nondelayed_users = []
        delayed_users = []

        for user in self._telegram_users:
            if user.get('delay') is True:
                delayed_users.append(user)
            else:
                nondelayed_users.append(user)

        self.__send_telegram_alert(nondelayed_users, msg)
        self.__send_delayed(delayed_users, msg)

        # TODO : Halamish decide
        # try:
        #     if self._debug and not user.get('develop') is True:
        #         continue
        #
        #     # otciq alerts are only for users with high permissions
        #     if diff.get('diff_appendix') == 'otciq':
        #         if user.get('permissions') == 'high':
        #             self._telegram_bot.sendMessage(chat_id=user.get("chat_id"), text=msg,
        #                                            parse_mode=telegram.ParseMode.MARKDOWN)
        #     else:
        #         self._telegram_bot.sendMessage(chat_id=user.get("chat_id"), text=msg,
        #                                        parse_mode=telegram.ParseMode.MARKDOWN)
        #
        # except Exception as e:
        #     logger.exception(e)

    def __send_delayed(self, delayed_users, msg):
        scheduler = BackgroundScheduler(executors={
            'default': ThreadPoolExecutor(10),
        }, timezone=" Africa/Abidjan")

        disable_apscheduler_logs()
        trigger = DateTrigger(run_date=datetime.utcnow() + timedelta(minutes=10))

        # Running daily alerter half an hour before the market opens
        scheduler.add_job(self.__send_telegram_alert,
                          args=[delayed_users, msg],
                          trigger=trigger)
        scheduler.start()

    def __send_telegram_alert(self, users_group, msg):
        try:
            for user in users_group:
                self._telegram_bot.sendMessage(chat_id=user.get("chat_id"), text=msg,
                                               parse_mode=telegram.ParseMode.MARKDOWN)

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
        title = '*{key}* has {verb}:\n'
        subtitle = ''

        if diff.get('diff_type') == 'remove':
            verb = 'been removed'
            body = diff.get('old')
        elif diff.get('diff_type') == 'add':
            verb = 'been added'
            body = diff.get('new')
        else:
            verb = 'changed'
            body = '{old} {fast_forward}{fast_forward}{fast_forward} {new}\n'.format(
                fast_forward=self.FAST_FORWARD_EMOJI_UNICODE,
                old=diff.get('old'),
                new=diff.get('new'))

        title = title.format(key=diff.get('changed_key'), verb=verb)

        if diff.get('diff_appendix') == 'otciq':
            subtitle = 'Detected First OTCIQ approach {check_mark}'.format(check_mark=self.CHECK_MARK_EMOJI_UNICODE)

        title = title if not subtitle else title + subtitle + '\n'

        return '{title}\n' \
               '{body}'.format(
            title=title,
            body=body)

    def _get_sorted_diffs(self, ticker):
        return pandas.DataFrame(
            self._mongo_db.diffs.find({"ticker": ticker}, {"_id": False}).sort('date', pymongo.ASCENDING))
