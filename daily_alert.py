import arrow
import telegram
from telegram import InlineKeyboardMarkup

from runnable import Runnable
from src.rest import ActivationCodes


class DailyAlert(Runnable):
    PUNCH_EMOJI_UNICODE = u'\U0001F44A'
    REMINDER_MESSAGE = """{punch_emoji} Dear user,
Your free trial {formatted_time}.

Check our website for pricing plans and more info."""

    def run(self):
        self.remind_users()

    def remind_users(self):
        for user in self._mongo_db.telegram_users.find({'activation': ActivationCodes.TRIAL}):
            try:
                if 'trial_date' not in user:
                    self.logger.info(f"Updating {user.get('user_name')} trial date")
                    self._mongo_db.telegram_users.update_one(user, {'$set': {'trial_date': arrow.utcnow().format()}})
                    continue

                # Capping trial date
                trial_date = arrow.get(user['trial_date']) if arrow.get(user['trial_date']) > arrow.get('2021-06-08T13:00:00+00:00') else arrow.get('2021-06-08T13:00:00+00:00')

                current_date = arrow.get(arrow.utcnow().date()).shift(hours=13)
                days = (current_date - trial_date).days

                if days in [14, 12, 7]:

                    if days == 14:
                        self.logger.info(f"{user.get('user_name')} trial ended")
                        self._mongo_db.telegram_users.update_one(user, {'$set': {'activation': ActivationCodes.UNREGISTER}})
                    msg = self.REMINDER_MESSAGE.format(punch_emoji=self.PUNCH_EMOJI_UNICODE,
                                                       formatted_time=self.get_formatted_time(days))

                    self._telegram_bot.send_message(chat_id=user.get('chat_id'), text=msg,
                                                    reply_markup=InlineKeyboardMarkup([[telegram.InlineKeyboardButton("Subscribe", url='https://www.stocker.watch/plans-pricing')]]))
            except Exception as e:
                self.logger.warning(f"Couldn't remind user {user}")
                self.logger.error(e)

    @staticmethod
    def get_formatted_time(days):
        if days == 7:
            return "will expire in less than a week"
        elif days == 12:
            return "will expire in less than two days"
        elif days == 14:
            return 'has expired'
        else:
            return "will expire in less than a week"


if __name__ == '__main__':
    DailyAlert().run()
