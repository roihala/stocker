#!/usr/bin/env python
# -*- coding: utf-8 -*-
import logging
import os
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, ConversationHandler, CallbackQueryHandler

from runnable import Runnable
from src.telegram_bot.base_bot import BaseBot
from src.telegram_bot.owner_tools import Tools
from src.telegram_bot.resources.indexers import Indexers

LOGGER_PATH = os.path.join(os.path.dirname(__file__), 'stocker_alerts_bot.log')


class Stocker(Runnable):
    def run(self):
        if os.getenv('TELEGRAM_TOKEN') is not None:
            updater = Updater(os.getenv('TELEGRAM_TOKEN'))
        else:
            updater = Updater(self.args.token)

        dp = updater.dispatcher

        # Bad APIs make bad workarounds
        setattr(dp, 'mongo_db', self._mongo_db)
        setattr(dp, 'telegram_bot', self._telegram_bot)
        setattr(dp, 'logger', self.logger)
        setattr(dp, 'debug', self._debug)
        base_bot = BaseBot(self._mongo_db, self._telegram_bot, self.logger, self._debug)

        tools_conv = ConversationHandler(
            entry_points=[CommandHandler('Tools', base_bot.tools_command),
                          CommandHandler('Start', base_bot.start_command)],
            states={
                # START_CALLBACK: [CallbackQueryHandler(Bot.start_callback)],
                Indexers.CONVERSATION_CALLBACK: [CallbackQueryHandler(base_bot.conversation_callback)],
                Indexers.PRINT_INFO: [MessageHandler(Filters.regex('^[a-zA-Z]{3,5}$'), base_bot.info_callback),
                                      MessageHandler(~Filters.regex('^[a-zA-Z]{3,5}$'),
                                                     base_bot.invalid_ticker_format)],
                Indexers.DO_FREE_TRIAL: [MessageHandler(Filters.regex('.*'), base_bot.free_trial_callback)],
                Indexers.PRINT_DILUTION: [
                    MessageHandler(Filters.regex('^[a-zA-Z]{3,5}$'), base_bot.dilution_callback),
                    MessageHandler(~Filters.regex('^[a-zA-Z]{3,5}$'), base_bot.invalid_ticker_format)],
                Indexers.PRINT_ALERTS: [MessageHandler(Filters.regex('^[a-zA-Z]{3,5}$'), base_bot.alerts_callback),
                                        MessageHandler(~Filters.regex('^[a-zA-Z]{3,5}$'),
                                                       base_bot.invalid_ticker_format)]
            },

            fallbacks=[MessageHandler(Filters.regex('^/tools|/start$'), base_bot.conversation_fallback)]
        )

        broadcast_conv = ConversationHandler(
            entry_points=[CommandHandler('broadcast', base_bot.broadcast),
                          CommandHandler('launch_tweet', Tools.launch_tweet)],
            states={
                # Allowing letters and whitespaces
                Indexers.BROADCAST_MSG: [MessageHandler(Filters.text, base_bot.broadcast_callback)],
                Indexers.TWEET_MSG: [MessageHandler(Filters.text, Tools.tweet_callback)]
            },
            fallbacks=[],
        )
        # Re adding start command to allow deep linking
        dp.add_handler(tools_conv)

        dp.add_handler(CommandHandler('start', base_bot.start_command))
        dp.add_handler(broadcast_conv)

        dp.add_handler(CommandHandler('dilution', base_bot.dilution_command))
        dp.add_handler(CommandHandler('alerts', base_bot.alerts_command))
        dp.add_handler(CommandHandler('info', base_bot.info_command))
        dp.add_handler(CommandHandler('deregister', base_bot.deregister))
        dp.add_handler(CommandHandler('broadcast', base_bot.broadcast))
        dp.add_handler(CommandHandler('vip_user', base_bot.vip_user))
        dp.add_handler(CommandHandler('launch', Tools.launch_command))
        dp.add_handler(CommandHandler('reminder', Tools.reminder))

        # Start the Bot
        updater.start_polling()

        # Run the bot until you press Ctrl-C or the process receives SIGINT,
        # SIGTERM or SIGABRT. This should be used most of the time, since
        # start_polling() is non-blocking and will stop the bot gracefully.
        updater.idle()


def main():
    try:
        Stocker().run()
    except Exception as e:
        logging.exception(e)


if __name__ == '__main__':
    main()
