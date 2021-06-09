import telegram
from telegram import InlineKeyboardMarkup

from src.telegram_bot.resources.markup import Buttons
from src.telegram_bot.resources.messages import Messages
from src.telegram_bot.base_bot import BaseBot
from src.telegram_bot.resources.activation_kaki import ActivationCodes
from src.telegram_bot.resources.indexers import Indexers


class Tools(BaseBot):
    FIRE_EMOJI_UNICODE = u'\U0001F525'

    @classmethod
    def launch_tweet(self, update, context):
        update.message.reply_text('Insert tweet link')
        return Indexers.TWEET_MSG

    def tweet_callback(self, update, context):
        msg = f"""Dear users, *I need your help*!
    I uploaded a tweet about this launch and it would really help me if you could retweet :) 

    LETS BURN THE TWITTER! {self.FIRE_EMOJI_UNICODE} {self.FIRE_EMOJI_UNICODE} {self.FIRE_EMOJI_UNICODE}"""

        keyboard = InlineKeyboardMarkup([[telegram.InlineKeyboardButton("Tweet", url=update.message.text)]])

        self.send_broadcast_msg(update.message, update.message.from_user, msg=msg, keyboard=keyboard)

    def launch_command(self, update, context):
        if self.__validate_permissions(update.message, update.message.from_user):
            keyboard = InlineKeyboardMarkup(
                [[Buttons.FREE_TRIAL_BUTTON, telegram.InlineKeyboardButton("Stocker website", url=self.STOCKER_URL)]])

            self.send_broadcast_msg(update.message, update.message.from_user, msg=Messages.LAUNCH_MESSAGE,
                                    keyboard=keyboard)
            self.__purge_telegram_users(context)

        return Indexers.CONVERSATION_CALLBACK

    @classmethod
    def reminder(self, update, context):
        mongo_db = context._dispatcher.mongo_db
        fallen_users = [user for user in mongo_db.vip_users if not self._is_registered(user_name=user.get('user_name'),
                                                                                       chat_id=user.get('chat_id'))]
        print('debug')
        print(len(fallen_users))

        self.send_broadcast_msg(update.message, update.message.from_user)

    @classmethod
    def __purge_telegram_users(self, context):
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

            document = self.__create_user(context, user.get('user_name'), user.get('chat_id'),
                                          delay=delay, activation=ActivationCodes.ACTIVE, create=False)
            # hala
            if user.get('chat_id') == 1151317792:
                document.update({'permissions': 'high'})

            vip_users.append(document)

        # Removing all users
        mongo_db.telegram_users.remove()
        mongo_db.telegram_users.insert_many(vip_users)
