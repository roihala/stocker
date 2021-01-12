#!/usr/bin/env python
# -*- coding: utf-8 -*-
import logging
import os

import dataframe_image as dfi
import telegram
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, ConversationHandler

from client import Client
from runnable import Runnable

PRINT_HISTORY, GENDER, LOCATION, BIO = range(4)

VALIDATE_PASSWORD, STAM = range(2)

LOGGER_PATH = os.path.join(os.path.dirname(__file__), 'stocker_alerts_bot.log')


class Bot(Runnable):
    TEMP_IMAGE_PATH_FORMAT = os.path.join(os.path.dirname(__file__), '{name}.png')

    def __init__(self):

        if os.getenv("ENV") == "production":
            self._debug = False
            self._mongo_db = self.init_mongo(os.environ['MONGO_URI'])
            self._telegram_bot = self.init_telegram(os.environ['TELEGRAM_TOKEN'])
            logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
        else:
            super().__init__()

    @property
    def log_name(self) -> str:
        return 'stocker_alerts_bot.log'

    def run(self):
        if os.getenv('TELEGRAM_TOKEN') is not None:
            updater = Updater(os.getenv('TELEGRAM_TOKEN'))
        else:
            updater = Updater(self.args.token)

        dp = updater.dispatcher

        # Bad APIs make bad workarounds
        setattr(dp, 'mongo_db', self._mongo_db)

        alerts_conv = ConversationHandler(
            entry_points=[CommandHandler('alerts', Bot.alerts)],
            states={
                # Allowing 3-5 letters
                PRINT_HISTORY: [MessageHandler(Filters.regex('^[a-zA-Z]{3,5}$'), Bot.alerts_request),
                                MessageHandler(~Filters.regex('^[a-zA-Z]{3,5}$'), Bot.invalid_ticker_format)]
            },
            fallbacks=[],
        )

        dd_conv = ConversationHandler(
            entry_points=[CommandHandler('dd', Bot.dd)],
            states={
                # Allowing 3-5 letters
                PRINT_HISTORY: [MessageHandler(Filters.regex('^[a-zA-Z]{3,5}$'), Bot.dd_request),
                                MessageHandler(~Filters.regex('^[a-zA-Z]{3,5}$'), Bot.invalid_ticker_format)]
            },
            fallbacks=[],
        )

        register_conv = ConversationHandler(
            entry_points=[CommandHandler('register', Bot.register)],
            states={
                # Allowing letters and whitespaces
                VALIDATE_PASSWORD: [MessageHandler(Filters.regex('^[a-zA-Z_ ]*$'), Bot.validate_password)]
            },
            fallbacks=[],
        )

        dp.add_handler(register_conv)
        dp.add_handler(alerts_conv)
        dp.add_handler(dd_conv)

        dp.add_handler(CommandHandler('start', Bot.start))
        dp.add_handler(CommandHandler('deregister', Bot.deregister))

        # Start the Bot
        updater.start_polling()

        # Run the bot until you press Ctrl-C or the process receives SIGINT,
        # SIGTERM or SIGABRT. This should be used most of the time, since
        # start_polling() is non-blocking and will stop the bot gracefully.
        updater.idle()

    @staticmethod
    def start(update, context):
        update.message.reply_text(
            '''   
    Stocker alerts bot currently supports the following commands:
            
    /register - Register to get alerts on modifications straight to your telegram account.
    /deregister - Do this to stop getting alerts from stocker. *not recommended*
    /history - Get the saved history of a certain stock, note that columns with no changes will be removed.
    /alerts - Get every alert that stocker has detected for a specific ticker.''',
            parse_mode=telegram.ParseMode.MARKDOWN)
        return ConversationHandler.END

    @staticmethod
    def register(update, context):
        try:
            update.message.reply_text('Insert password please')
            return VALIDATE_PASSWORD
        except Exception as e:
            update.message.reply_text(
                '{user_name} couldn\'t register, please contact the support team'.format(user_name=user.name))
            logging.exception(e.__traceback__)

    @staticmethod
    def validate_password(update, context):
        user = update.message.from_user
        password = update.message.text

        # Allowing users to register only with this specific password
        if password == 'KingofLion':
            # replace_one will create one if no results found in filter
            replace_filter = {'user_name': user.name}

            # Using private attr because of bad API
            context._dispatcher.mongo_db.telegram_users.replace_one(replace_filter,
                                                                    {'user_name': user.name, 'chat_id': user.id},
                                                                    upsert=True)

            logging.info("{user_name} of {chat_id} registered".format(user_name=user.name, chat_id=user.id))

            update.message.reply_text('{user_name} Registered successfully'.format(user_name=user.name))
        else:
            logging.warning(
                "{user_name} of {chat_id} have tried to register with password: {password}".format(user_name=user.name,
                                                                                                   chat_id=user.id,
                                                                                                   password=password))
        return ConversationHandler.END

    @staticmethod
    def deregister(update, context):
        user = update.message.from_user
        try:
            # Using private attr because of bad API
            context._dispatcher.mongo_db.telegram_users.delete_one({'user_name': user.name})
            context._dispatcher.mongo_db.telegram_users.delete_one({'chat_id': user.id})

            logging.info("{user_name} of {chat_id} deregistered".format(user_name=user.name, chat_id=user.id))

            update.message.reply_text('{user_name} Deregistered successfully'.format(user_name=user.name))

        except Exception as e:
            update.message.reply_text(
                '{user_name} couldn\'t register, please contact the support team'.format(user_name=user.name))
            logging.exception(e.__traceback__)

    @staticmethod
    def alerts(update, context):
        user = update.message.from_user

        if Bot.__is_registered(context._dispatcher.mongo_db, user.name, user.id):
            update.message.reply_text('Insert a valid OTC ticker')
            return PRINT_HISTORY
        else:
            update.message.reply_text('You need to be registered in order to use this. Check /register for more info')
            return ConversationHandler.END

    @staticmethod
    def invalid_ticker_format(update, context):
        update.message.reply_text('Invalid input, please insert 3-5 letters OTC registered ticker')

        return ConversationHandler.END

    @staticmethod
    def alerts_request(update, context):
        ticker = update.message.text.upper()

        try:
            alerts_df = Client.get_diffs(context._dispatcher.mongo_db, ticker)

            Bot.send_df(alerts_df, ticker, update.message.reply_document)

        except Exception as e:
            logging.exception(e, exc_info=True)
            update.message.reply_text("Couldn't produce alerts for {ticker}".format(ticker=ticker))

        return ConversationHandler.END

    @staticmethod
    def dd_request(update, context):
        ticker = update.message.text.upper()

        try:
            dd_df = Client.get_history(context._dispatcher.mongo_db, ticker)

            Bot.send_df(dd_df, ticker, update.message.reply_document)

        except Exception as e:
            logging.exception(e, exc_info=True)
            update.message.reply_text("Couldn't produce alerts for {ticker}".format(ticker=ticker))

        return ConversationHandler.END

    @staticmethod
    def dd(update, context):
        user = update.message.from_user

        if Bot.__is_registered(context._dispatcher.mongo_db, user.name, user.id):
            update.message.reply_text('Insert a valid OTC ticker')
            return PRINT_HISTORY
        else:
            update.message.reply_text('You need to be registered in order to use this. Check /register for more info')
            return ConversationHandler.END

    @staticmethod
    def send_df(df, name, func, **kwargs):
        image_path = Bot.TEMP_IMAGE_PATH_FORMAT.format(name=name)

        # Converting to image because dataframe isn't shown well in telegram
        dfi.export(df, image_path, max_rows=100, max_cols=100)

        with open(image_path, 'rb') as image:
            func(document=image, **kwargs)

        os.remove(image_path)

    @staticmethod
    def __is_registered(mongo_db, user_name, chat_id):
        return bool(mongo_db.telegram_users.find_one({'user_name': user_name, 'chat_id': chat_id}))


def main():
    try:
        Bot().run()
    except Exception as e:
        logging.exception(e)


if __name__ == '__main__':
    main()
