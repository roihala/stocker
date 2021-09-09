import base64
from urllib.parse import urlparse, parse_qs

import pandas
import secrets
from operator import itemgetter

import argon2
import os
import arrow
from functools import reduce

import dataframe_image as dfi
import plotly.express as px
import requests
import telegram
import validators
from google.cloud import storage

from telegram.ext import ConversationHandler
from telegram import InlineKeyboardMarkup

from client import Client
from src.collect.records import filings_collector
from src.common.otcm import REQUIRED_HEADERS

from src.read import readers
from alert import Alert
from src.read.reader_base import ReaderBase
from src.telegram_bot.base_bot import BaseBot
from src.telegram_bot.registration_bot import RegistrationBot
from src.telegram_bot.resources.activation_kaki import ActivationCodes
from src.telegram_bot.resources.actions import Actions
from src.telegram_bot.resources.indexers import Indexers
from src.telegram_bot.resources.markup import Keyboards, Buttons
from src.telegram_bot.resources.messages import Messages

from src.collect.tickers import collectors


class FatherBot(BaseBot):
    POOP_EMOJI_UNICODE = u'\U0001F4A9'
    FETCH_FILINGS_BUCKET_NAME = 'stocker_filings_translator'

    def __init__(self, registration_bot: RegistrationBot, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.registration_bot = registration_bot

    PAYMENT_URL = 'https://www.stocker.watch/plans-pricing'
    STOCKER_URL = 'https://www.stocker.watch'
    MARKET_EYES_URL = 'https://t.me/EyesOnMarket'
    TWITTER_URL = 'https://twitter.com/EyesOnMarket'

    FREE_TRIAL_TOKENS = {
        'c92be8609f80cac1aa96bad370acd64761836bd3f62de0cb448690de81c3a865': 'judit',
        'fe69f4558183d6307d988c11a8e0b42839a94fb6de371a1fc9f362f698465f7f': 'special',
        'a80ddd492ea6c9e652864afcf9c8a89509abd446aab12e794b446624a70bd00d': 'reddit',
        'fc4519d98ffaaed1e227d5214e27bf56f969306d7bb60e87f21eaf432d7c9f02': 'kevin',
        '7354be84e72f6fc3048b72320cc663994f1ba542a5a69ddb9964bfea4d884e1d': 'mambo',
        '6bf81fb9d29270a8200cb3cd635295829f12d73af3e3b4db8719904f6a2b0fee': 'otcfree',
        'free_trial': 'website'
    }
    DEREGISTER_TOKEN = 'f16e4d4c8ee076e33d27a0c1a5b1adc7886b324c520f55206f913275bc0c075d'

    SPLIT_BOT_TOKEN = 'babf734369844d1b42da3f23fe5f97bd28b1c606c4e67ac2a5a32e5890378ec4'

    CLOUD_STORAGE_BASE_PATH = 'https://storage.googleapis.com/{bucket}/{blob}'

    TEMP_IMAGE_FILE_FORMAT = '{name}.png'
    MAX_MESSAGE_LENGTH = 4096

    def conversation_callback(self, update, context):
        query = update.callback_query
        query.answer()

        if update.callback_query.data == Actions.FREE_TRIAL:
            self.registration_bot.free_trial(query.message, query.from_user, context)
            return Indexers.CONVERSATION_CALLBACK

        elif update.callback_query.data == Actions.TOOLS:
            self.tools(query.message, query.from_user, edit_text=True)
            return Indexers.CONVERSATION_CALLBACK

        elif update.callback_query.data == Actions.BACK_TO_MENU:

            self.start(query.message, query.from_user, edit_message=True)
            return Indexers.CONVERSATION_CALLBACK

        elif update.callback_query.data == Actions.AGREE:
            if not self.registration_bot.create_user_args:
                return Indexers.CONVERSATION_CALLBACK

            # TODO: create user should update user
            self.registration_bot.create_user(query.from_user.name, query.from_user.id, query.message,
                                              **self.registration_bot.create_user_args)

            self.registration_bot.create_user_args = {}
            return Indexers.CONVERSATION_CALLBACK

        elif update.callback_query.data == Actions.SurveyActions.START_SURVEY:
            self.registration_bot.start_survey(query.message)
            return Indexers.CONVERSATION_CALLBACK

        elif update.callback_query.data in Actions.SurveyActions.get_survey_actions():
            return self.registration_bot.survey_callback(query, update)

        elif update.callback_query.data == Actions.FETCH_FILINGS:
            query.message.reply_text('Please enter valid filing link')
            return Indexers.PRINT_FETCH_FILINGS

        query.message.reply_text('Please insert valid OTC ticker')
        if update.callback_query.data == Actions.INFO:
            return Indexers.PRINT_INFO
        elif update.callback_query.data == Actions.OTCIQ:
            return Indexers.PRINT_OTCIQ

        elif update.callback_query.data == Actions.ALERTS:
            return Indexers.PRINT_ALERTS
        elif update.callback_query.data == Actions.DILUTION:
            return Indexers.PRINT_DILUTION
        else:
            return ConversationHandler.END

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
            arg = update.message.text.split(' ')[1]

            if arg in self.FREE_TRIAL_TOKENS.keys():
                source = self.FREE_TRIAL_TOKENS[arg]
                if source in ['judit', 'special', 'kevin', 'otcfree']:
                    weeks = 4
                else:
                    weeks = 2

                self.registration_bot.free_trial(update.message, update.message.from_user, context,
                                                 weeks=weeks, source=source)
            elif arg == self.DEREGISTER_TOKEN:
                self.registration_bot.deregister(update.message.from_user, update.message)
            elif arg == self.SPLIT_BOT_TOKEN:
                self.mongo_db.telegram_users.update_one({'chat_id': update.message.from_user.id},
                                                        {'$set': {'bot': self.bot_instance.username}})
                update.message.reply_text('Updated bot successfully!')
                self.start(update.message, update.message.from_user)
            else:
                self.registration_bot.activate_token(update, arg, context)
        else:
            self.start(update.message, update.message.from_user)

        return Indexers.CONVERSATION_CALLBACK

    def start(self, message, from_user, edit_message=False):
        start_msg = Messages.START_MESSAGE

        if self._is_high_permission_user(from_user.name, from_user.id):
            start_msg += '\n/broadcast - Send meesages to all users'

        keyboard = InlineKeyboardMarkup([
            [Buttons.FREE_TRIAL, Buttons.TOOLS]])

        if edit_message:
            message.delete()

        message.reply_text(start_msg,
                           parse_mode=telegram.ParseMode.MARKDOWN,
                           reply_markup=keyboard)

    def tools_command(self, update, context):
        self.tools(update.message, update.message.from_user)

        return Indexers.CONVERSATION_CALLBACK

    def tools(self, message, from_user, edit_text=False):
        if not self._is_registered(from_user.name, from_user.id):
            message.reply_text(Messages.UNREGISTERED)
            return ConversationHandler.END

        if edit_text:
            message.delete()
        message.reply_photo('https://static.wixstatic.com/media/7bd982_a90480838b0d431882413fd0414833a9~mv2.png',
                            reply_markup=Keyboards.TOOLS)

    def alerts_command(self, update, context):
        user = update.message.from_user
        ticker = self.__extract_ticker(context)

        if not ticker:
            update.message.reply_text("Couldn't detect ticker, Please try again by the format: /alerts TICKR")

        elif not self._is_registered(user.name, user.id):
            update.message.reply_text(Messages.UNREGISTERED)

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

            alert_body = '\n\n'.join(
                [alerter.get_text(append_dates=True) for alerter in Alert.get_alerters(diffs, alerter_args) if
                 alerter.get_text(append_dates=True)])

            text = Alert.build_text(alert_body, ticker, self.mongo_db, is_alert=False)

            if len(text) > self.MAX_MESSAGE_LENGTH:
                pending_message.delete()
                self.__send_long_message(message.reply_text, text, parse_mode=telegram.ParseMode.MARKDOWN)
            else:
                pending_message.edit_text(text, parse_mode=telegram.ParseMode.MARKDOWN)

            # Joe Cazz
            try:
                if from_user.id == 797932115:
                    self.bot_instance.send_message(406000980,
                                                   text=f'{self.POOP_EMOJI_UNICODE} Ofek gay\n/alerts on {ticker}')
                    self.bot_instance.send_message(1151317792,
                                                   text=f'{self.POOP_EMOJI_UNICODE} Ofek gay\n/alerts on {ticker}')
            except Exception as e:
                self.logger.warning("Couldn't send message to ofek")
                self.logger.exception(e)

        except Exception as e:
            self.logger.exception(e, exc_info=True)
            message.reply_text("Couldn't produce alerts for {ticker}".format(ticker=ticker))

        return ConversationHandler.END

    def info_command(self, update, context):
        user = update.message.from_user
        ticker = FatherBot.__extract_ticker(context)

        if not ticker:
            update.message.reply_text("Couldn't detect ticker, Please try again by the format: /info TICKR")

        elif not self._is_registered(user.name, user.id):
            update.message.reply_text(Messages.UNREGISTERED)

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

            message.reply_text(Client.info(self.mongo_db, ticker),
                               parse_mode=telegram.ParseMode.MARKDOWN)

            # Joe Cazz
            try:
                if from_user.id == 797932115:
                    self.bot_instance.send_message(406000980,
                                                   text=f'{self.POOP_EMOJI_UNICODE} Ofek gay\n/info on {ticker}')
                    self.bot_instance.send_message(1151317792,
                                                   text=f'{self.POOP_EMOJI_UNICODE} Ofek gay\n/info on {ticker}')
            except Exception as e:
                self.logger.warning("Couldn't send message to ofek")
                self.logger.exception(e)

        except Exception as e:
            self.logger.exception(e, exc_info=True)
            message.reply_text("Couldn't produce info for {ticker}".format(ticker=ticker))

    def dilution_command(self, update, context):
        user = update.message.from_user
        ticker = self.__extract_ticker(context)

        if not ticker:
            update.message.reply_text("Couldn't detect ticker, Please try again by the format: /dilution TICKR")

        elif not self._is_registered(user.name, user.id):
            update.message.reply_text(Messages.UNREGISTERED)

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

            relevant_keys = [key for key in readers.Securities.DILUTION_KEYS if key in securities_df.columns]

            if not relevant_keys:
                pending_message.edit_text(f"There was no dilution in {ticker}")
                return

            fig = px.line(securities_df, x="date",
                          y=relevant_keys,
                          title=ticker)
            self.__send_df(securities_df, ticker, message.reply_document,
                           plotly_fig=fig, reply_markup=telegram.ReplyKeyboardRemove())

            # Joe Cazz
            try:
                if from_user.id == 797932115:
                    self.bot_instance.send_message(406000980,
                                                   text=f'{self.POOP_EMOJI_UNICODE} Ofek gay\n/dilution on {ticker}')
                    self.bot_instance.send_message(1151317792,
                                                   text=f'{self.POOP_EMOJI_UNICODE} Ofek gay\n/dilution  on {ticker}')
            except Exception as e:
                self.logger.warning("Couldn't send message to ofek")
                self.logger.exception(e)

        except Exception as e:
            self.logger.exception(e, exc_info=True)
            message.reply_text("Couldn't produce dilution for {ticker}".format(ticker=ticker))

        pending_message.delete()
        return ConversationHandler.END

    def otciq_command(self, update, context):
        user = update.message.from_user
        tickers = FatherBot.__extract_tickers(context)

        if not tickers:
            update.message.reply_text("Couldn't detect ticker, Please try again by the format: /otciq TICKR")

        elif not self._is_registered(user.name, user.id):
            update.message.reply_text(Messages.UNREGISTERED)

        else:
            self.print_otciq(update.message,
                             update.message.from_user,
                             tickers)

    def otciq_callback(self, update, context):
        ticker = update.message.text.upper()

        self.print_otciq(update.message,
                         update.message.from_user,
                         [ticker])

        return Indexers.CONVERSATION_CALLBACK

    def print_otciq(self, message, from_user, tickers):

        for ticker in tickers:
            try:
                self.logger.info(
                    "{user_name} of {chat_id} have used /otciq on ticker: {ticker}".format(
                        user_name=from_user.name,
                        chat_id=from_user.id,
                        ticker=ticker
                    ))

                text = Alert.build_text(readers.Otciq(self.mongo_db, ticker).generate_info(), ticker, self.mongo_db,
                                        is_alert=False)

                message.reply_text(text=text,
                                   parse_mode=telegram.ParseMode.MARKDOWN)

                # Joe Cazz
                try:
                    if from_user.id == 797932115:
                        self.bot_instance.send_message(406000980,
                                                       text=f'{self.POOP_EMOJI_UNICODE} Ofek gay\n/otciq on {ticker}')
                        self.bot_instance.send_message(1151317792,
                                                       text=f'{self.POOP_EMOJI_UNICODE} Ofek gay\n/otciq on {ticker}')
                except Exception as e:
                    self.logger.warning("Couldn't send message to ofek")
                    self.logger.exception(e)

            except Exception as e:
                self.logger.exception(e, exc_info=True)
                message.reply_text("Couldn't produce otciq for {ticker}".format(ticker=ticker))

    def fetch_filings_command(self, update, context):
        if len(context.args) >= 1:
            self.fetch_filings(update.message,
                               update.message.from_user,
                               context.args)
        else:
            update.message.reply_text("Please insert list of valid links separated by whitespace, e.g:\n\n"
                                      "/fetch_filing http://www.otcmarkets.com/financialReportViewer?symbol=MDMN&id=300919")

    def fetch_filings_callback(self, update, context):
        url = update.message.text
        self.fetch_filings(update.message, update.message.from_user, [url])

        return Indexers.CONVERSATION_CALLBACK

    def fetch_filings(self, message, from_user, urls):
        self.logger.info(
            "{user_name} of {chat_id} have used /fetch_filing on urls: {urls}".format(
                user_name=from_user.name,
                chat_id=from_user.id,
                urls=urls
            ))

        urls_mapping = {}
        urls = [url for url in urls if self.__is_filing_url(url)]

        if not urls:
            message.reply_text("Please insert list of valid links separated by whitespace, e.g:\n\n"
                               "/fetch_filing http://www.otcmarkets.com/financialReportViewer?symbol=MDMN&id=300919")

        for url in urls:
            record_id = self.__export_record_id(url)
            if record_id:
                public_url = self.__upload_or_detect(record_id)

                if public_url:
                    urls_mapping[url] = public_url

        if urls_mapping:
            text = "🚨 Fetched filings\n" + '\n'.join(
                [f"🔴 {ReaderBase.escape_markdown(origin)}\n🟢{ReaderBase.escape_markdown(translation)}\n"
                 for origin, translation in urls_mapping.items()])

            message.reply_text(text, parse_mode=telegram.ParseMode.MARKDOWN)
        else:
            message.reply_text("Couldn't fetch filings")

        # Joe Cazz
        try:
            if from_user.id == 797932115:
                self.bot_instance.send_message(406000980,
                                               text=f'{self.POOP_EMOJI_UNICODE} Ofek gay\n/fetch_filings on {urls}')
                self.bot_instance.send_message(1151317792,
                                               text=f'{self.POOP_EMOJI_UNICODE} Ofek gay\n/fetch_filings on {urls}')
        except Exception as e:
            self.logger.warning("Couldn't send message to ofek")
            self.logger.exception(e)

    def __is_filing_url(self, url):
        if validators.url(url) and any(
                [prefix in url for prefix in ['https://backend.otcmarkets.com/otcapi/company/financial-report',
                                              'http://www.otcmarkets.com/financialReportViewer']]):
            return True
        return False

    def __export_record_id(self, url):
        try:
            if 'https://backend.otcmarkets.com/otcapi/company/financial-report' in url:
                parts = urlparse(url).path.split('/')
                return int(parts[parts.index('content') - 1])
            elif 'http://www.otcmarkets.com/financialReportViewer' in url:
                parsed_url = urlparse(url)
                return int(parse_qs(parsed_url.query)['id'][0])

        except Exception as e:
            self.logger.warning(f"Coulnd't export record_id from {url}")
            self.logger.exception(e)

    def __is_filing_exist(self, record_id):
        # TODO
        return True

    def __upload_or_detect(self, record_id):
        storage_client = storage.Client()
        bucket = storage_client.bucket(self.FETCH_FILINGS_BUCKET_NAME)

        base64_record_id = base64.b64encode(str(record_id).encode('ascii')).decode('ascii')

        blobs = storage_client.list_blobs(self.FETCH_FILINGS_BUCKET_NAME)

        # Detect existing
        for blob in blobs:
            if blob.name == base64_record_id:
                return blob.public_url

        filing_path = self.__download_filing(record_id)

        blob = bucket.blob(base64_record_id)
        blob.upload_from_filename(filing_path)

        return filings_collector.FilingsCollector.CLOUD_STORAGE_BASE_PATH.format(
            bucket=self.FETCH_FILINGS_BUCKET_NAME, blob=base64_record_id)

    def __download_filing(self, record_id):
        response = requests.get(
            'https://backend.otcmarkets.com/otcapi/company/financial-report/{id}/content'.format(id=record_id),
            headers=REQUIRED_HEADERS)

        if not response.ok:
            self.logger.warning(f"Couldn't get pdf from {response.request.url}, status code: {response.status_code}")
            return ''

        pdf_path = os.path.join(filings_collector.PDF_DIR, 'telegram', f"{record_id}.pdf")

        # Creating if not exist
        os.makedirs(os.path.dirname(pdf_path), exist_ok=True)

        with open(pdf_path, 'wb') as f:
            f.write(response.content)

        return pdf_path

    def _is_registered(self, user_name, chat_id):
        user = self.mongo_db.telegram_users.find_one({'chat_id': chat_id})

        if user and user.get('activation') in [ActivationCodes.ACTIVE, ActivationCodes.TRIAL]:
            return True
        return False

    @staticmethod
    def invalid_ticker_format(update, context):
        update.message.reply_text('Invalid input, please insert 3-5 letters OTC registered ticker')

        return Indexers.CONVERSATION_CALLBACK

    @staticmethod
    def invalid_url_format(update, context):
        update.message.reply_text('Invalid input, please enter valid filing link')
        return Indexers.CONVERSATION_CALLBACK

    @staticmethod
    def __send_df(df, ticker, func, plotly_fig=None, **kwargs):
        image_path = FatherBot.TEMP_IMAGE_FILE_FORMAT.format(name=ticker)

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
        for msg in [msg[i: i + FatherBot.MAX_MESSAGE_LENGTH] for i in
                    range(0, len(msg), FatherBot.MAX_MESSAGE_LENGTH)]:
            func(msg, *args, **kwargs)

    @staticmethod
    def __format_message(text, date):
        # Add date and blank lines
        return f"{text}\n{ReaderBase.format_stocker_date(date)}"

    @staticmethod
    def __extract_ticker(context):
        if len(context.args) == 1:
            ticker = context.args[0]
            if 4 <= len(ticker) <= 5 and all([char.isalpha() for char in ticker]):
                return ticker.upper()

        return None

    @staticmethod
    def __extract_tickers(context):
        return [FatherBot.__validate_ticker(arg) for arg in context.args]

    @staticmethod
    def __validate_ticker(arg):
        if 4 <= len(arg) <= 5 and all([char.isalpha() for char in arg]):
            return arg.upper()
