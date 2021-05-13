#!/usr/bin/env python
# -*- coding: utf-8 -*-
import logging
import os
import arrow
from functools import reduce

import dataframe_image as dfi
import plotly.express as px
import telegram

from src.factory import Factory
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, ConversationHandler, CallbackQueryHandler
from telegram import InlineKeyboardMarkup

from client import Client
from runnable import Runnable
from src.read import readers
from alert import Alert

CHOOSE_TOOL, START_CALLBACK, PRINT_ALERTS, PRINT_INFO, BROADCAST_MSG, REGISTER, CONVERSATION_CALLBACK, PRINT_DILUTION = range(
    8)

LOGGER_PATH = os.path.join(os.path.dirname(__file__), 'stocker_alerts_bot.log')


class Bot(Runnable):
    START_MESSAGE = '''
The following commands will make me sing:

/register - Register to get alerts on updates straight to your telegram account.
/tools - A user friendly interface for reaching our tools  

/alerts - Resend previously detected alerts for a given ticker.
/deregister - Do this to stop getting alerts from stocker. *not recommended*.
/dilution - A graph of changes in AS/SS/unrestricted over time
/info - View the LATEST information for a given ticker.
    '''

    TEMP_IMAGE_FILE_FORMAT = '{name}.png'
    MAX_MESSAGE_LENGTH = 4096

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

        tools_conv = ConversationHandler(
            entry_points=[CommandHandler('Tools', Bot.tools_command),
                          CommandHandler('Start', Bot.start_command)],
            states={
                # START_CALLBACK: [CallbackQueryHandler(Bot.start_callback)],
                CONVERSATION_CALLBACK: [CallbackQueryHandler(Bot.conversation_callback)],
                CHOOSE_TOOL: [MessageHandler(Filters.regex('^/tools|/start$'), Bot.tools)],

                PRINT_INFO: [MessageHandler(Filters.regex('^[a-zA-Z]{3,5}$'), Bot.info_callback),
                             MessageHandler(~Filters.regex('^[a-zA-Z]{3,5}$'), Bot.invalid_ticker_format)],
                REGISTER: [MessageHandler(Filters.regex('.*'), Bot.register_conv_callback)],
                PRINT_DILUTION: [MessageHandler(Filters.regex('^[a-zA-Z]{3,5}$'), Bot.dilution_callback),
                                 MessageHandler(~Filters.regex('^[a-zA-Z]{3,5}$'), Bot.invalid_ticker_format)],
                PRINT_ALERTS: [MessageHandler(Filters.regex('^[a-zA-Z]{3,5}$'), Bot.alerts_callback),
                               MessageHandler(~Filters.regex('^[a-zA-Z]{3,5}$'), Bot.invalid_ticker_format)]
            },

            fallbacks=[MessageHandler(Filters.regex('^/tools|/start$'), Bot.conversation_fallback)]
        )

        broadcast_conv = ConversationHandler(
            entry_points=[CommandHandler('broadcast', Bot.broadcast)],
            states={
                # Allowing letters and whitespaces
                BROADCAST_MSG: [MessageHandler(Filters.text, Bot.send_broadcast_msg)]
            },
            fallbacks=[],
        )

        dp.add_handler(tools_conv)
        dp.add_handler(broadcast_conv)

        dp.add_handler(CommandHandler('register', Bot.register_command))
        dp.add_handler(CommandHandler('dilution', Bot.dilution_command))
        dp.add_handler(CommandHandler('alerts', Bot.alerts_command))
        dp.add_handler(CommandHandler('info', Bot.info_command))
        dp.add_handler(CommandHandler('deregister', Bot.deregister))
        dp.add_handler(CommandHandler('broadcast', Bot.broadcast))

        # Start the Bot
        updater.start_polling()

        # Run the bot until you press Ctrl-C or the process receives SIGINT,
        # SIGTERM or SIGABRT. This should be used most of the time, since
        # start_polling() is non-blocking and will stop the bot gracefully.
        updater.idle()

    @staticmethod
    def conversation_fallback(update, context):
        if update.message.text == '/start':
            Bot.start(update.message, update.message.from_user, context)
        elif update.message.text == '/tools':
            Bot.tools(update.message, update.message.from_user, context)
        else:
            raise ValueError("Logic shouldn't get here")

        return CONVERSATION_CALLBACK

    @staticmethod
    def start_command(update, context):
        Bot.start(update.message, update.message.from_user, context)

        return CONVERSATION_CALLBACK

    @staticmethod
    def start(message, from_user, context, edit_text=False):
        start_msg = Bot.START_MESSAGE

        if Bot.__is_high_permission_user(context._dispatcher.mongo_db, from_user.name, from_user.id):
            start_msg += '\n/broadcast - Send meesages to all users'

        keyboard = InlineKeyboardMarkup([
            [telegram.InlineKeyboardButton("register", callback_data='register'),
             telegram.InlineKeyboardButton("tools", callback_data='tools')]])

        if edit_text:
            message.edit_text(start_msg,
                              parse_mode=telegram.ParseMode.MARKDOWN,
                              reply_markup=keyboard)
        else:
            message.reply_text(start_msg,
                               parse_mode=telegram.ParseMode.MARKDOWN,
                               reply_markup=keyboard)

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
    def tools_command(update, context):
        Bot.tools(update.message, update.message.from_user, context)

        return CONVERSATION_CALLBACK

    @staticmethod
    def tools(message, from_user, context, edit_text=False):
        if not Bot.__is_registered(context._dispatcher.mongo_db, from_user.name, from_user.id):
            message.reply_text('You need to be registered in order to use this. Check /register for more info')
            return ConversationHandler.END

        keyboard = InlineKeyboardMarkup([
            [telegram.InlineKeyboardButton("Alerts", callback_data='alerts'),
             telegram.InlineKeyboardButton("Dilution", callback_data='dilution'),
             telegram.InlineKeyboardButton("Info", callback_data='info')],
            [telegram.InlineKeyboardButton("« Back to start menu", callback_data='back')]
        ])

        msg = 'Please choose one of the following:'

        if edit_text:
            message.edit_text(msg, parse_mode=telegram.ParseMode.MARKDOWN, reply_markup=keyboard)
        else:
            message.reply_text(msg, parse_mode=telegram.ParseMode.MARKDOWN, reply_markup=keyboard)

    @staticmethod
    def invalid_ticker_format(update, context):
        update.message.reply_text('Invalid input, please insert 3-5 letters OTC registered ticker')

        return CONVERSATION_CALLBACK

    @staticmethod
    def invalid_collection(update, context):
        update.message.reply_text(
            'Invalid input. Please choose one of this collections: {}'.format(Factory.TICKER_COLLECTIONS.keys()))

        return ConversationHandler.END

    @staticmethod
    def conversation_callback(update, context):
        query = update.callback_query
        query.answer()

        if update.callback_query.data == 'register':
            Bot.register(query.message, query.from_user, context)
            return CONVERSATION_CALLBACK

        elif update.callback_query.data == 'tools':
            Bot.tools(query.message, query.from_user, context, edit_text=True)
            return CONVERSATION_CALLBACK

        elif update.callback_query.data == 'back':
            Bot.start(query.message, query.from_user, context, edit_text=True)
            return CONVERSATION_CALLBACK

        query.message.reply_text('Please insert valid OTC ticker')
        if update.callback_query.data == 'info':
            return PRINT_INFO
        elif update.callback_query.data == 'alerts':
            return PRINT_ALERTS
        elif update.callback_query.data == 'dilution':
            return PRINT_DILUTION
        else:
            return ConversationHandler.END

    @staticmethod
    def register_command(update, context):
        Bot.register(update.message,
                     update.message.from_user,
                     context)

    @staticmethod
    def register_callback(update, context):
        Bot.register(update.message,
                     update.message.from_user,
                     context)

        return CONVERSATION_CALLBACK

    @staticmethod
    def register_conv_callback(update, context):
        query = update.callback_query
        query.answer()

        Bot.register(query.message,
                     query.from_user,
                     context)

        return REGISTER

    @staticmethod
    def register(message, from_user, context):
        # replace_one will create one if no results found in filter
        replace_filter = {'chat_id': from_user.id}

        # Using private attr because of bad API
        context._dispatcher.mongo_db.telegram_users.replace_one(replace_filter,
                                                                {'chat_id': from_user.id, 'user_name': from_user.name,
                                                                 'delay': True},
                                                                upsert=True)

        context._dispatcher.logger.info(
            "{user_name} of {chat_id} registered".format(user_name=from_user.name, chat_id=from_user.id))

        message.reply_text('{user_name} Registered successfully'.format(user_name=from_user.name))

    @staticmethod
    def alerts_command(update, context):
        user = update.message.from_user
        ticker = Bot.__extract_ticker(context)

        if not ticker:
            update.message.reply_text("Couldn't detect ticker, Please try again by the format: /alerts TICKR")

        elif not Bot.__is_registered(context._dispatcher.mongo_db, user.name, user.id):
            update.message.reply_text('You need to be registered in order to use this. Check /register for more info')

        else:
            Bot.print_alerts(update.message,
                             update.message.from_user,
                             ticker,
                             context)

    @staticmethod
    def alerts_callback(update, context):
        ticker = update.message.text.upper()

        Bot.print_alerts(update.message,
                         update.message.from_user,
                         ticker,
                         context)

        return CONVERSATION_CALLBACK

    @staticmethod
    def print_alerts(message, from_user, ticker, context):
        try:
            pending_message = message.reply_text("This operation might take some time...")

            context._dispatcher.logger.info(
                "{user_name} of {chat_id} have used /alerts on ticker: {ticker}".format(
                    user_name=from_user.name,
                    chat_id=from_user.id,
                    ticker=ticker
                ))
            diffs = Client.get_diffs(context._dispatcher.mongo_db, ticker).to_dict('records')
            alerter_args = {'mongo_db': context._dispatcher.mongo_db, 'telegram_bot': context._dispatcher.telegram_bot,
                            'ticker': ticker, 'debug': context._dispatcher.debug}
            messages = Alert.generate_msg(diffs, alerter_args, as_dict=True)

            msg = Alert.generate_title(ticker, context._dispatcher.mongo_db) + '\n' + \
                  reduce(lambda _, diff: _ + (Bot.__format_message(messages, diff) if diff.get('_id') in messages else ''), diffs, '')

            if len(msg) > Bot.MAX_MESSAGE_LENGTH:
                pending_message.delete()
                Bot.__send_long_message(message.reply_text, msg, parse_mode=telegram.ParseMode.MARKDOWN)
            else:
                pending_message.edit_text(msg, parse_mode=telegram.ParseMode.MARKDOWN)

        except Exception as e:
            context._dispatcher.logger.exception(e, exc_info=True)
            message.reply_text("Couldn't produce alerts for {ticker}".format(ticker=ticker))

        return ConversationHandler.END

    @staticmethod
    def info_command(update, context):
        user = update.message.from_user
        ticker = Bot.__extract_ticker(context)

        if not ticker:
            update.message.reply_text("Couldn't detect ticker, Please try again by the format: /info TICKR")

        elif not Bot.__is_registered(context._dispatcher.mongo_db, user.name, user.id):
            update.message.reply_text('You need to be registered in order to use this. Check /register for more info')

        else:
            Bot.print_info(update.message,
                           update.message.from_user,
                           ticker,
                           context)

    @staticmethod
    def info_callback(update, context):
        ticker = update.message.text.upper()

        Bot.print_info(update.message,
                       update.message.from_user,
                       ticker,
                       context)

        return CONVERSATION_CALLBACK

    @staticmethod
    def print_info(message, from_user, ticker, context):
        try:
            context._dispatcher.logger.info(
                "{user_name} of {chat_id} have used /info on ticker: {ticker}".format(
                    user_name=from_user.name,
                    chat_id=from_user.id,
                    ticker=ticker
                ))

            # Escaping irrelevant markdown characters
            message.reply_text(Client.info(context._dispatcher.mongo_db, ticker),
                               parse_mode=telegram.ParseMode.MARKDOWN)

        except Exception as e:
            context._dispatcher.logger.exception(e, exc_info=True)
            message.reply_text("Couldn't produce info for {ticker}".format(ticker=ticker))

    @staticmethod
    def dilution_command(update, context):
        user = update.message.from_user
        ticker = Bot.__extract_ticker(context)

        if not ticker:
            update.message.reply_text("Couldn't detect ticker, Please try again by the format: /dilution TICKR")

        elif not Bot.__is_registered(context._dispatcher.mongo_db, user.name, user.id):
            update.message.reply_text('You need to be registered in order to use this. Check /register for more info')

        else:
            Bot.print_dilution(update.message,
                               update.message.from_user,
                               ticker,
                               context)

    @staticmethod
    def dilution_callback(update, context):
        ticker = update.message.text.upper()

        Bot.print_dilution(update.message,
                           update.message.from_user,
                           ticker,
                           context)

        return CONVERSATION_CALLBACK

    @staticmethod
    def print_dilution(message, from_user, ticker, context):
        pending_message = message.reply_text("This operation might take some time...")

        try:
            context._dispatcher.logger.info(
                "{user_name} of {chat_id} have used /dilution on ticker: {ticker}".format(
                    user_name=from_user.name,
                    chat_id=from_user.id,
                    ticker=ticker
                ))

            securities_df = readers.Securities(mongo_db=context._dispatcher.mongo_db, ticker=ticker) \
                .get_sorted_history(filter_rows=True, filter_cols=True)
            fig = px.line(securities_df, x="date",
                          y=[key for key in readers.Securities.DILUTION_KEYS if key in securities_df.columns],
                          title=ticker)
            Bot.send_df(securities_df, ticker, message.reply_document,
                        plotly_fig=fig, reply_markup=telegram.ReplyKeyboardRemove())

        except Exception as e:
            context._dispatcher.logger.exception(e, exc_info=True)
            message.reply_text("Couldn't produce dilution for {ticker}".format(ticker=ticker))

        pending_message.delete()
        return ConversationHandler.END

    @staticmethod
    def send_df(df, ticker, func, plotly_fig=None, **kwargs):
        image_path = Bot.TEMP_IMAGE_FILE_FORMAT.format(name=ticker)

        if plotly_fig:
            plotly_fig.write_image(image_path)
        else:
            # Converting to image because dataframe isn't shown well in telegram
            dfi.export(df, image_path, table_conversion="matplotlib")

        with open(image_path, 'rb') as image:
            func(document=image, **kwargs)

        os.remove(image_path)

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
        return ConversationHandler.END

    @staticmethod
    def __is_high_permission_user(mongo_db, user_name, chat_id):
        return bool(
            mongo_db.telegram_users.find_one({'user_name': user_name, 'chat_id': chat_id, 'permissions': 'high'}))

    @staticmethod
    def __send_long_message(func, msg, *args, **kwargs):
        for msg in [msg[i: i + Bot.MAX_MESSAGE_LENGTH] for i in range(0, len(msg), Bot.MAX_MESSAGE_LENGTH)]:
            func(msg, *args, **kwargs)

    @staticmethod
    def __is_registered(mongo_db, user_name, chat_id):
        return bool(mongo_db.telegram_users.find_one({'user_name': user_name, 'chat_id': chat_id}))

    @staticmethod
    def __format_message(messages, diff):
        # Add date and blank lines
        return f"{messages[diff.get('_id')]}\n_{arrow.get(diff.get('date')).to('Asia/Jerusalem').format()}_\n\n"

    @staticmethod
    def __extract_ticker(context):
        if len(context.args) == 1:
            ticker = context.args[0]
            if 4 <= len(ticker) <= 5 and all([char.isalpha() for char in ticker]):
                return ticker.upper()

        return None


def main():
    try:
        Bot().run()
    except Exception as e:
        logging.exception(e)


if __name__ == '__main__':
    main()
