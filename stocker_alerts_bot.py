#!/usr/bin/env python
# -*- coding: utf-8 -*-
import concurrent.futures
import json
import logging
import os
import sys

import inflection
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, ConversationHandler, CallbackQueryHandler

from common_runnable import CommonRunnable
from src.telegram_bot.father_bot import FatherBot
from src.telegram_bot.owner_bot import OwnerBot
from src.telegram_bot.registration_bot import RegistrationBot
from src.telegram_bot.resources.indexers import Indexers

LOGGER_PATH = os.path.join(os.path.dirname(__file__), 'stocker_alerts_bot.log')


class DefaultCustomFormatter(logging.Formatter):
    def format(self, record):
        if record.args and isinstance(record.args, dict):
            return json.dumps(record.args)
        else:
            logmsg = super(DefaultCustomFormatter, self).format(record)
            return logmsg


class Stocker(CommonRunnable):
    def __init__(self, args=None):
        super().__init__(args)
        self.executor = None

    def run(self):
        updaters = []
        telegram_bots = self._mongo_db.bots.find() if not self._debug else self._mongo_db.bots.find_one({'name': 'stocker_tests_bot'})
        telegram_bots = [_ for _ in telegram_bots]

        # Initialize thread pool
        if len(telegram_bots) > 1:
            self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=len(telegram_bots) - 1)

        for bot in telegram_bots:
            updater = Updater(bot["token"])
            updaters.append(updater)
            dp = updater.dispatcher

            bot_args = {
                'mongo_db': self._mongo_db,
                'bot_instance': self.init_telegram(bot['token']),
                'logger': self.logger,
                'debug': self._debug
            }

            registration_bot = RegistrationBot(**bot_args)
            owner_bot = OwnerBot(**bot_args)
            father_bot = FatherBot(registration_bot, **bot_args)

            tools_conv = ConversationHandler(
                entry_points=[CommandHandler('Tools', father_bot.tools_command),
                              CommandHandler('Start', father_bot.start_command)],
                states={
                    # START_CALLBACK: [CallbackQueryHandler(Bot.start_callback)],
                    Indexers.CONVERSATION_CALLBACK: [CallbackQueryHandler(father_bot.conversation_callback)],
                    Indexers.PRINT_INFO: [MessageHandler(Filters.regex('^[a-zA-Z]{3,5}$'), father_bot.info_callback),
                                          MessageHandler(~Filters.regex('^[a-zA-Z]{3,5}$'),
                                                         father_bot.invalid_ticker_format)],
                    Indexers.PRINT_OTCIQ: [MessageHandler(Filters.regex('^[a-zA-Z]{3,5}$'), father_bot.otciq_callback),
                                           MessageHandler(~Filters.regex('^[a-zA-Z]{3,5}$'),
                                                          father_bot.invalid_ticker_format)],
                    Indexers.DO_FREE_TRIAL: [MessageHandler(Filters.regex('.*'), registration_bot.free_trial_callback)],
                    Indexers.PRINT_DILUTION: [
                        MessageHandler(Filters.regex('^[a-zA-Z]{3,5}$'), father_bot.dilution_callback),
                        MessageHandler(~Filters.regex('^[a-zA-Z]{3,5}$'), father_bot.invalid_ticker_format)],
                    Indexers.PRINT_ALERTS: [MessageHandler(Filters.regex('^[a-zA-Z]{3,5}$'), father_bot.alerts_callback),
                                            MessageHandler(~Filters.regex('^[a-zA-Z]{3,5}$'),
                                                           father_bot.invalid_ticker_format)],
                    Indexers.GET_WATCHLIST: [MessageHandler(Filters.regex('^[a-zA-Z]{3,5}(?:,[a-zA-Z]{3,5})*$'),
                                                            registration_bot.watchlist_callback),
                                             MessageHandler(~Filters.regex('^[a-zA-Z]{3,5}(?:,[a-zA-Z]{3,5})*$'),
                                                            registration_bot.invalid_watchlist)],

                },

                fallbacks=[MessageHandler(Filters.regex('^/tools|/start$'), father_bot.conversation_fallback)]
            )

            broadcast_conv = ConversationHandler(
                entry_points=[CommandHandler('broadcast', owner_bot.broadcast_command),
                              CommandHandler('launch_tweet', owner_bot.launch_tweet)],
                states={
                    # Allowing letters and whitespaces
                    Indexers.BROADCAST_MSG: [MessageHandler(Filters.text, owner_bot.broadcast_callback)],
                    Indexers.TWEET_MSG: [MessageHandler(Filters.text, owner_bot.tweet_callback)]
                },
                fallbacks=[],
            )

            # Re adding start command to allow deep linking
            dp.add_handler(tools_conv)

            dp.add_handler(CommandHandler('start', father_bot.start_command))
            dp.add_handler(broadcast_conv)

            dp.add_handler(CommandHandler('dilution', father_bot.dilution_command))
            dp.add_handler(CommandHandler('alerts', father_bot.alerts_command))
            dp.add_handler(CommandHandler('info', father_bot.info_command))
            dp.add_handler(CommandHandler('otciq', father_bot.otciq_command))
            dp.add_handler(CommandHandler('deregister', registration_bot.deregister_command))
            dp.add_handler(CommandHandler('broadcast', owner_bot.broadcast_command))
            dp.add_handler(CommandHandler('vip_user', owner_bot.vip_user))
            dp.add_handler(CommandHandler('add_bot', owner_bot.add_bot))
            dp.add_handler(CommandHandler('split_bot', owner_bot.split_bot))

        # Start pooling first bot
        updaters[0].start_polling()

        for updater in updaters[1:]:
            # Start the Bot
            updater.start_polling()

            # Run the bot until you press Ctrl-C or the process receives SIGINT,
            # SIGTERM or SIGABRT. This should be used most of the time, since
            # start_polling() is non-blocking and will stop the bot gracefully.
            # idle each updater in Thread pool
            self.executor.submit(updater.idle)

        # IDLE first bot
        updaters[0].idle()

    def _init_logging(self):
        cloud_logger = logging.getLogger(inflection.underscore(self.__class__.__name__))

        cloud_logger.setLevel(logging.INFO)
        cloud_stream = logging.StreamHandler(sys.stdout)
        cloud_stream.setFormatter(DefaultCustomFormatter())

        cloud_logger.addHandler(cloud_stream)
        return cloud_logger


def main():
    try:
        Stocker().run()
    except Exception as e:
        logging.exception(e)


if __name__ == '__main__':

    main()
