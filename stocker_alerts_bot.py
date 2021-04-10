#!/usr/bin/env python
# -*- coding: utf-8 -*-
import logging
import os

import dataframe_image as dfi
import telegram
from src.factory import Factory
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, ConversationHandler, CallbackQueryHandler
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from client import Client
from runnable import Runnable

PRINT_HISTORY, GET_COLLECTION, GENDER, LOCATION, BIO = range(5)

VALIDATE_PASSWORD, STAM = range(2)

BROADCAST_MSG, STAM = range(2)

REGISTER = range(1)

LOGGER_PATH = os.path.join(os.path.dirname(__file__), 'stocker_alerts_bot.log')


class Bot(Runnable):
    TEMP_IMAGE_FILE_FORMAT = '{name}.png'

    def run(self):
        if os.getenv('TELEGRAM_TOKEN') is not None:
            updater = Updater(os.getenv('TELEGRAM_TOKEN'))
        else:
            updater = Updater(self.args.token)

        dp = updater.dispatcher

        # Bad APIs make bad workarounds
        setattr(dp, 'mongo_db', self._mongo_db)
        setattr(dp, 'logger', self.logger)

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
                GET_COLLECTION: [MessageHandler(Filters.regex('^[a-zA-Z]{3,5}$'), Bot.get_collection),
                                 MessageHandler(~Filters.regex('^[a-zA-Z]{3,5}$'), Bot.invalid_ticker_format)],
                PRINT_HISTORY: [MessageHandler(Filters.text(Factory.COLLECTIONS.keys()), Bot.dd_request),
                                MessageHandler(~Filters.text(Factory.COLLECTIONS.keys()), Bot.invalid_collection)]
            },
            fallbacks=[],
        )

        register_conv = ConversationHandler(
            entry_points=[CommandHandler('register', Bot.register),
                          CallbackQueryHandler(Bot.register)],
            states={
                # Allowing letters and whitespaces
                VALIDATE_PASSWORD: [MessageHandler(Filters.regex('^[a-zA-Z_ ]*$'), Bot.validate_password)]
            },
            fallbacks=[],
        )

        broadcast_conv = ConversationHandler(
            entry_points=[CommandHandler('broadcast', Bot.broadcast)],
            states={
                # Allowing letters and whitespaces
                BROADCAST_MSG: [MessageHandler(Filters.regex('^[a-zA-Z_ ]*$'), Bot.send_broadcast_msg)]
            },
            fallbacks=[],
        )

        # dp.add_handler(start_conv)
        dp.add_handler(register_conv)
        dp.add_handler(alerts_conv)
        dp.add_handler(dd_conv)
        dp.add_handler(broadcast_conv)

        dp.add_handler(CommandHandler('start', Bot.start))
        dp.add_handler(CommandHandler('deregister', Bot.deregister))
        dp.add_handler(CommandHandler('broadcast', Bot.broadcast))

        # Start the Bot
        updater.start_polling()

        # Run the bot until you press Ctrl-C or the process receives SIGINT,
        # SIGTERM or SIGABRT. This should be used most of the time, since
        # start_polling() is non-blocking and will stop the bot gracefully.
        updater.idle()

    @staticmethod
    def start(update, context):
        user = update.message.from_user
        start_msg = '''   
    Stocker alerts bot currently supports the following commands:

    /register - Register to get alerts on modifications straight to your telegram account.
    /deregister - Do this to stop getting alerts from stocker. *not recommended*
    /history - Get the saved history of a certain stock, note that columns with no changes will be removed.
    /alerts - Get every alert that stocker has detected for a specific ticker.'''

        if Bot.__is_high_permission_user(context._dispatcher.mongo_db, user.name, user.id):
            start_msg += '\n    /broadcast - Send meesages to all users'

        keyboard = InlineKeyboardMarkup([
            [telegram.InlineKeyboardButton("register", callback_data='register')]])

        update.message.reply_text(start_msg,
                                  parse_mode=telegram.ParseMode.MARKDOWN,
                                  reply_markup=keyboard)
        return REGISTER

    @staticmethod
    def register(update, context):
        try:
            # If trying to register by the 'register' button on /start
            if update.callback_query:
                update.callback_query.message.reply_text('Insert password please')
            else:
                update.message.reply_text('Insert password please')
            return VALIDATE_PASSWORD
        except Exception as e:
            update.message.reply_text(
                '{user_name} couldn\'t register, please contact the support team'.format(
                    user_name=update.message.from_user))
            context._dispatcher.logger.exception(e.__traceback__)

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
                                                                    {'user_name': user.name, 'chat_id': user.id,
                                                                     'delay': True},
                                                                    upsert=True)

            context._dispatcher.logger.info(
                "{user_name} of {chat_id} registered".format(user_name=user.name, chat_id=user.id))

            update.message.reply_text('{user_name} Registered successfully'.format(user_name=user.name))
        else:
            context._dispatcher.logger.warning(
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

            context._dispatcher.logger.info(
                "{user_name} of {chat_id} deregistered".format(user_name=user.name, chat_id=user.id))

            update.message.reply_text('{user_name} Deregistered successfully'.format(user_name=user.name))

        except Exception as e:
            update.message.reply_text(
                '{user_name} couldn\'t register, please contact the support team'.format(user_name=user.name))
            context._dispatcher.logger.exception(e.__traceback__)

    @staticmethod
    def alerts(update, context):
        user = update.message.from_user

        if Bot.__is_registered(context._dispatcher.mongo_db, user.name, user.id):
            kb = telegram.ReplyKeyboardMarkup(
                [[telegram.KeyboardButton(collection)] for collection in Factory.COLLECTIONS.keys()])
            update.message.reply_text('Insert a valid OTC ticker',
                                      reply_markup=kb)

            return PRINT_HISTORY
        else:
            update.message.reply_text('You need to be registered in order to use this. Check /register for more info')
            return ConversationHandler.END

    @staticmethod
    def invalid_ticker_format(update, context):
        update.message.reply_text('Invalid input, please insert 3-5 letters OTC registered ticker')

        return ConversationHandler.END

    @staticmethod
    def invalid_collection(update, context):
        update.message.reply_text(
            'Invalid input. Please choose one of this collections: {}'.format(Factory.COLLECTIONS.keys()))

        return ConversationHandler.END

    @staticmethod
    def alerts_request(update, context):
        user = update.message.from_user
        ticker = update.message.text.upper()

        try:
            context._dispatcher.logger.info("{user_name} of {chat_id} have used /alerts on ticker: {ticker}".format(
                user_name=user.name,
                chat_id=user.id,
                ticker=ticker
            ))
            alerts_df = Client.get_diffs(context._dispatcher.mongo_db, ticker)

            Bot.send_df(alerts_df, ticker, update.message.reply_document)

        except Exception as e:
            context._dispatcher.logger.exception(e, exc_info=True)
            update.message.reply_text("Couldn't produce alerts for {ticker}".format(ticker=ticker))

        return ConversationHandler.END

    @staticmethod
    def get_collection(update, context):
        ticker = update.message.text.upper()

        context.user_data["ticker"] = ticker

        kb = telegram.ReplyKeyboardMarkup(
            [[telegram.KeyboardButton(collection)] for collection in Factory.COLLECTIONS.keys()])
        update.message.reply_text('Choose a collection.',
                                  reply_markup=kb)

        return PRINT_HISTORY

    @staticmethod
    def dd_request(update, context):
        collection = update.message.text
        ticker = context.user_data["ticker"]

        try:
            update.message.reply_text("This action might take some time...",
                                      reply_markup=telegram.ReplyKeyboardRemove())
            dd_df = Client.get_history(context._dispatcher.mongo_db, ticker)
            if len(dd_df.index) == 0:
                update.message.reply_text("{} does not have any history for {} collection.".format(ticker, collection),
                                          reply_markup=telegram.ReplyKeyboardRemove())
                return ConversationHandler.END

            dd_df = dd_df[(dd_df.source == collection)]

            Bot.send_df(dd_df, ticker, update.message.reply_document, reply_markup=telegram.ReplyKeyboardRemove())

        except Exception as e:
            context._dispatcher.logger.exception(e, exc_info=True)
            update.message.reply_text("Couldn't produce alerts for {ticker}".format(ticker=ticker),
                                      reply_markup=telegram.ReplyKeyboardRemove())

        return ConversationHandler.END

    @staticmethod
    def dd(update, context):
        user = update.message.from_user

        if Bot.__is_registered(context._dispatcher.mongo_db, user.name, user.id):
            update.message.reply_text('Insert a valid OTC ticker')

            return GET_COLLECTION
        else:
            update.message.reply_text('You need to be registered in order to use this. Check /register for more info')
            return ConversationHandler.END

    @staticmethod
    def send_df(df, name, func, **kwargs):
        image_path = Bot.TEMP_IMAGE_FILE_FORMAT.format(name=name)

        # Converting to image because dataframe isn't shown well in telegram
        dfi.export(df, image_path, table_conversion="matplotlib")

        with open(image_path, 'rb') as image:
            func(document=image, **kwargs)

        os.remove(image_path)

    @staticmethod
    def __is_registered(mongo_db, user_name, chat_id):
        return bool(mongo_db.telegram_users.find_one({'user_name': user_name, 'chat_id': chat_id}))

    @staticmethod
    def broadcast(update, context):
        try:
            update.message.reply_text('Insert broadcast message please')
            return BROADCAST_MSG
        except Exception as e:
            update.message.reply_text(
                '{user_name} couldn\'t register, please contact the support team'.format(
                    user_name=update.message.from_user))
            context._dispatcher.logger.exception(e.__traceback__)

    @staticmethod
    def send_broadcast_msg(update, context):
        from_user = update.message.from_user
        broadcast_msg = update.message.text

        if Bot.__is_high_permission_user(context._dispatcher.mongo_db, from_user.name, from_user.id):
            for to_user in context._dispatcher.mongo_db.telegram_users.find():
                bot_instance = update.message.bot
                try:
                    bot_instance.sendMessage(chat_id=to_user['chat_id'], text=broadcast_msg)
                except telegram.error.BadRequest:
                    context._dispatcher.logger.warning(
                        "{user_name} of {chat_id} not found during broadcast message sending.".format(
                            user_name=to_user['user_name'],
                            chat_id=to_user['chat_id']))
            update.message.reply_text('Your message have been sent to all of the stocker bot users.')
        else:
            update.message.reply_text('Your user do not have the sufficient permissions to run this command.')
            context._dispatcher.logger.warning(
                "{user_name} of {chat_id} have tried to run an high permission user command".format(
                    user_name=from_user.name,
                    chat_id=from_user.id))

    @staticmethod
    def __is_high_permission_user(mongo_db, user_name, chat_id):
        return bool(
            mongo_db.telegram_users.find_one({'user_name': user_name, 'chat_id': chat_id, 'permissions': 'high'}))


def main():
    try:
        Bot().run()
    except Exception as e:
        logging.exception(e)


if __name__ == '__main__':
    main()
