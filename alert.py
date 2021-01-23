from time import sleep

from pymongo.errors import PyMongoError

from runnable import Runnable
from src.factory import Factory
from stocker_alerts_bot import Bot


class Alert(Runnable):
    def run(self):
        if self._debug:
            self.listen()
            return

        # TODO: scheduler
        pass

    def listen(self):
        while True:
            try:
                with self._mongo_db.diffs.watch() as stream:
                    for event in stream:
                        self.logger.info('event: {event}'.format(event=event))
                        try:
                            diff = event.get('fullDocument')

                            if event['operationType'] != 'insert' or diff.get('source') in self.get_daily_alerters():
                                continue

                            object_id = diff.pop('_id')

                            alerter_args = {'mongo_db': self._mongo_db, 'telegram_bot': self._telegram_bot,
                                            'debug': self._debug}
                            alerter = Factory.alerters_factory(diff.get('source'), **alerter_args)

                            if alerter.alert(diff):
                                self._mongo_db.diffs.update_one({'_id': object_id}, {'$set': {"alerted": True}})

                        except Exception as e:
                            self.logger.warning("Couldn't alert {event}".format(event=event))
                            self.logger.exception(e)

            except PyMongoError as e:
                # We know it's unrecoverable:
                self.logger.exception(e)

            sleep(5000)

    def __telegram_alert(self, alerter):
        alerts_df = alerter.get_saved_alerts(self._mongo_db)

        for user in self._mongo_db.telegram_users.find():
            try:
                name = '{name}_report'.format(name=alerter.__name__.lower())
                Bot.send_df(alerts_df, name, self._telegram_bot.send_document, **{'chat_id': user.get('chat_id')})

            except Exception as e:
                self.logger.exception(e)

    @staticmethod
    def get_daily_alerters():
        return ['securities']


if __name__ == '__main__':
    Alert().run()
