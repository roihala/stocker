#!/usr/bin/env python
# -*- coding: utf-8 -*-
import secrets

import argon2
import logging
import os
import arrow
from functools import reduce

import dataframe_image as dfi
import plotly.express as px
import telegram
from telegram.utils import helpers as telegram_helpers
from argon2.exceptions import VerifyMismatchError, VerificationError

from src.alert.alerter_base import AlerterBase
from src.factory import Factory
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, ConversationHandler, CallbackQueryHandler
from telegram import InlineKeyboardMarkup

from client import Client
from runnable import Runnable
from src.read import readers
from alert import Alert
from src.rest import ActivationCodes

CHOOSE_TOOL, PRINT_ALERTS, PRINT_INFO, BROADCAST_MSG, TWEET_MSG, DO_FREE_TRIAL, CONVERSATION_CALLBACK, PRINT_DILUTION = range(8)

# Actions
FREE_TRIAL, TOOLS, BACK, INFO, ALERTS, DILUTION, ACTIVATE, AGREE = (
    'free_trial', 'tools', 'back', 'info', 'alerts', 'dilution', 'activate', 'agree')

LOGGER_PATH = os.path.join(os.path.dirname(__file__), 'stocker_alerts_bot.log')


class Bot(Runnable):
    CHECK_MARK_EMOJI_UNICODE = u'\U00002705'
    HEART_EMOJI_UNICODE = u'\U00002764'
    PUNCH_EMOJI_UNICODE = u'\U0001F44A'
    FIRE_EMOJI_UNICODE = u'\U0001F525'

    START_MESSAGE = '''
The following commands will make me sing:

/register - Register to get alerts on updates straight to your telegram account.
/tools - User friendly interface for reaching our tools  

/alerts - Resend previously detected alerts for a given ticker.
/deregister - Do this to stop getting alerts from stocker. *not recommended*.
/dilution - A graph of changes in AS/SS/unrestricted over time
/info - View the LATEST information for a given ticker.
    '''
    PAYMENT_URL = 'https://www.stocker.watch/plans-pricing'
    STOCKER_URL = 'https://www.stocker.watch'
    MARKET_EYES_URL = 'https://t.me/EyesOnMarket'
    TWITTER_URL = 'https://twitter.com/EyesOnMarket'

    JUDIT_FREE_TRIAL = 'c92be8609f80cac1aa96bad370acd64761836bd3f62de0cb448690de81c3a865'
    WEBSITE_FREE_TRIAL = 'free_trial'

    TEMP_IMAGE_FILE_FORMAT = '{name}.png'
    MAX_MESSAGE_LENGTH = 4096

    CONTACT_BUTTON = telegram.InlineKeyboardButton("Contact", url=MARKET_EYES_URL)
    TERMS_BUTTON = telegram.InlineKeyboardButton("Terms and conditions", url="http://tinyurl.com/agreemant")
    TOOLS_BUTTON = telegram.InlineKeyboardButton("Tools", callback_data=TOOLS)
    SUBSCRIBE_BUTTON = telegram.InlineKeyboardButton("Subscribe", url=PAYMENT_URL)
    FREE_TRIAL_BUTTON = telegram.InlineKeyboardButton("Free trial", callback_data=FREE_TRIAL)
    BACK_BUTTON = telegram.InlineKeyboardButton("« Back to start menu", callback_data=BACK)

    START_KEYBOARD = InlineKeyboardMarkup([[FREE_TRIAL_BUTTON, TOOLS_BUTTON]])
    SUBSCRIBE_KEYBOARD = InlineKeyboardMarkup([[CONTACT_BUTTON, SUBSCRIBE_BUTTON]])
    TOOLS_KEYBOARD = InlineKeyboardMarkup([[TOOLS_BUTTON]])

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
                          CommandHandler('Start', Bot.start_command),
                          CommandHandler('launch', Bot.launch_command)],
            states={
                # START_CALLBACK: [CallbackQueryHandler(Bot.start_callback)],
                CONVERSATION_CALLBACK: [CallbackQueryHandler(Bot.conversation_callback)],
                CHOOSE_TOOL: [MessageHandler(Filters.regex('^/tools|/start$'), Bot.tools)],

                PRINT_INFO: [MessageHandler(Filters.regex('^[a-zA-Z]{3,5}$'), Bot.info_callback),
                             MessageHandler(~Filters.regex('^[a-zA-Z]{3,5}$'), Bot.invalid_ticker_format)],
                DO_FREE_TRIAL: [MessageHandler(Filters.regex('.*'), Bot.free_trial_callback)],
                PRINT_DILUTION: [MessageHandler(Filters.regex('^[a-zA-Z]{3,5}$'), Bot.dilution_callback),
                                 MessageHandler(~Filters.regex('^[a-zA-Z]{3,5}$'), Bot.invalid_ticker_format)],
                PRINT_ALERTS: [MessageHandler(Filters.regex('^[a-zA-Z]{3,5}$'), Bot.alerts_callback),
                               MessageHandler(~Filters.regex('^[a-zA-Z]{3,5}$'), Bot.invalid_ticker_format)]
            },

            fallbacks=[MessageHandler(Filters.regex('^/tools|/start$'), Bot.conversation_fallback)]
        )

        broadcast_conv = ConversationHandler(
            entry_points=[CommandHandler('broadcast', Bot.broadcast),
                          CommandHandler('launch_tweet', Bot.launch_tweet)],
            states={
                # Allowing letters and whitespaces
                BROADCAST_MSG: [MessageHandler(Filters.text, Bot.broadcast_callback)],
                TWEET_MSG: [MessageHandler(Filters.text, Bot.tweet_callback)]
            },
            fallbacks=[],
        )
        # Re adding start command to allow deep linking
        dp.add_handler(tools_conv)

        dp.add_handler(CommandHandler('start', Bot.start_command))
        dp.add_handler(broadcast_conv)

        dp.add_handler(CommandHandler('dilution', Bot.dilution_command))
        dp.add_handler(CommandHandler('alerts', Bot.alerts_command))
        dp.add_handler(CommandHandler('info', Bot.info_command))
        dp.add_handler(CommandHandler('deregister', Bot.deregister))
        dp.add_handler(CommandHandler('broadcast', Bot.broadcast))
        dp.add_handler(CommandHandler('launch', Bot.launch_command))
        dp.add_handler(CommandHandler('vip_user', Bot.vip_user))



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
        # This is how we support deep linking
        if len(update.message.text.split(' ')) == 2:
            value = update.message.text.split(' ')[1]
            if value in [Bot.JUDIT_FREE_TRIAL, Bot.WEBSITE_FREE_TRIAL]:
                weeks = 4 if Bot.JUDIT_FREE_TRIAL else 2
                if value == Bot.JUDIT_FREE_TRIAL:
                    source = 'judit'
                elif value == Bot.WEBSITE_FREE_TRIAL:
                    source = 'website'
                else:
                    source = 'default'

                Bot.free_trial(update.message, update.message.from_user, context, weeks=weeks, source=source)
            else:
                Bot.activate_token(update, update.message.text.split(' ')[1], context)
        else:
            Bot.start(update.message, update.message.from_user, context)

        return CONVERSATION_CALLBACK

    @staticmethod
    def activate_token(update, token, context) -> None:
        from_user = update.message.from_user
        mongo_db = context._dispatcher.mongo_db

        token_verified, token_occupied, user_document = Bot.__verify_token(token, mongo_db)

        msg = Bot.__get_registration_message(token_verified, token_occupied, from_user, mongo_db, token)

        if token_verified and not token_occupied:
            Bot.__user_agreemant(update.message, context, args={'activation': ActivationCodes.ACTIVE, 'update_query': user_document, 'delete_other_documents': True})

        else:
            update.message.reply_text(msg, parse_mode=telegram.ParseMode.MARKDOWN, reply_markup=Bot.SUBSCRIBE_KEYBOARD)

    @staticmethod
    def start(message, from_user, context, edit_message=False):
        start_msg = Bot.START_MESSAGE

        if Bot.__is_high_permission_user(context._dispatcher.mongo_db, from_user.name, from_user.id):
            start_msg += '\n/broadcast - Send meesages to all users'

        keyboard = InlineKeyboardMarkup([
            [Bot.FREE_TRIAL_BUTTON, Bot.TOOLS_BUTTON]])

        if edit_message:
            message.delete()

        message.reply_text(start_msg,
                           parse_mode=telegram.ParseMode.MARKDOWN,
                           reply_markup=keyboard)

    @staticmethod
    def deregister(update, context):
        user = update.message.from_user
        try:
            context._dispatcher.mongo_db.telegram_users.update_one({'chat_id': user.id},
                                                                   {'$set': {'activation': ActivationCodes.DEREGISTER}})

            context._dispatcher.logger.info(
                "{user_name} of {chat_id} deregistered".format(user_name=user.name, chat_id=user.id))

            update.message.reply_text('{user_name} Deregistered successfully'.format(user_name=user.name))

        except Exception as e:
            update.message.reply_text(
                '{user_name} couldn\'t deregister, please contact the support team'.format(user_name=user.name))
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
            [telegram.InlineKeyboardButton("Alerts", callback_data=ALERTS),
             telegram.InlineKeyboardButton("Dilution", callback_data=DILUTION),
             telegram.InlineKeyboardButton("Info", callback_data=INFO)],
            [Bot.BACK_BUTTON]
        ])

        if edit_text:
            message.delete()
        message.reply_photo('https://static.wixstatic.com/media/7bd982_a90480838b0d431882413fd0414833a9~mv2.png',
                            reply_markup=keyboard)

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

        if update.callback_query.data == FREE_TRIAL:
            Bot.free_trial(query.message, query.from_user, context)
            return CONVERSATION_CALLBACK

        elif update.callback_query.data == TOOLS:
            Bot.tools(query.message, query.from_user, context, edit_text=True)
            return CONVERSATION_CALLBACK

        elif update.callback_query.data == BACK:
            Bot.start(query.message, query.from_user, context, edit_message=True)
            return CONVERSATION_CALLBACK

        elif update.callback_query.data == AGREE:
            Bot.__create_user(context, query.from_user.name, query.from_user.id, **context._dispatcher.activate_args)
            return CONVERSATION_CALLBACK

        query.message.reply_text('Please insert valid OTC ticker')
        if update.callback_query.data == INFO:
            return PRINT_INFO
        elif update.callback_query.data == ALERTS:
            return PRINT_ALERTS
        elif update.callback_query.data == DILUTION:
            return PRINT_DILUTION
        else:
            return ConversationHandler.END

    @staticmethod
    def free_trial_callback(update, context):
        query = update.callback_query
        query.answer()

        Bot.free_trial(query.message,
                       query.from_user,
                       context)

        return DO_FREE_TRIAL

    @staticmethod
    def free_trial(message, from_user, context, weeks=2, source='default'):
        try:
            user = context._dispatcher.mongo_db.telegram_users.find({'chat_id': from_user.id}).limit(1)[0]
        except IndexError:
            user = None

        if not user:
            Bot.__user_agreemant(message, context, {'activation': ActivationCodes.TRIAL, 'appendix': {'weeks': weeks, 'source': source}})

        else:
            if user.get('activation') in [ActivationCodes.TRIAL, ActivationCodes.ACTIVE]:
                msg = f'{from_user.name} is already registered!\n' \
                    'Try our tools for some cool stuff!'
                keyboard = Bot.TOOLS_KEYBOARD
            elif user.get('activation') in [ActivationCodes.CANCEL, ActivationCodes.DEREGISTER]:
                msg = f'{from_user.name} subscription has ended, please renew your subscription'
                keyboard = Bot.SUBSCRIBE_KEYBOARD
            elif user.get('activation') == ActivationCodes.UNREGISTER:
                msg = f'{from_user.name} free trial has ended\n' \
                    f'Please purchase subscription plan'
                keyboard = Bot.SUBSCRIBE_KEYBOARD
            elif user.get('activation') == ActivationCodes.PENDING:
                msg = f'{from_user.name} has pending subscription plan\n' \
                    f'Please check your email for activation'
                keyboard = InlineKeyboardMarkup([[Bot.CONTACT_BUTTON]])
            else:
                context._dispatcher.logger.warning(f"No activation for user: {user}")
                msg = f'An error has occurred, please contact us for further information'
                keyboard = InlineKeyboardMarkup([[Bot.CONTACT_BUTTON]])

            message.reply_text(msg, parse_mode=telegram.ParseMode.MARKDOWN, reply_markup=keyboard)

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
                  reduce(
                      lambda _, diff: _ + (Bot.__format_message(messages, diff) if diff.get('_id') in messages else ''),
                      diffs, '')

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
                .get_sorted_history(filter_rows=True, filter_cols=True).replace('', 0)

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
                '{user_name} couldn\'t broadcast, please contact the support team'.format(
                    user_name=update.message.from_user))
            context._dispatcher.logger.exception(e.__traceback__)

    @staticmethod
    def broadcast_callback(update, context):
        Bot.send_broadcast_msg(update.message, update.message.from_user, context, keyboard=Bot.TOOLS_KEYBOARD)
        pass

    @staticmethod
    def send_broadcast_msg(message, from_user, context, msg=None, keyboard=None):
        msg = msg if msg else message.text

        if Bot.__validate_permissions(message, from_user, context):
            for to_user in context._dispatcher.mongo_db.telegram_users.find():
                try:
                    if keyboard:
                        context._dispatcher.telegram_bot.send_message(
                            chat_id=to_user['chat_id'], text=msg,
                            parse_mode=telegram.ParseMode.MARKDOWN, reply_markup=keyboard)
                    else:
                        context._dispatcher.telegram_bot.send_message(chat_id=to_user['chat_id'], text=msg)
                except telegram.error.BadRequest:
                    context._dispatcher.logger.warning(
                        "{user_name} of {chat_id} not found during broadcast message sending.".format(
                            user_name=to_user['user_name'],
                            chat_id=to_user['chat_id']))
            message.reply_text('Your message have been sent to all of the stocker bot users.')

        return ConversationHandler.END

    @staticmethod
    def launch_tweet(update, context):
        update.message.reply_text('Insert tweet link')
        return TWEET_MSG

    @staticmethod
    def tweet_callback(update, context):
        msg = f"""Dear users, *I need your help*!
I uploaded a tweet about this launch and it would really help me if you could retweet :) 

LETS BURN THE TWITTER! {Bot.FIRE_EMOJI_UNICODE} {Bot.FIRE_EMOJI_UNICODE} {Bot.FIRE_EMOJI_UNICODE}"""

        keyboard = InlineKeyboardMarkup([[telegram.InlineKeyboardButton("Tweet", url=update.message.text)]])

        Bot.send_broadcast_msg(update.message, update.message.from_user, context, msg=msg, keyboard=keyboard)

    @staticmethod
    def vip_user(update, context):
        if not Bot.__is_high_permission_user(context._dispatcher.mongo_db, update.message.from_user.name, update.message.from_user.id):
            update.message.reply_text('This operation is only supported for high permission users')
            return

        token = secrets.token_urlsafe()

        document = {
            'token': argon2.PasswordHasher().hash(token),
            'date': arrow.utcnow().format(),
            'activation': ActivationCodes.PENDING
        }

        context._dispatcher.mongo_db.telegram_users.insert_one(document)

        update.message.reply_text(
            text=telegram_helpers.create_deep_linked_url(context._dispatcher.telegram_bot.username, token))

    @staticmethod
    def launch_command(update, context):
        if Bot.__validate_permissions(update.message, update.message.from_user, context):
            msg = f"""Dear users {Bot.PUNCH_EMOJI_UNICODE} 
I'm excited to tell you that great things are happening, and the greatest among them started because of your feedbacks, so thank you guys, *you are all marked as VIP users* {Bot.HEART_EMOJI_UNICODE}

Starting from today, Stocker Alerts will not remain a free bot! 
But for now, you can just click on free trial to get ADDITIONAL TWO WEEKS of free usage

Love you all and please keep sending us feedbacks, *We wont bite*"""
            keyboard = InlineKeyboardMarkup(
                [[Bot.FREE_TRIAL_BUTTON, telegram.InlineKeyboardButton("Stocker website", url=Bot.STOCKER_URL)]])

            Bot.send_broadcast_msg(update.message, update.message.from_user, context, msg=msg, keyboard=keyboard)
            Bot.__purge_telegram_users(context)

        return CONVERSATION_CALLBACK

    @staticmethod
    def __purge_telegram_users(context):
        mongo_db = context._dispatcher.mongo_db

        # nati, penny, balla
        vip_chat_ids = [480181908, 452073423, 907488369]
        # yoav, hala, mek
        non_delayed_vips = [564105605, 1151317792, 745230781]

        vip_users = []
        for user in mongo_db.telegram_users.find(
                {'chat_id': {'$in': vip_chat_ids + non_delayed_vips}}):
            if user.get('chat_id') in non_delayed_vips:
                delay = False
            else:
                delay = True

            document = Bot.__create_user(context, user.get('user_name'), user.get('chat_id'),
                                         delay=delay, activation=ActivationCodes.ACTIVE, create=False)
            # hala
            if user.get('chat_id') == 1151317792:
                document.update({'permissions': 'high'})

            vip_users.append(document)

        # Removing all users
        mongo_db.telegram_users.remove()
        mongo_db.telegram_users.insert_many(vip_users)

    @staticmethod
    def __validate_permissions(message, from_user, context):
        if Bot.__is_high_permission_user(context._dispatcher.mongo_db, from_user.name, from_user.id):
            return True
        else:
            message.reply_text('Your user do not have the sufficient permissions to run this command.')
            context._dispatcher.logger.warning(
                "{user_name} of {chat_id} have tried to run an high permission user command".format(
                    user_name=from_user.name,
                    chat_id=from_user.id))
            return False

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
        user = mongo_db.telegram_users.find_one({'user_name': user_name, 'chat_id': chat_id})

        if user and user.get('activation') in [ActivationCodes.ACTIVE, ActivationCodes.TRIAL]:
            return True
        return False

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

    @staticmethod
    def __log_telegram_action(mongo_db, user, action, is_success=False, payload='', appendix=''):
        mongo_db.telegram_actions.insert_one({
            'action': action,
            'date': arrow.utcnow().format(),
            'success': is_success,
            'chat_id': user.id,
            'user_name': user.name,
            'payload': payload,
            'appendix': appendix
        })

    @staticmethod
    def __get_registration_message(token_verified, token_occupied, from_user, mongo_db, token):
        if token_verified:
            if not token_occupied:
                Bot.__log_telegram_action(mongo_db, from_user, ACTIVATE, is_success=True, payload=token)
                return f'{Bot.CHECK_MARK_EMOJI_UNICODE} {from_user.name} *Verified successfully*.\n\n' \
                    "Please send us your feedbacks and suggestions, *we won't bite*"
            else:
                Bot.__log_telegram_action(mongo_db, from_user, ACTIVATE, is_success=True, payload=token,
                                          appendix='already_activated')
                return "This token was already activated, You may buy a new one or:\n" \
                       "Contact https://t.me/EyesOnMarket if you don't know why you're seeing this message"
        else:
            Bot.__log_telegram_action(mongo_db, from_user, ACTIVATE, payload=token)
            return 'Fuck off and pay like everybody else'

    @staticmethod
    def __verify_token(token, mongo_db):
        ph = argon2.PasswordHasher()
        token_verified = False
        token_occupied = False

        for user in mongo_db.telegram_users.find():
            try:
                if 'token' not in user:
                    continue

                # Comparing hashed token to obtained token
                token_verified = ph.verify(user['token'], token)

                # Verification succeed, checking if this token is occupied
                if 'chat_id' in user:
                    token_occupied = True

                return token_verified, token_occupied, user

            except (VerifyMismatchError, VerificationError):
                pass

        return token_verified, token_occupied, None

    @staticmethod
    def __create_user(context, user_name, chat_id, activation, delay=True, appendix: dict = None,
                      update_query=None, create=True, delete_other_documents=False):
        """

        :param user:
        :param activation: Activation code from the list below:

        TRIAL, ACTIVE, CANCEL, UNREGISTER, PENDING = ('frial', 'active', 'cancel', 'unregister', 'pending')
        :return:
        """
        user_document = {
            'user_name': user_name,
            'chat_id': chat_id,
            f'{activation}_date': arrow.utcnow().format(),
            'delay': delay,
            'activation': activation
        }
        if appendix:
            user_document.update({'appendix': appendix})

        if not create:
            return user_document

        if isinstance(update_query, dict):
            context._dispatcher.mongo_db.telegram_users.update_one(update_query, {'$set': user_document})
        else:
            context._dispatcher.mongo_db.telegram_users.insert_one(user_document)

        if delete_other_documents:
            for document in [user for user in context._dispatcher.mongo_db.telegram_users.find() if user.get('chat_id') == chat_id and ('token' not in user)]:
                context._dispatcher.mongo_db.telegram_users.delete_one(document)

        text = f"""Welcome to Stocker alerts, here's a quick how-to guide: 
1. The main part - our alerts:
From now on you will start getting alerts to this chat where: 
{AlerterBase.RED_CIRCLE_EMOJI_UNICODE} Means old value
{AlerterBase.GREEN_CIRCLE_EMOJI_UNICODE} Means new value

2. Our tools:
You may use them in different ways, the most popular is through /tools command.
For the more technical of you - there's a list of our supported commands in /start command
e.g:
/dilution SOAN
/alerts ggii

Good luck {Bot.HEART_EMOJI_UNICODE}
"""
        msg = context._dispatcher.telegram_bot.send_message(chat_id=chat_id, text=text, parse_mode=telegram.ParseMode.MARKDOWN, reply_markup=Bot.TOOLS_KEYBOARD)
        context._dispatcher.telegram_bot.pin_chat_message(chat_id=1151317792, message_id=msg.message_id)

    @staticmethod
    def __user_agreemant(message, context, args):
        setattr(context._dispatcher, 'activate_args', args)
        keyboard = InlineKeyboardMarkup([
            [telegram.InlineKeyboardButton("Agree", callback_data=AGREE),
             Bot.TERMS_BUTTON], [Bot.BACK_BUTTON]])

        message.reply_text("By clicking on \"Agree\" you agree to Stocker's terms of service, "
                           "which can be viewed by clicking on \"Terms and conditions\"", reply_markup=keyboard)


def main():
    try:
        Bot().run()
    except Exception as e:
        logging.exception(e)


if __name__ == '__main__':
    main()
