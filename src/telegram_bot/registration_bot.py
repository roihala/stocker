import argon2

import telegram
from argon2.exceptions import VerifyMismatchError, VerificationError
from telegram import InlineKeyboardMarkup

from src.telegram_bot.base_bot import BaseBot
from src.telegram_bot.resources.actions import Actions
from src.telegram_bot.resources.messages import Messages
from src.telegram_bot.resources.activation_kaki import ActivationCodes
from src.telegram_bot.resources.indexers import Indexers
from src.telegram_bot.resources.markup import Buttons, Keyboards


class RegistrationBot(BaseBot):
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

    def deregister_command(self, update, context):
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

    def __user_agreemant(self, message, context, args):
        # TODO
        setattr(context._dispatcher, 'activate_args', args)
        keyboard = InlineKeyboardMarkup([
            [telegram.InlineKeyboardButton("Agree", callback_data=Actions.AGREE),
             Buttons.TERMS_BUTTON], [Buttons.BACK_BUTTON]])

        message.reply_text("By clicking on \"Agree\" you agree to Stocker's terms of service, "
                           "which can be viewed by clicking on \"Terms and conditions\"", reply_markup=keyboard)

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

    def __get_registration_message(self, token_verified, token_occupied, from_user, token):
        # TODO
        if token_verified:
            if not token_occupied:
                self.logger.info('User activated successfully',
                                 self._generate_log_json(from_user, Actions.ACTIVATE, is_success=True))
                return f'{Messages.CHECK_MARK_EMOJI_UNICODE} {from_user.name} *Verified successfully*.\n\n' \
                    "Please send us your feedbacks and suggestions, *we won't bite*"
            else:
                self.logger.info('User activated successfully', self._generate_log_json(from_user, Actions.ACTIVATE,
                                                                                        is_success=False, payload=token,
                                                                                        description='already_activated'))
                return "This token was already activated, You may buy a new one or:\n" \
                       "Contact https://t.me/EyesOnMarket if you don't know why you're seeing this message"
        else:
            self.logger.info('User activated successfully',
                             self._generate_log_json(from_user, Actions.ACTIVATE, is_success=False,
                                                     description='tried to register with token', payload=token))
            return 'Fuck off and pay like everybody else'
