from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.schedulers.blocking import BlockingScheduler

from runnable import Runnable
from scheduler_utils import disable_apscheduler_logs
from src.alert.daily_alerter import DailyAlerter
from src.factory import Factory
from stocker_alerts_bot import Bot


class Alert(Runnable):
    def run(self):
        scheduler = BlockingScheduler(executors={
            'default': ThreadPoolExecutor(10000)
        }, timezone="US/Eastern")

        disable_apscheduler_logs()

        # Running daily alerter half an hour before the market opens
        scheduler.add_job(self.run_daily, trigger='cron', hour='9', minute='00')
        scheduler.start()

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
