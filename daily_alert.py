from runnable import Runnable
from src.alert.daily_alerter import DailyAlerter
from src.factory import Factory
from stocker_alerts_bot import Bot


class Alert(Runnable):
    def run(self):
        pass
        # TODO: scheduler

    def run_daily(self):
        [self.__telegram_alert(alerter) for alerter in Factory.get_alerters() if issubclass(alerter, DailyAlerter)]

    def __telegram_alert(self, alerter):
        alerts_df = alerter.get_saved_alerts(self._mongo_db)

        for user in self._mongo_db.telegram_users.find():
            try:
                name = '{name}_report'.format(name=alerter.__name__.lower())
                Bot.send_df(alerts_df, name, self._telegram_bot.send_document, **{'chat_id': user.get('chat_id')})

            except Exception as e:
                self.logger.exception(e)


if __name__ == '__main__':
    Alert().run()
