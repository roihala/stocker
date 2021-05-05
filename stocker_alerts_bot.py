#!/usr/bin/env python
# -*- coding: utf-8 -*-
import logging
import os

import dataframe_image as dfi
import telegram
from src.factory import Factory
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, ConversationHandler, CallbackQueryHandler
from telegram import InlineKeyboardMarkup

from client import Client
from runnable import Runnable
from src.read import readers

PRINT_DD, GET_TOPIC, PRINT_ALERTS, PRINT_INFO, VALIDATE_PASSWORD, BROADCAST_MSG, REGISTER = range(7)

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

        start_conv = ConversationHandler(
            entry_points=[CommandHandler('start', Bot.start)],
            states={
                REGISTER: [CallbackQueryHandler(Bot.register_callback)],
                VALIDATE_PASSWORD: [MessageHandler(Filters.regex('^[a-zA-Z_ ]*$'), Bot.validate_password)]
            },
            fallbacks=[]
        )

        alerts_conv = ConversationHandler(
            entry_points=[CommandHandler('alerts', Bot.alerts)],
            states={
                # Allowing 3-5 letters
                PRINT_ALERTS: [MessageHandler(Filters.regex('^[a-zA-Z]{3,5}$'), Bot.alerts_request),
                           MessageHandler(~Filters.regex('^[a-zA-Z]{3,5}$'), Bot.invalid_ticker_format)]
            },
            fallbacks=[],
        )

        info_conv = ConversationHandler(
            entry_points=[CommandHandler('info', Bot.info)],
            states={
                # Allowing 3-5 letters
                PRINT_INFO: [MessageHandler(Filters.regex('^[a-zA-Z]{3,5}$'), Bot.info_request),
                               MessageHandler(~Filters.regex('^[a-zA-Z]{3,5}$'), Bot.invalid_ticker_format)]
            },
            fallbacks=[],
        )

        dd_conv = ConversationHandler(
            entry_points=[CommandHandler('dd', Bot.dd)],
            states={
                # Allowing 3-5 letters
                GET_TOPIC: [MessageHandler(Filters.regex('^[a-zA-Z]{3,5}$'), Bot.get_topic),
                            MessageHandler(~Filters.regex('^[a-zA-Z]{3,5}$'), Bot.invalid_ticker_format)],
                PRINT_DD: [CallbackQueryHandler(Bot.dd_callback)]
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

        broadcast_conv = ConversationHandler(
            entry_points=[CommandHandler('broadcast', Bot.broadcast)],
            states={
                # Allowing letters and whitespaces
                BROADCAST_MSG: [MessageHandler(Filters.text, Bot.send_broadcast_msg)]
            },
            fallbacks=[],
        )

        dp.add_handler(start_conv)
        dp.add_handler(alerts_conv)
        dp.add_handler(info_conv)
        dp.add_handler(register_conv)
        dp.add_handler(dd_conv)
        dp.add_handler(broadcast_conv)

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
    Please use one of the following commands:

/register - Register to get alerts on updates straight to your telegram account.
/alerts - Previously detected alerts for a given ticker.
/dd - Dig in to updates that weren't alerted.
/deregister - Do this to stop getting alerts from stocker. *not recommended*.
    '''

        if Bot.__is_high_permission_user(context._dispatcher.mongo_db, user.name, user.id):
            start_msg += '\n    /broadcast - Send meesages to all users'

        keyboard = InlineKeyboardMarkup([
            [telegram.InlineKeyboardButton("register", callback_data='register')]])

        update.message.reply_text(start_msg,
                                  parse_mode=telegram.ParseMode.MARKDOWN,
                                  reply_markup=keyboard)
        return REGISTER

    @staticmethod
    def register_callback(update, context):
        try:
            # If trying to register by the 'register' button on /start
            if update.callback_query.data == 'register':
                update.callback_query.message.reply_text('Insert password please')
                return VALIDATE_PASSWORD
            else:
                return ConversationHandler.END
        except Exception as e:
            update.message.reply_text(
                '{user_name} couldn\'t register, please contact the support team'.format(
                    user_name=update.message.from_user))
            context._dispatcher.logger.exception(e.__traceback__)
            return ConversationHandler.END

    @staticmethod
    def register(update, context):
        try:
            update.message.reply_text('Insert password please')
            return VALIDATE_PASSWORD
        except Exception as e:
            update.message.reply_text(
                '{user_name} couldn\'t register, please contact the support team'.format(
                    user_name=update.message.from_user))
            context._dispatcher.logger.exception(e.__traceback__)
            return ConversationHandler.END

    @staticmethod
    def validate_password(update, context):
        user = update.message.from_user
        password = update.message.text

        # Allowing users to register only with this specific password
        if password == 'KingofLion':
            # replace_one will create one if no results found in filter
            replace_filter = {'chat_id': user.id}

            # Using private attr because of bad API
            context._dispatcher.mongo_db.telegram_users.replace_one(replace_filter,
                                                                    {'chat_id': user.id, 'user_name': user.name,
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
            update.message.reply_text('Wrong password, please make sure you have the correct credentials for this bot!')
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
            update.message.reply_text('Insert a valid OTC ticker')

            return PRINT_ALERTS
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
            'Invalid input. Please choose one of this collections: {}'.format(Factory.TICKER_COLLECTIONS.keys()))

        return ConversationHandler.END

    @staticmethod
    def alerts_request(update, context):
        user = update.message.from_user
        ticker = update.message.text.upper()
        update.message.reply_text("This operation might take some time...")

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
    def get_topic(update, context):
        ticker = update.message.text.upper()
        context.user_data["ticker"] = ticker

        keyboard = InlineKeyboardMarkup([
            [telegram.InlineKeyboardButton("Share Structure", callback_data='ss'),
             telegram.InlineKeyboardButton("Company Profile", callback_data='profile')]])

        update.message.reply_text('Please Choose a topic:',
                                  reply_markup=keyboard)

        return PRINT_DD

    @staticmethod
    def dd_callback(update, context):
        topic = update.callback_query.data
        update.callback_query.answer()
        ticker = context.user_data["ticker"]

        try:
            dd_df = None
            update.callback_query.message.reply_text("This operation might take some time...")

            if topic == 'ss':
                dd_df = readers.Securities(mongo_db=context._dispatcher.mongo_db, ticker=ticker)\
                    .get_sorted_history(filter_rows=True, filter_cols=True)
            elif topic == 'profile':
                profile_df = readers.Profile(mongo_db=context._dispatcher.mongo_db, ticker=ticker) \
                    .get_sorted_history(filter_rows=True, filter_cols=True)
                symbols_df = readers.Symbols(mongo_db=context._dispatcher.mongo_db, ticker=ticker) \
                    .get_sorted_history(filter_rows=True, filter_cols=True)

                # TODO
                dd_df = profile_df.join(symbols_df, how='outer', lsuffix='_1')

            if dd_df is None:
                update.callback_query.message.reply_text("Couldn't get /dd for {ticker}".format(ticker=ticker, topic=topic))
                context._dispatcher.logger.warning("Couldn't generate /dd for {ticker} on {topic} topic".format(ticker=ticker, topic=topic))
                return ConversationHandler.END

            Bot.send_df(dd_df, ticker, update.callback_query.message.reply_document, reply_markup=telegram.ReplyKeyboardRemove())

        except Exception as e:
            context._dispatcher.logger.exception(e, exc_info=True)
            update.callback_query.message.reply_text("Couldn't produce {topic} for {ticker}".format(ticker=ticker,
                                                                                                    topic=topic))

        return ConversationHandler.END

    @staticmethod
    def dd(update, context):
        user = update.message.from_user

        if Bot.__is_registered(context._dispatcher.mongo_db, user.name, user.id):
            update.message.reply_text('Insert a valid OTC ticker')

            return GET_TOPIC
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
    def info(update, context):
        user = update.message.from_user

        if Bot.__is_registered(context._dispatcher.mongo_db, user.name, user.id):
            update.message.reply_text('Insert a valid OTC ticker')

            return PRINT_INFO
        else:
            update.message.reply_text('You need to be registered in order to use this. Check /register for more info')
            return ConversationHandler.END

    @staticmethod
    def info_request(update, context):
        user = update.message.from_user
        ticker = update.message.text.upper()

        try:
            context._dispatcher.logger.info("{user_name} of {chat_id} have used /info on ticker: {ticker}".format(
                user_name=user.name,
                chat_id=user.id,
                ticker=ticker
            ))

            update.message.reply_text(Client.info(context._dispatcher.mongo_db, ticker))

        except Exception as e:
            context._dispatcher.logger.exception(e, exc_info=True)
            update.message.reply_text("Couldn't produce info for {ticker}".format(ticker=ticker))

        return ConversationHandler.END

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
        return ConversationHandler.END

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
