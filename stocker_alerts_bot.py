#!/usr/bin/env python
# -*- coding: utf-8 -*-
import argparse
import logging
import os

import dataframe_image as dfi
import telegram
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, ConversationHandler

from alert import Alert
from src.alert.ticker_history import TickerHistory
from src.find.site import InvalidTickerExcpetion

PRINT_HISTORY, GENDER, LOCATION, BIO = range(4)

LOGGER_PATH = os.path.join(os.path.dirname(__file__), 'stocker_alerts_bot.log')
HISTORY_IMAGE_PATH_FORMAT = os.path.join(os.path.dirname(__file__), '{ticker}.png')


def start(update, context):
    update.message.reply_text(
        '''   
Stocker alerts bot currently supports the following commands:
        
/history - Get the saved history of a certain stock, note that duplications will be removed
/register - Register to get alerts on modifications straight to your telegram account''',
        parse_mode=telegram.ParseMode.MARKDOWN)


def register(update, context):
    user = update.message.from_user

    try:
        # Using private attr because of bad API

        # replace_one will create one if no results found in filter
        replace_filter = {'user_name': user.name}
        context._dispatcher.mongo_db.telegram_users.replace_one(replace_filter,
                                                                {'user_name': user.name, 'chat_id': user.id},
                                                                upsert=True)

        logging.info("{user_name} of {chat_id} registered".format(user_name=user.name, chat_id=user.id))

        update.message.reply_text('{user_name} Registered successfully'.format(user_name=user.name))

    except Exception as e:
        update.message.reply_text(
            '{user_name} couldn\'t register, please contact the support team'.format(user_name=user.name))
        logging.exception(e.__traceback__)


def history(update, context):
    user = update.message.from_user

    if __is_registered(context._dispatcher.mongo_db, user.name, user.id):
        update.message.reply_text('Insert ticker')
        return PRINT_HISTORY
    else:
        update.message.reply_text('You need to be registered to use this. Check /register for more info')
        return ConversationHandler.END


def invalid_input(update, context):
    update.message.reply_text('Invalid input, please insert 3-5 letters OTC registered ticker')

    return ConversationHandler.END


def history_request(update, context):
    ticker = update.message.text.upper()

    try:
        history_df = get_history(context._dispatcher.mongo_db, ticker)
    except InvalidTickerExcpetion:
        update.message.reply_text('No history for {ticker}'.format(ticker=ticker))
        return ConversationHandler.END

    history_image_path = HISTORY_IMAGE_PATH_FORMAT.format(ticker=ticker)

    # Converting to image because dataframe isn't shown well in telegram
    dfi.export(history_df, history_image_path)

    with open(history_image_path, 'rb') as image:
        update.message.reply_document(image)

    os.remove(history_image_path)

    return ConversationHandler.END


def get_history(mongo_db, ticker):
    history_df = TickerHistory(ticker, mongo_db).get_sorted_history(duplicates=False)

    if history_df.empty:
        raise InvalidTickerExcpetion("No history for {ticker}".format(ticker=ticker))

    # Prettify timestamps
    history_df["date"] = history_df["date"].apply(TickerHistory.timestamp_to_datestring)
    history_df["verifiedDate"] = history_df["verifiedDate"].dropna().apply(
        TickerHistory.timestamp_to_datestring)

    return history_filters(history_df)


def history_filters(history_df):
    # Filtering columns that doesn't have even one truth value
    any_columns = history_df.any()
    return history_df[any_columns[any_columns].index]


def __is_registered(mongo_db, user_name, chat_id):
    return bool(mongo_db.telegram_users.find_one({'user_name': user_name, 'chat_id': chat_id}))


def main(args):
    # logging.basicConfig(filename=LOGGER_PATH, level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

    updater = Updater(args.token, use_context=True)

    dp = updater.dispatcher

    # Bad APIs make bad workarounds
    setattr(dp, 'mongo_db', Alert.init_mongo(args.uri))

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('history', history)],
        states={
            PRINT_HISTORY: [MessageHandler(Filters.regex('^[a-zA-Z]{3,5}$'), history_request),
                            MessageHandler(~Filters.regex('^[a-zA-Z]{3,5}$'), invalid_input)]
        },
        fallbacks=[],
    )

    dp.add_handler(conv_handler)

    dp.add_handler(CommandHandler('register', register))
    dp.add_handler(CommandHandler('start', start))

    # Start the Bot
    updater.start_polling()

    # Run the bot until you press Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT. This should be used most of the time, since
    # start_polling() is non-blocking and will stop the bot gracefully.
    updater.idle()


def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--history', dest='history', help='Print the saved history of a ticker')
    parser.add_argument('--uri', dest='uri', help='MongoDB URI of the format mongodb://...', required=True)
    parser.add_argument('--token', dest='token', help='Telegram bot token', required=True)
    return parser.parse_args()


if __name__ == '__main__':
    main(get_args())
