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

from src.factory import Factory
from telegram.ext import ConversationHandler
from telegram import InlineKeyboardMarkup

from client import Client
from src.read import readers
from alert import Alert
from src.telegram_bot.resources.activation_kaki import ActivationCodes
from src.telegram_bot.resources.actions import Actions
from src.telegram_bot.resources.indexers import Indexers
from src.telegram_bot.resources.markup import Keyboards, Buttons
from src.telegram_bot.resources.messages import Messages


class BaseBot(object):
    def __init__(self, mongo_db, bot_instance, logger, debug):
        self.mongo_db = mongo_db
        self.bot_instance = bot_instance
        self.logger = logger
        self.debug = debug

    PAYMENT_URL = 'https://www.stocker.watch/plans-pricing'
    STOCKER_URL = 'https://www.stocker.watch'
    MARKET_EYES_URL = 'https://t.me/EyesOnMarket'
    TWITTER_URL = 'https://twitter.com/EyesOnMarket'

    JUDIT_FREE_TRIAL = 'c92be8609f80cac1aa96bad370acd64761836bd3f62de0cb448690de81c3a865'
    TWO_MONTHS_FREE_TRIAL = 'fe69f4558183d6307d988c11a8e0b42839a94fb6de371a1fc9f362f698465f7f'
    WEBSITE_FREE_TRIAL = 'free_trial'

    TEMP_IMAGE_FILE_FORMAT = '{name}.png'
    MAX_MESSAGE_LENGTH = 4096

    def conversation_fallback(self, update, context):
        if update.message.text == '/start':
            self.start(update.message, update.message.from_user)
        elif update.message.text == '/tools':
            self.tools(update.message, update.message.from_user)
        else:
            raise ValueError("Logic shouldn't get here")

        return Indexers.CONVERSATION_CALLBACK

    def start_command(self, update, context):
        # This is how we support deep linking
        if len(update.message.text.split(' ')) == 2:
            value = update.message.text.split(' ')[1]
            if value in [self.JUDIT_FREE_TRIAL, self.WEBSITE_FREE_TRIAL]:
                weeks = 2
                if value == self.JUDIT_FREE_TRIAL:
                    source = 'judit'
                    weeks = 4
                elif value == self.WEBSITE_FREE_TRIAL:
                    source = 'website'
                elif value == self.TWO_MONTHS_FREE_TRIAL:
                    source = 'special'
                    weeks = 8
                else:
                    source = 'default'

                self.free_trial(update.message, update.message.from_user, context, weeks=weeks, source=source)
            else:
                self.activate_token(update, update.message.text.split(' ')[1], context)
        else:
            self.start(update.message, update.message.from_user)

        return Indexers.CONVERSATION_CALLBACK

    def activate_token(self, update, token, context) -> None:
        from_user = update.message.from_user

        token_verified, token_occupied, user_document = self.__verify_token(token)

        msg = self.__get_registration_message(token_verified, token_occupied, from_user, token)

        if token_verified and not token_occupied:
            self.__user_agreemant(update.message, context,
                                  args={'activation': ActivationCodes.ACTIVE, 'update_query': user_document,
                                        'delete_other_documents': True})

        else:
            update.message.reply_text(msg, parse_mode=telegram.ParseMode.MARKDOWN,
                                      reply_markup=Keyboards.SUBSCRIBE_KEYBOARD)

    def start(self, message, from_user, edit_message=False):
        start_msg = Messages.START_MESSAGE

        if self.__is_high_permission_user(from_user.name, from_user.id):
            start_msg += '\n/broadcast - Send meesages to all users'

        keyboard = InlineKeyboardMarkup([
            [Buttons.FREE_TRIAL_BUTTON, Buttons.TOOLS_BUTTON]])

        if edit_message:
            message.delete()

        message.reply_text(start_msg,
                           parse_mode=telegram.ParseMode.MARKDOWN,
                           reply_markup=keyboard)

    def deregister(self, update, context):
        # TODO
        user = update.message.from_user
        try:
            self.mongo_db.telegram_users.update_one({'chat_id': user.id},
                                                    {'$set': {'activation': ActivationCodes.DEREGISTER}})

            self.logger.info(
                "{user_name} of {chat_id} deregistered".format(user_name=user.name, chat_id=user.id))

            update.message.reply_text('{user_name} Deregistered successfully'.format(user_name=user.name))

        except Exception as e:
            update.message.reply_text(
                '{user_name} couldn\'t deregister, please contact the support team'.format(user_name=user.name))
            self.logger.exception(e.__traceback__)

    def tools_command(self, update, context):
        self.tools(update.message, update.message.from_user)

        return Indexers.CONVERSATION_CALLBACK

    def tools(self, message, from_user, edit_text=False):
        if not self._is_registered(from_user.name, from_user.id):
            message.reply_text('You need to be registered in order to use this. Check /register for more info')
            return ConversationHandler.END

        keyboard = InlineKeyboardMarkup([
            [telegram.InlineKeyboardButton("Alerts", callback_data=Actions.ALERTS),
             telegram.InlineKeyboardButton("Dilution", callback_data=Actions.DILUTION),
             telegram.InlineKeyboardButton("Info", callback_data=Actions.INFO)],
            [Buttons.BACK_BUTTON]
        ])

        if edit_text:
            message.delete()
        message.reply_photo('https://static.wixstatic.com/media/7bd982_a90480838b0d431882413fd0414833a9~mv2.png',
                            reply_markup=keyboard)

    def conversation_callback(self, update, context):
        query = update.callback_query
        query.answer()

        if update.callback_query.data == Actions.FREE_TRIAL:
            self.free_trial(query.message, query.from_user, context)
            return Indexers.CONVERSATION_CALLBACK

        elif update.callback_query.data == Actions.TOOLS:
            self.tools(query.message, query.from_user, edit_text=True)
            return Indexers.CONVERSATION_CALLBACK

        elif update.callback_query.data == Actions.BACK:
            self.start(query.message, query.from_user, edit_message=True)
            return Indexers.CONVERSATION_CALLBACK

        elif update.callback_query.data == Actions.AGREE:
            # TODO
            self.__create_user(query.from_user.name, query.from_user.id, **context._dispatcher.activate_args)
            self.bot_instance.edit_message_reply_markup(chat_id=query.from_user.id,
                                                        message_id=query.message.message_id,
                                                        reply_markup=InlineKeyboardMarkup(
                                                            [[Buttons.TERMS_BUTTON], [Buttons.BACK_BUTTON]]))
            return Indexers.CONVERSATION_CALLBACK

        query.message.reply_text('Please insert valid OTC ticker')
        if update.callback_query.data == Actions.INFO:
            return Indexers.PRINT_INFO
        elif update.callback_query.data == Actions.ALERTS:
            return Indexers.PRINT_ALERTS
        elif update.callback_query.data == Actions.DILUTION:
            return Indexers.PRINT_DILUTION
        else:
            return ConversationHandler.END

    def free_trial_callback(self, update, context):
        query = update.callback_query
        query.answer()

        self.free_trial(query.message,
                        query.from_user,
                        context)

        return Indexers.DO_FREE_TRIAL

    def free_trial(self, message, from_user, context, weeks=2, source='default'):
        try:
            user = self.mongo_db.telegram_users.find({'chat_id': from_user.id}).limit(1)[0]
        except IndexError:
            user = None

        if not user:
            self.__user_agreemant(message, context,
                                  {'activation': ActivationCodes.TRIAL, 'appendix': {'weeks': weeks, 'source': source}})

        else:
            if user.get('activation') in [ActivationCodes.TRIAL, ActivationCodes.ACTIVE]:
                msg = f'{from_user.name} is already registered!\n' \
                    'Try our tools for some cool stuff!'
                keyboard = Keyboards.TOOLS_KEYBOARD
            elif user.get('activation') in [ActivationCodes.CANCEL, ActivationCodes.DEREGISTER]:
                msg = f'{from_user.name} subscription has ended, please renew your subscription'
                keyboard = Keyboards.SUBSCRIBE_KEYBOARD
            elif user.get('activation') == ActivationCodes.UNREGISTER:
                msg = f'{from_user.name} free trial has ended\n' \
                    f'Please purchase subscription plan'
                keyboard = Keyboards.SUBSCRIBE_KEYBOARD
            elif user.get('activation') == ActivationCodes.PENDING:
                msg = f'{from_user.name} has pending subscription plan\n' \
                    f'Please check your email for activation'
                keyboard = InlineKeyboardMarkup([[Buttons.CONTACT_BUTTON]])
            else:
                self.logger.warning(f"No activation for user: {user}")
                msg = f'An error has occurred, please contact us for further information'
                keyboard = InlineKeyboardMarkup([[Buttons.CONTACT_BUTTON]])

            message.reply_text(msg, parse_mode=telegram.ParseMode.MARKDOWN, reply_markup=keyboard)

    def alerts_command(self, update, context):
        user = update.message.from_user
        ticker = self.__extract_ticker(context)

        if not ticker:
            update.message.reply_text("Couldn't detect ticker, Please try again by the format: /alerts TICKR")

        elif not self._is_registered(user.name, user.id):
            update.message.reply_text('You need to be registered in order to use this. Check /register for more info')

        else:
            self.print_alerts(update.message,
                              update.message.from_user,
                              ticker)

    def alerts_callback(self, update, context):
        ticker = update.message.text.upper()

        self.print_alerts(update.message,
                          update.message.from_user,
                          ticker)

        return Indexers.CONVERSATION_CALLBACK

    def print_alerts(self, message, from_user, ticker):
        try:
            pending_message = message.reply_text("This operation might take some time...")

            self.logger.info(
                "{user_name} of {chat_id} have used /alerts on ticker: {ticker}".format(
                    user_name=from_user.name,
                    chat_id=from_user.id,
                    ticker=ticker
                ))
            diffs = Client.get_diffs(self.mongo_db, ticker).to_dict('records')
            alerter_args = {'mongo_db': self.mongo_db, 'telegram_bot': self.bot_instance,
                            'ticker': ticker, 'debug': self.debug}
            messages = Alert.generate_msg(diffs, alerter_args, as_dict=True)

            msg = Alert.generate_title(ticker, self.mongo_db) + '\n' + \
                  reduce(lambda _, diff: _ + (
                      self.__format_message(messages, diff) if diff.get('_id') in messages else ''),
                         diffs, '')

            if len(msg) > self.MAX_MESSAGE_LENGTH:
                pending_message.delete()
                self.__send_long_message(message.reply_text, msg, parse_mode=telegram.ParseMode.MARKDOWN)
            else:
                pending_message.edit_text(msg, parse_mode=telegram.ParseMode.MARKDOWN)

        except Exception as e:
            self.logger.exception(e, exc_info=True)
            message.reply_text("Couldn't produce alerts for {ticker}".format(ticker=ticker))

        return ConversationHandler.END

    def info_command(self, update, context):
        user = update.message.from_user
        ticker = BaseBot.__extract_ticker(context)

        if not ticker:
            update.message.reply_text("Couldn't detect ticker, Please try again by the format: /info TICKR")

        elif not self._is_registered(user.name, user.id):
            update.message.reply_text('You need to be registered in order to use this. Check /register for more info')

        else:
            self.print_info(update.message,
                            update.message.from_user,
                            ticker)

    def info_callback(self, update, context):
        ticker = update.message.text.upper()

        self.print_info(update.message,
                        update.message.from_user,
                        ticker)

        return Indexers.CONVERSATION_CALLBACK

    def print_info(self, message, from_user, ticker):
        try:
            self.logger.info(
                "{user_name} of {chat_id} have used /info on ticker: {ticker}".format(
                    user_name=from_user.name,
                    chat_id=from_user.id,
                    ticker=ticker
                ))

            # Escaping irrelevant markdown characters
            message.reply_text(Client.info(self.mongo_db, ticker),
                               parse_mode=telegram.ParseMode.MARKDOWN)

        except Exception as e:
            self.logger.exception(e, exc_info=True)
            message.reply_text("Couldn't produce info for {ticker}".format(ticker=ticker))

    def dilution_command(self, update, context):
        user = update.message.from_user
        ticker = self.__extract_ticker(context)

        if not ticker:
            update.message.reply_text("Couldn't detect ticker, Please try again by the format: /dilution TICKR")

        elif not self._is_registered(user.name, user.id):
            update.message.reply_text('You need to be registered in order to use this. Check /register for more info')

        else:
            self.print_dilution(update.message,
                                update.message.from_user,
                                ticker)

    def dilution_callback(self, update, context):
        ticker = update.message.text.upper()

        self.print_dilution(update.message,
                            update.message.from_user,
                            ticker)

        return Indexers.CONVERSATION_CALLBACK

    def print_dilution(self, message, from_user, ticker):
        pending_message = message.reply_text("This operation might take some time...")

        try:
            self.logger.info(
                "{user_name} of {chat_id} have used /dilution on ticker: {ticker}".format(
                    user_name=from_user.name,
                    chat_id=from_user.id,
                    ticker=ticker
                ))

            securities_df = readers.Securities(mongo_db=self.mongo_db, ticker=ticker) \
                .get_sorted_history(filter_rows=True, filter_cols=True).replace('', 0)

            fig = px.line(securities_df, x="date",
                          y=[key for key in readers.Securities.DILUTION_KEYS if key in securities_df.columns],
                          title=ticker)
            self.__send_df(securities_df, ticker, message.reply_document,
                           plotly_fig=fig, reply_markup=telegram.ReplyKeyboardRemove())

        except Exception as e:
            self.logger.exception(e, exc_info=True)
            message.reply_text("Couldn't produce dilution for {ticker}".format(ticker=ticker))

        pending_message.delete()
        return ConversationHandler.END

    def broadcast(self, update, context):
        try:
            update.message.reply_text('Insert broadcast message please')
            return Indexers.BROADCAST_MSG
        except Exception as e:
            update.message.reply_text(
                '{user_name} couldn\'t broadcast, please contact the support team'.format(
                    user_name=update.message.from_user))
            self.logger.exception(e.__traceback__)

    def broadcast_callback(self, update, context):
        self.send_broadcast_msg(update.message, update.message.from_user, keyboard=Keyboards.TOOLS_KEYBOARD)

    def send_broadcast_msg(self, message, from_user, users=None, msg=None, keyboard=None):
        msg = msg if msg else message.text
        users = users if users else self.mongo_db.telegram_users.find()

        if self.__validate_permissions(message, from_user):
            for to_user in users:
                try:
                    if keyboard:
                        self.bot_instance.send_message(
                            chat_id=to_user['chat_id'], text=msg,
                            parse_mode=telegram.ParseMode.MARKDOWN, reply_markup=keyboard)
                    else:
                        self.bot_instance.send_message(chat_id=to_user['chat_id'], text=msg)
                except telegram.error.BadRequest:
                    self.logger.warning(
                        "{user_name} of {chat_id} not found during broadcast message sending.".format(
                            user_name=to_user['user_name'],
                            chat_id=to_user['chat_id']))
            message.reply_text('Your message have been sent to all of the stocker bot users.')

        return ConversationHandler.END

    def vip_user(self, update, context):
        if not self.__is_high_permission_user(update.message.from_user.name, update.message.from_user.id):
            update.message.reply_text('This operation is only supported for high permission users')
            return

        token = secrets.token_urlsafe()

        document = {
            'token': argon2.PasswordHasher().hash(token),
            'date': arrow.utcnow().format(),
            'activation': ActivationCodes.PENDING
        }

        self.mongo_db.telegram_users.insert_one(document)

        update.message.reply_text(
            text=telegram_helpers.create_deep_linked_url(self.bot_instance.username, token))

    def __validate_permissions(self, message, from_user):
        if self.__is_high_permission_user(from_user.name, from_user.id):
            return True
        else:
            message.reply_text('Your user do not have the sufficient permissions to run this command.')
            self.logger.warning(
                "{user_name} of {chat_id} have tried to run an high permission user command".format(
                    user_name=from_user.name,
                    chat_id=from_user.id))
            return False

    def __log_telegram_action(self, user, action, is_success=False, payload='', appendix=''):
        # TODO: Add real logger here
        self.mongo_db.telegram_actions.insert_one({
            'action': action,
            'date': arrow.utcnow().format(),
            'success': is_success,
            'chat_id': user.id,
            'user_name': user.name,
            'payload': payload,
            'appendix': appendix
        })

    def __get_registration_message(self, token_verified, token_occupied, from_user, token):
        # TODO
        if token_verified:
            if not token_occupied:
                self.__log_telegram_action(from_user, Actions.ACTIVATE, is_success=True, payload=token)
                return f'{Messages.CHECK_MARK_EMOJI_UNICODE} {from_user.name} *Verified successfully*.\n\n' \
                    "Please send us your feedbacks and suggestions, *we won't bite*"
            else:
                self.__log_telegram_action(from_user, Actions.ACTIVATE, is_success=True, payload=token,
                                           appendix='already_activated')
                return "This token was already activated, You may buy a new one or:\n" \
                       "Contact https://t.me/EyesOnMarket if you don't know why you're seeing this message"
        else:
            self.__log_telegram_action(from_user, Actions.ACTIVATE, payload=token)
            return 'Fuck off and pay like everybody else'

    def __user_agreemant(self, message, context, args):
        # TODO
        setattr(context._dispatcher, 'activate_args', args)
        keyboard = InlineKeyboardMarkup([
            [telegram.InlineKeyboardButton("Agree", callback_data=Actions.AGREE),
             Buttons.TERMS_BUTTON], [Buttons.BACK_BUTTON]])

        message.reply_text("By clicking on \"Agree\" you agree to Stocker's terms of service, "
                           "which can be viewed by clicking on \"Terms and conditions\"", reply_markup=keyboard)

    def __is_high_permission_user(self, user_name, chat_id):
        return bool(
            self.mongo_db.telegram_users.find_one({'user_name': user_name, 'chat_id': chat_id, 'permissions': 'high'}))

    def _is_registered(self, user_name, chat_id):
        user = self.mongo_db.telegram_users.find_one({'user_name': user_name, 'chat_id': chat_id})

        if user and user.get('activation') in [ActivationCodes.ACTIVE, ActivationCodes.TRIAL]:
            return True
        return False

    def __verify_token(self, token):
        ph = argon2.PasswordHasher()
        token_verified = False
        token_occupied = False

        for user in self.mongo_db.telegram_users.find():
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

    def __create_user(self, user_name, chat_id, activation, delay=True, appendix: dict = None,
                      update_query=None, create=True, delete_other_documents=False):
        """

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
            self.mongo_db.telegram_users.update_one(update_query, {'$set': user_document})
        else:
            self.mongo_db.telegram_users.insert_one(user_document)

        if delete_other_documents:
            for document in [user for user in self.mongo_db.telegram_users.find()
                             if user.get('chat_id') == chat_id and ('token' not in user)]:
                self.mongo_db.telegram_users.delete_one(document)

        msg = self.bot_instance.send_message(chat_id=chat_id, text=Messages.WELCOME_MESSAGE,
                                             parse_mode=telegram.ParseMode.MARKDOWN,
                                             reply_markup=Keyboards.TOOLS_KEYBOARD)
        self.bot_instance.pin_chat_message(chat_id=1151317792, message_id=msg.message_id)

    @staticmethod
    def invalid_collection(update, context):
        update.message.reply_text(
            'Invalid input. Please choose one of this collections: {}'.format(Factory.TICKER_COLLECTIONS.keys()))

        return ConversationHandler.END

    @staticmethod
    def invalid_ticker_format(update, context):
        update.message.reply_text('Invalid input, please insert 3-5 letters OTC registered ticker')

        return Indexers.CONVERSATION_CALLBACK

    @staticmethod
    def __send_df(df, ticker, func, plotly_fig=None, **kwargs):
        image_path = BaseBot.TEMP_IMAGE_FILE_FORMAT.format(name=ticker)

        if plotly_fig:
            plotly_fig.write_image(image_path)
        else:
            # Converting to image because dataframe isn't shown well in telegram_bot
            dfi.export(df, image_path, table_conversion="matplotlib")

        with open(image_path, 'rb') as image:
            func(document=image, **kwargs)

        os.remove(image_path)

    @staticmethod
    def __send_long_message(func, msg, *args, **kwargs):
        for msg in [msg[i: i + BaseBot.MAX_MESSAGE_LENGTH] for i in
                    range(0, len(msg), BaseBot.MAX_MESSAGE_LENGTH)]:
            func(msg, *args, **kwargs)

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
