import argon2
import secrets

import arrow
import telegram
from telegram import InlineKeyboardMarkup
from telegram.ext import ConversationHandler
from telegram.utils import helpers as telegram_helpers


from src.telegram_bot.base_bot import BaseBot
from src.telegram_bot.resources.activation_kaki import ActivationCodes
from src.telegram_bot.resources.indexers import Indexers
from src.telegram_bot.resources.markup import Keyboards


class OwnerBot(BaseBot):
    FIRE_EMOJI_UNICODE = u'\U0001F525'

    def broadcast_command(self, update, context):
        try:
            update.message.reply_text('Insert broadcast message please')
            return Indexers.BROADCAST_MSG
        except Exception as e:
            update.message.reply_text(
                '{user_name} couldn\'t broadcast, please contact the support team'.format(
                    user_name=update.message.from_user))
            self.logger.exception(e.__traceback__)

    def broadcast_callback(self, update, context):
        self.send_broadcast_msg(update.message, update.message.from_user)
        return ConversationHandler.END

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
                except Exception as e:
                    self.logger.warning(
                        "Couldn't send broadcast to {user_name} of {chat_id}".format(
                            user_name=to_user['user_name'],
                            chat_id=to_user['chat_id']))
                    self.logger.exception(e)
            message.reply_text('Your message have been sent to all of the stocker bot users.')

        return ConversationHandler.END

    def vip_user(self, update, context):
        if not self._is_high_permission_user(update.message.from_user.name, update.message.from_user.id):
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

    def launch_tweet(self, update, context):
        update.message.reply_text('Insert tweet link')
        return Indexers.TWEET_MSG

    def tweet_callback(self, update, context):
        msg = f"""Dear users, *I need your help*!
    I uploaded a tweet about this launch and it would really help me if you could retweet :) 

    LETS BURN THE TWITTER! {self.FIRE_EMOJI_UNICODE} {self.FIRE_EMOJI_UNICODE} {self.FIRE_EMOJI_UNICODE}"""

        keyboard = InlineKeyboardMarkup([[telegram.InlineKeyboardButton("Tweet", url=update.message.text)]])

        self.send_broadcast_msg(update.message, update.message.from_user, msg=msg, keyboard=keyboard)
        return ConversationHandler.END

    def __validate_permissions(self, message, from_user):
        if self._is_high_permission_user(from_user.name, from_user.id):
            return True
        else:
            message.reply_text('Your user do not have the sufficient permissions to run this command.')
            self.logger.warning(
                "{user_name} of {chat_id} have tried to run an high permission user command".format(
                    user_name=from_user.name,
                    chat_id=from_user.id))
            return False
