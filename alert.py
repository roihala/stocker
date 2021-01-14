from runnable import Runnable
from src.alert.daily_alerter import DailyAlerter
from src.factory import Factory
from stocker_alerts_bot import Bot

from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.schedulers.blocking import BlockingScheduler

from utils import disable_apscheduler_logs


class Alert(Runnable):
    def run(self):
        [self.__telegram_alert(alerter) for alerter in Factory.get_alerters() if issubclass(alerter, DailyAlerter)]

    def run_daily(self):
        scheduler = BlockingScheduler(executors={
            'default': ThreadPoolExecutor(10000)
        }, timezone="US/Eastern")

        disable_apscheduler_logs()

        # Running daily alerter half an hour before the market opens
        scheduler.add_job(self.run, trigger='cron', hour='9', minute='00')
        scheduler.start()

    def __telegram_alert(self, alerter):
        alerts_df = alerter.get_saved_alerts(self._mongo_db)

        for user in self._mongo_db.telegram_users.find():
            try:
                name = '{name}_report'.format(name=alerter.__name__.lower())
                Bot.send_df(alerts_df, name, self._telegram_bot.send_document, **{'chat_id': user.get('chat_id')})

            except Exception as e:
                self.logger.exception(e)


if __name__ == '__main__':
    Alert().run_daily()
