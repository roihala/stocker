import telegram
from telegram import InlineKeyboardMarkup

from src.telegram_bot.resources.actions import Actions


class Buttons(object):
    MARKET_EYES_URL = 'https://t.me/EyesOnMarket'
    PAYMENT_URL = 'https://www.stocker.watch/plans-pricing'
    AGREEMANT_URL = "http://tinyurl.com/agreemant"

    CONTACT_BUTTON = telegram.InlineKeyboardButton("Contact", url=MARKET_EYES_URL)
    TERMS_BUTTON = telegram.InlineKeyboardButton("Terms and conditions", url=AGREEMANT_URL)
    TOOLS_BUTTON = telegram.InlineKeyboardButton("Tools", callback_data=Actions.TOOLS)
    SUBSCRIBE_BUTTON = telegram.InlineKeyboardButton("Subscribe", url=PAYMENT_URL)
    FREE_TRIAL_BUTTON = telegram.InlineKeyboardButton("Free trial", callback_data=Actions.FREE_TRIAL)
    BACK_BUTTON = telegram.InlineKeyboardButton("« Back to start menu", callback_data=Actions.BACK)


class Keyboards(object):
    START_KEYBOARD = InlineKeyboardMarkup([[Buttons.FREE_TRIAL_BUTTON, Buttons.TOOLS_BUTTON]])
    SUBSCRIBE_KEYBOARD = InlineKeyboardMarkup([[Buttons.CONTACT_BUTTON, Buttons.SUBSCRIBE_BUTTON]])
    TOOLS_KEYBOARD = InlineKeyboardMarkup([[Buttons.TOOLS_BUTTON]])
