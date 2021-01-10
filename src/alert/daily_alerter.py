import arrow
import pandas
import pymongo

from src.alert import alerter_base


class DailyAlerter(alerter_base.AlerterBase):
    def get_alerts(self, latest, current):
        # get alerts also saves the diffs to mongo
        super().get_alerts(latest, current)
        return None

    @classmethod
    def get_saved_alerts(cls, mongo_db):
        diffs = pandas.DataFrame(mongo_db.diffs.find({}, {"_id": False}).sort('date', pymongo.ASCENDING))

        diffs = diffs.loc[diffs['source'] == str(cls.__name__).lower()]

        # Transforming date form for pandas indexing
        diffs['date'] = diffs['date'].apply(lambda x: arrow.get(x).date())
        diffs = diffs.set_index(['date'])

        # Getting all securities diffs since yesterday
        today_diffs = diffs.loc[arrow.utcnow().shift(days=-1, minutes=-15).date(): arrow.utcnow().date()]

        return today_diffs
