import arrow
import telegram
from telegram import InlineKeyboardMarkup

from common_runnable import CommonRunnable


class DailyAlert(CommonRunnable):
    PUNCH_EMOJI_UNICODE = u'\U0001F44A'
    REMINDER_MESSAGE = """{punch_emoji} Dear user,
Your free trial {formatted_time}.


Check our website for pricing plans and more info."""
    MARKET_EYES_URL = 'https://t.me/EyesOnMarket'
    PAYMENT_URL = 'https://www.stocker.watch/plans-pricing'
    SUBSCRIBE_KEYBOARD = InlineKeyboardMarkup([[telegram.InlineKeyboardButton("Contact", url=MARKET_EYES_URL),
                                                telegram.InlineKeyboardButton("Subscribe", url=PAYMENT_URL)]])

    def run(self):
        self.remind_users()

    def remind_users(self):
        # for user in self._mongo_db.telegram_users.find({'activation': 'trial'}):
        #     try:
        #         if 'trial_date' not in user:
        #             self.logger.info(f"Updating {user.get('user_name')} trial date")
        #             self._mongo_db.telegram_users.update_one(user, {'$set': {'trial_date': arrow.utcnow().format()}})
        #             continue
        #
        #         # Capping trial date
        #         trial_date = arrow.get(user['trial_date']) if arrow.get(user['trial_date']) > arrow.get(
        #             '2021-06-08T13:00:00+00:00') else arrow.get('2021-06-08T13:00:00+00:00')
        #         current_date = arrow.utcnow().floor('hours')
        #
        #         try:
        #             trial_period = user['appendix']['weeks'] * 7
        #         except KeyError:
        #             trial_period = 14
        #
        #         remain = trial_period - (current_date - trial_date).days
        #
        #         if remain in [0, 2, 7] or remain < 0:
        #             if remain <= 0:
        #                 self.logger.info(f"{user.get('user_name')} trial ended")
        #                 self._mongo_db.telegram_users.update_one(user, {'$set': {'activation': 'unregister'}})
        #             msg = self.REMINDER_MESSAGE.format(punch_emoji=self.PUNCH_EMOJI_UNICODE,
        #                                                formatted_time=self.get_formatted_time(remain))
        #
        #             self._telegram_bot.send_message(chat_id=user.get('chat_id'), text=msg,
        #                                             reply_markup=self.SUBSCRIBE_KEYBOARD)
        #     except Exception as e:
        #         self.logger.warning(f"Couldn't remind user {user}")
        #         self.logger.error(e)

        for user in self._mongo_db.telegram_users.find({'cancel_at': {'$exists': True}}):
            try:
                if arrow.get(user.get('cancel_at')).date() >= arrow.utcnow().date():
                    self.logger.info(f"Canceling {user.get('user_name')}")
                    self._mongo_db.telegram_users.update_one(user, {'$set': {'activation': 'cancel'}})
            except Exception as e:
                self.logger.warning(f"Couldn't cancel user {user}")
                self.logger.error(e)

    @staticmethod
    def get_formatted_time(remain):
        if remain == 7:
            return "will expire in less than a week."
        elif remain == 2:
            return "will expire in less than two days."
        elif remain <= 0:
            return 'has expired.\nWe had great time together, hope to see you soon!'
        else:
            return "will expire in less than a week"


if __name__ == '__main__':
    DailyAlert().run()
