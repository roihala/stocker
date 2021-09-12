import random

import argon2
import secrets

import arrow
import telegram
from telegram import InlineKeyboardMarkup
from telegram.ext import ConversationHandler
from telegram.utils import helpers as telegram_helpers

from src.telegram_bot.base_bot import BaseBot
from src.telegram_bot.father_bot import FatherBot
from src.telegram_bot.resources.activation_kaki import ActivationCodes
from src.telegram_bot.resources.indexers import Indexers


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

    def send_broadcast_msg(self, message, from_user, msg=None, keyboard=None):
        msg = msg if msg else message.text
        if self.__validate_permissions(message, from_user):
            for to_user in self.mongo_db.telegram_users.find(
                    {'activation': {"$in": [ActivationCodes.TRIAL, ActivationCodes.ACTIVE]}}):
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
                            user_name=to_user.get('user_name'),
                            chat_id=to_user.get('chat_id')))
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

    def add_bot(self, update, context):
        if not self._is_high_permission_user(update.message.from_user.name, update.message.from_user.id):
            update.message.reply_text('This operation is only supported for high permission users')
            return
        try:
            if len(context.args) != 2:
                raise ValueError

            bot_name, token = context.args[0], context.args[1]
            link = telegram_helpers.create_deep_linked_url(bot_name)

            dcoument = {
                'name': bot_name,
                'token': token,
                'link': link
            }

            self.mongo_db.bots.insert_one(dcoument)

            update.message.reply_text(f"Created a new bot with these values:\n {dcoument}")

        except Exception as e:
            update.message.reply_text(f"Could't add bot with {context.args}")

    def split_bot(self, update, context):
        if not self._is_high_permission_user(update.message.from_user.name, update.message.from_user.id):
            update.message.reply_text('This operation is only supported for high permission users')
            return

        bots = [bot['name'] for bot in self.mongo_db.bots.find()]
        users = [_ for _ in self.mongo_db.telegram_users.find(
            {'activation': {"$in": [ActivationCodes.TRIAL, ActivationCodes.ACTIVE]}})]

        random.shuffle(users)

        for index, user in enumerate(users):
            try:
                # Main by default
                self.mongo_db.users.update_one({'chat_id': user['chat_id']}, {'$set': {'bot': 'stocker_alerts_bot'}})
                bot = bots[(index + 1) % 10]
                link = telegram_helpers.create_deep_linked_url(bot, FatherBot.SPLIT_BOT_TOKEN)

                text = f"""Here's a fixed link: {link}"""

                self.bot_instance.send_message(
                    chat_id=user['chat_id'], text=text)
            except Exception as e:
                self.logger.warning(f"Couldn't split for {user}")
                self.logger.exception(e)

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

    def is_exist(self, update, context):
        if len(context.args) != 1:
            update.message.reply_text('Please insert email address, e.g: /is_exist someone@gmail.com')
        else:
            users = [_ for _ in self.mongo_db.telegram_users.find({"email": {"$regex": f".*{context.args[0]}.*"}})]
            if users:
                update.message.reply_text(f'Detected users:\n```{users}```', parse_mode=telegram.ParseMode.MARKDOWN)
            else:
                update.message.reply_text(f"Couldn't find user by mail address: {context.args[0]}")

    def refresh_link(self, update, context):
        users = [_ for _ in self.mongo_db.telegram_users.find({"email": {"$regex": f".*{context.args[0]}.*"}})]
        if len(users) == 1:
            user = users[0]

            ph = argon2.PasswordHasher()
            token = secrets.token_urlsafe()

            link = telegram_helpers.create_deep_linked_url(user.get('bot', 'stocker_alerts_bot'), token)
            self.mongo_db.telegram_users.update_one({'chat_id': user.get('chat_id')},
                                                    {'$unset': {'user_name': 1, 'chat_id': 1},
                                                     '$set': {'token': ph.hash(token)}})

            update.message.reply_text(f"Here's a new activation link: {link}")
        else:
            update.message.reply_text(f"Please be more specific, detected: ```{users}```",
                                      parse_mode=telegram.ParseMode.MARKDOWN)

    def reactivate(self, update, context):
        if len(context.args) != 2:
            update.message.reply_text('Please insert valid email and date, e.g: /reactivate yanivlang@gmail.com 2021-12-22')

        try:
            activate_until = arrow.get(context.args[1])
        except (arrow.ParserError, ValueError):
            update.message.reply_text(f"Couldn't parse date: {context.args[1]}")
            return

        users = [_ for _ in self.mongo_db.telegram_users.find({"email": {"$regex": f".*{context.args[0]}.*"}})]

        if len(users) == 1:
            user = users[0]
            self.mongo_db.telegram_users.update_one({'email': user.get('email')},
                                                    {'$set': {'activation': ActivationCodes.ACTIVE,
                                                              'activate_until': activate_until.format()}})
            update.message.reply_text(f"Reactivated {context.args[0]} until {activate_until.format()}")
        else:
            update.message.reply_text(f"Please be more specific, detected: ```{users}```",
                                      parse_mode=telegram.ParseMode.MARKDOWN)

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
