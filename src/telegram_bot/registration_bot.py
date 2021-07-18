from copy import deepcopy

import argon2
import arrow

import telegram
from argon2.exceptions import VerifyMismatchError, VerificationError
from telegram import InlineKeyboardMarkup, ReplyKeyboardRemove, ReplyKeyboardMarkup

from src.telegram_bot.base_bot import BaseBot
from src.telegram_bot.resources.actions import Actions
from src.telegram_bot.resources.messages import Messages
from src.telegram_bot.resources.activation_kaki import ActivationCodes
from src.telegram_bot.resources.indexers import Indexers
from src.telegram_bot.resources.markup import Buttons, Keyboards


class RegistrationBot(BaseBot):
    class SurveySteps:
        INIT = 0
        PRICE = 1
        TIER = 2
        WATCHLIST = 3
        END = 4

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.create_user_args = {}
        self.watchlist_action = None
        self.survey_step = self.SurveySteps.INIT
        self.is_new_user_survey = False

    def create_user(self, user_name, chat_id, message, activation, delay=True, appendix: dict = None,
                    update_query=None, create=True):
        user_document = {
            'user_name': user_name,
            'chat_id': chat_id,
            f'{activation}_date': arrow.utcnow().format(),
            'delay': delay,
            'activation': activation,
            'configuration': self.__default_configuration()
        }

        if appendix:
            user_document.update({'appendix': appendix})

        if not create:
            return user_document

        if activation == ActivationCodes.ACTIVE:
            existing_entry = {}
            for document in self.mongo_db.telegram_users.find({"chat_id": chat_id}):
                if 'token' not in document:
                    existing_entry.update(document)
                    self.mongo_db.telegram_users.delete_one(document)
                    existing_entry.pop('_id')

            existing_entry.update(user_document)
            user_document = existing_entry

        if isinstance(update_query, dict):
            self.mongo_db.telegram_users.update_one(update_query, {'$set': user_document})
        else:
            self.mongo_db.telegram_users.insert_one(user_document)



        self.is_new_user_survey = True
        self.start_survey(message)

    def user_agreemant(self, message, args):
        """

        :param message:
        :param args: self.create_user args, will be stored in self.create_user_args
        :return:
        """
        # Storing create_user args
        self.create_user_args = args

        keyboard = InlineKeyboardMarkup([
            [telegram.InlineKeyboardButton("Agree", callback_data=Actions.AGREE),
             Buttons.TERMS], [Buttons.BACK_TO_START]])

        message.reply_text("By clicking on \"Agree\" you agree to Stocker's terms of service, "
                           "which can be viewed by clicking on \"Terms and conditions\"", reply_markup=keyboard)

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
            self.user_agreemant(message, {'activation': ActivationCodes.TRIAL,
                                          'appendix': {'weeks': weeks, 'source': source}})
            return

        if 'appendix' in user and user['appendix'].get('weeks') < weeks:
            appendix = deepcopy(user['appendix'])
            appendix.update({'weeks': weeks, 'source': source})
            self.mongo_db.telegram_users.update_one(user, {'$set': {'appendix': appendix}})

            msg = f'{from_user.name} updated free trial period to {weeks} weeks\n' \
                'Try our tools for some cool stuff!'
            keyboard = Keyboards.BACK_TO_TOOLS

        elif user.get('activation') in [ActivationCodes.TRIAL, ActivationCodes.ACTIVE]:
            msg = f'{from_user.name} is already registered!\n' \
                'Try our tools for some cool stuff!'
            keyboard = Keyboards.BACK_TO_TOOLS
        elif user.get('activation') in [ActivationCodes.CANCEL, ActivationCodes.DEREGISTER]:
            msg = f'{from_user.name} subscription has ended, please renew your subscription'
            keyboard = Keyboards.SUBSCRIBE
        elif user.get('activation') == ActivationCodes.UNREGISTER:
            msg = f'{from_user.name} free trial has ended\n' \
                f'Please purchase subscription plan'
            keyboard = Keyboards.SUBSCRIBE
        elif user.get('activation') == ActivationCodes.PENDING:
            msg = f'{from_user.name} has pending subscription plan\n' \
                f'Please check your email for activation'
            keyboard = InlineKeyboardMarkup([[Buttons.CONTACT]])
        else:
            self.logger.warning(f"No activation for user: {user}")
            msg = f'An error has occurred, please contact us for further information'
            keyboard = InlineKeyboardMarkup([[Buttons.CONTACT]])

        message.reply_text(msg, parse_mode=telegram.ParseMode.MARKDOWN, reply_markup=keyboard)

    def deregister_command(self, update, context):
        user = update.message.from_user
        self.deregister(user, update.message)

    def deregister(self, user, message):
        try:
            self.mongo_db.telegram_users.update_one({'chat_id': user.id},
                                                    {'$set': {'activation': ActivationCodes.DEREGISTER}})

            self.logger.info(
                "{user_name} of {chat_id} deregistered".format(user_name=user.name, chat_id=user.id))

            message.reply_text('{user_name} Deregistered successfully'.format(user_name=user.name))

        except Exception as e:
            message.reply_text(
                '{user_name} couldn\'t deregister, please contact the support team'.format(user_name=user.name))
            self.logger.exception(e.__traceback__)

    def activate_token(self, update, token, context) -> None:
        from_user = update.message.from_user

        token_verified, token_occupied, user_document = self.__verify_token(token)

        if token_verified and not token_occupied:
            self.user_agreemant(update.message,
                                args={'activation': ActivationCodes.ACTIVE, 'update_query': user_document})

        else:
            msg = self.__activation_failure_message(token_verified, token_occupied, from_user, token)
            update.message.reply_text(msg, parse_mode=telegram.ParseMode.MARKDOWN, reply_markup=Keyboards.SUBSCRIBE)

    def survey_callback(self, query, update):
        if update.callback_query.data == Actions.SurveyActions.SKIP_SURVEY:
            self.__end_survey(query.message, query.from_user.id)

        if update.callback_query.data in Actions.SurveyActions.get_watchlist_actions():
            self.watchlist_action = update.callback_query.data
            query.message.reply_text('Please insert a list of tickers, separated ONLY by *,* (comma), e.g:\n'
                                     'NECA,GGII,MJWL',
                                     parse_mode=telegram.ParseMode.MARKDOWN)
            return Indexers.GET_WATCHLIST

        # Survey actions
        elif update.callback_query.data in Actions.SurveyActions.get_survey_actions(exclude_wathclist=True):
            return self.survey(query.message, query.from_user, update.callback_query.data)

    def survey(self, message, from_user, action, remove_keyboard=False):
        print('survey', action, self.survey_step)

        if remove_keyboard:
            _ = message.reply_text(text='.', parse_mode=telegram.ParseMode.MARKDOWN,
                                   reply_markup=telegram.ReplyKeyboardRemove())
            _.delete()

        self.__update_by_action(action, from_user)

        if action == Actions.SurveyActions.BACK:
            self.survey_step = max(self.SurveySteps.PRICE, self.survey_step - 1)
        else:
            self.survey_step = min(self.SurveySteps.END, self.survey_step + 1)

        if self.survey_step == self.SurveySteps.PRICE:
            msg = 'Please choose price range'
            keyboard = InlineKeyboardMarkup([
                [Buttons.LOWER_THAN_5, Buttons.LOWER_THAN_2, Buttons.LOWER_THAN_1],
                [Buttons.BACK, Buttons.SKIP]
            ])
        elif self.survey_step == self.SurveySteps.TIER:
            msg = 'Please choose tier range'
            keyboard = InlineKeyboardMarkup([
                [Buttons.LOWER_THAN_QB, Buttons.LOWER_THAN_CURRENT],
                [Buttons.BACK, Buttons.SKIP]
            ])
        elif self.survey_step == self.SurveySteps.WATCHLIST:
            msg, keyboard = self.__get_watchlist_message(from_user)
        elif self.survey_step == self.SurveySteps.END:
            self.__end_survey(message, from_user.id, edit_text=True if remove_keyboard else False)
            return
        else:
            raise ValueError("Logic shouldn't get here")

        if remove_keyboard:
            message.reply_text(text=msg, parse_mode=telegram.ParseMode.MARKDOWN, reply_markup=keyboard)
        else:
            try:
                message.edit_text(text=msg, parse_mode=telegram.ParseMode.MARKDOWN, reply_markup=keyboard)
            except telegram.error.BadRequest:
                # Message unchanged
                pass

        return Indexers.CONVERSATION_CALLBACK

    def watchlist_callback(self, update, context):
        new_tickers = [ticker.upper() for ticker in set(update.message.text.split(','))]
        saved_watchlist = self.__get_configuration(update.message.from_user.id).get('watchlist')

        if self.watchlist_action == Actions.SurveyActions.REPLACE_WATCHLIST:
            watchlist = new_tickers
        elif self.watchlist_action == Actions.SurveyActions.ADD_TO_WATCHLIST:
            watchlist = list(set(saved_watchlist) | set(new_tickers))
        elif self.watchlist_action == Actions.SurveyActions.REMOVE_FROM_WATHCLIST:
            watchlist = list(set(saved_watchlist) - set(new_tickers))
        else:
            raise ValueError("Logic shouldn't get here")

        self.__update_configuration(update.message.from_user.id, {'watchlist': watchlist})

        self.watchlist_action = None
        self.survey_step += 1

        update.message.reply_text(f"Your new watchlist is {','.join(watchlist)}\n\n")

        return Indexers.CONVERSATION_CALLBACK

    def invalid_watchlist(self, update, context):
        update.message.reply_text(Messages.INVALID_WATCHLIST)

        return Indexers.GET_WATCHLIST

    def __update_by_action(self, action: Actions.SurveyActions, from_user):
        update = None

        if action in Actions.SurveyActions.get_price_actions():
            if action == Actions.SurveyActions.LOWER_THAN_5:
                update = {'max_price': 0.05}
            elif action == Actions.SurveyActions.LOWER_THAN_2:
                update = {'max_price': 0.02}
            elif action == Actions.SurveyActions.LOWER_THAN_1:
                update = {'max_price': 0.01}
        elif action in Actions.SurveyActions.get_tier_actions():
            if action == Actions.SurveyActions.LOWER_THAN_CURRENT:
                update = {'max_tier': 'PC'}
            if action == Actions.SurveyActions.LOWER_THAN_QB:
                update = {'max_tier': 'QB'}

        if update:
            self.__update_configuration(from_user.id, update)

    def __end_survey(self, message, chat_id, edit_text=True):
        self.survey_step = self.SurveySteps.INIT

        if self.is_new_user_survey:
            try:
                self.bot_instance.unpin_all_chat_messages(chat_id)
            except telegram.error.TimedOut:
                pass
            welcome = self.bot_instance.send_message(chat_id=chat_id, text=Messages.WELCOME_MESSAGE,
                                                     parse_mode=telegram.ParseMode.MARKDOWN,
                                                     reply_markup=Keyboards.BACK_TO_TOOLS)
            self.bot_instance.pin_chat_message(chat_id=chat_id,message_id=welcome.message_id)
            self.is_new_user_survey = False
        else:
            if edit_text:
                message.edit_text(Messages.SURVEY_END, reply_markup=Keyboards.SURVEY_END)
            else:
                message.reply_text(text=Messages.SURVEY_END, parse_mode=telegram.ParseMode.MARKDOWN,
                                   reply_markup=Keyboards.SURVEY_END)

    def __get_watchlist_message(self, from_user):
        try:
            current_wathclist = self.mongo_db.telegram_users.find_one({'chat_id': from_user.id}).get(
                'configuration').get('watchlist')
        except Exception:
            current_wathclist = None

        if current_wathclist:
            msg = f"Your watchlist is:\n{','.join(current_wathclist)}\nWhat would you like to do with it?"
            keyboard = InlineKeyboardMarkup([
                [Buttons.ADD_TO_WATCHLIST, Buttons.REMOVE_FROM_WATCHLIST, Buttons.REPLACE_WATCHLIST],
                [Buttons.BACK, Buttons.SKIP]
            ])
        else:
            msg = 'Press the button to set a watchlist'
            keyboard = InlineKeyboardMarkup([
                [Buttons.REPLACE_WATCHLIST],
                [Buttons.BACK, Buttons.SKIP]
            ])
        return msg, keyboard

    def start_survey(self, message):
        self.survey_step = self.SurveySteps.INIT

        msg = f"Lets take a quick survey to configure your alerts"

        if self.is_new_user_survey:
            keyboard = InlineKeyboardMarkup([[Buttons.CONTINUE, Buttons.SKIP_SURVEY]])
            message.edit_text(text=msg, parse_mode=telegram.ParseMode.MARKDOWN, reply_markup=keyboard)
        else:
            keyboard = InlineKeyboardMarkup([[Buttons.CONTINUE, Buttons.BACK_TO_START]])
            message.delete()
            message.reply_text(text=msg, parse_mode=telegram.ParseMode.MARKDOWN, reply_markup=keyboard)

    def __verify_token(self, token):
        ph = argon2.PasswordHasher()
        token_verified = False
        token_occupied = False

        for user in self.mongo_db.telegram_users.find():
            try:
                if 'token' not in user:
                    continue

                # Comparing hashed token to obtained token
                ph.verify(user['token'], token)

                token_verified = True

                # Verification succeed, checking if this token is occupied
                if 'chat_id' in user:
                    token_occupied = True

                return token_verified, token_occupied, user

            except (VerifyMismatchError, VerificationError):
                pass

        return token_verified, token_occupied, None

    def __activation_failure_message(self, token_verified, token_occupied, from_user, token):
        if token_verified and token_occupied:
            self.logger.info('Token occupied', self._generate_log_json(from_user, Actions.ACTIVATE,
                                                                       is_success=False, payload=token,
                                                                       description='already_activated'))
            return "This token was already activated, You may buy a new one or:\n" \
                   "Contact https://t.me/EyesOnMarket if you don't know why you're seeing this message"
        else:
            self.logger.info('Unexisting token',
                             self._generate_log_json(from_user, Actions.ACTIVATE, is_success=False,
                                                     description='tried to register with token', payload=token))
            return 'Fuck off and pay like everybody else'

    def __get_configuration(self, chat_id):
        return self.mongo_db.telegram_users.find_one({'chat_id': chat_id}).get('configuration')

    def __update_configuration(self, chat_id, update):
        user = self.mongo_db.telegram_users.find_one({'chat_id': chat_id})
        if not user:
            raise ValueError(f"No such user: {chat_id}")

        if 'configuration' not in user:
            user['configuration'] = self.__default_configuration()

        user['configuration'].update(update)
        self.mongo_db.telegram_users.update_one({'chat_id': chat_id}, {'$set': user})

    @staticmethod
    def __default_configuration():
        return {
            'max_price': 0.05,
            'max_tier': 'QB',
            'watchlist': [],
        }

    @staticmethod
    def __extract_tickers(msg):
        return msg.split(' ')
