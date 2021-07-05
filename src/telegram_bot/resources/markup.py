import telegram
from telegram import InlineKeyboardMarkup, ReplyKeyboardMarkup

from src.telegram_bot.resources.actions import Actions


class Buttons(object):
    MARKET_EYES_URL = 'https://t.me/EyesOnMarket'
    PAYMENT_URL = 'https://www.stocker.watch/plans-pricing'
    AGREEMANT_URL = "https://tinyurl.com/stocker-agreemants"

    ALERTS = telegram.InlineKeyboardButton("Alerts", callback_data=Actions.ALERTS)
    DILUTION = telegram.InlineKeyboardButton("Dilution", callback_data=Actions.DILUTION)
    INFO = telegram.InlineKeyboardButton("Info", callback_data=Actions.INFO)
    CONTACT = telegram.InlineKeyboardButton("Contact", url=MARKET_EYES_URL)
    TERMS = telegram.InlineKeyboardButton("Terms and conditions", url=AGREEMANT_URL)
    TOOLS = telegram.InlineKeyboardButton("Tools", callback_data=Actions.TOOLS)
    SUBSCRIBE = telegram.InlineKeyboardButton("Subscribe", url=PAYMENT_URL)
    FREE_TRIAL = telegram.InlineKeyboardButton("Free trial", callback_data=Actions.FREE_TRIAL)
    BACK_TO_START = telegram.InlineKeyboardButton("« Back to start menu", callback_data=Actions.BACK_TO_MENU)

    # Survey buttons
    BACK = telegram.InlineKeyboardButton("« Back", callback_data=Actions.SurveyActions.BACK)
    SKIP = telegram.InlineKeyboardButton("Skip", callback_data=Actions.SurveyActions.SKIP)
    CONTINUE = telegram.InlineKeyboardButton("Continue", callback_data=Actions.SurveyActions.CONTINUE)
    SKIP_SURVEY = telegram.InlineKeyboardButton("Skip", callback_data=Actions.SurveyActions.SKIP_SURVEY)
    LOWER_THAN_5 = telegram.InlineKeyboardButton('Lower than 0.05', callback_data=Actions.SurveyActions.LOWER_THAN_5)
    LOWER_THAN_2 = telegram.InlineKeyboardButton('Lower than 0.02', callback_data=Actions.SurveyActions.LOWER_THAN_2)
    LOWER_THAN_1 = telegram.InlineKeyboardButton('Lower than 0.01', callback_data=Actions.SurveyActions.LOWER_THAN_1)
    LOWER_THAN_CURRENT = telegram.InlineKeyboardButton('Lower than Pink Current',
                                                       callback_data=Actions.SurveyActions.LOWER_THAN_CURRENT)
    LOWER_THAN_QB = telegram.InlineKeyboardButton('Lower than OTCQB', callback_data=Actions.SurveyActions.LOWER_THAN_QB)
    ADD_TO_WATCHLIST = telegram.InlineKeyboardButton('Add to watchlist',
                                                     callback_data=Actions.SurveyActions.ADD_TO_WATCHLIST)
    REMOVE_FROM_WATCHLIST = telegram.InlineKeyboardButton('Remove from watchlist',
                                                          callback_data=Actions.SurveyActions.REMOVE_FROM_WATHCLIST)
    REPLACE_WATCHLIST = telegram.InlineKeyboardButton('Set new watchlist',
                                                      callback_data=Actions.SurveyActions.REPLACE_WATCHLIST)
    OLD_LOCATION = telegram.KeyboardButton(text='Send location', request_location=True)
    OLD_SKIP = telegram.KeyboardButton(text=Actions.SurveyActions.SKIP)
    OLD_BACK = telegram.KeyboardButton(text=Actions.SurveyActions.BACK)

    RESTART_SURVEY = telegram.InlineKeyboardButton('Restart survey', callback_data=Actions.SurveyActions.START_SURVEY)
    SURVEY = telegram.InlineKeyboardButton('Survey', callback_data=Actions.SurveyActions.START_SURVEY)


class Keyboards(object):
    TOOLS = InlineKeyboardMarkup([
        [Buttons.ALERTS,
         Buttons.DILUTION,
         Buttons.INFO],
        [Buttons.BACK_TO_START]
    ])
    START = InlineKeyboardMarkup([[Buttons.FREE_TRIAL, Buttons.TOOLS]])
    SUBSCRIBE = InlineKeyboardMarkup([[Buttons.CONTACT, Buttons.SUBSCRIBE]])
    BACK_TO_TOOLS = InlineKeyboardMarkup([[Buttons.TOOLS]])

    SURVEY_END = InlineKeyboardMarkup([[Buttons.RESTART_SURVEY, Buttons.CONTINUE]])
    LOCATION = ReplyKeyboardMarkup([[Buttons.OLD_LOCATION, Buttons.OLD_BACK, Buttons.OLD_SKIP]])
