from copy import deepcopy
from typing import Dict

import arrow
import inflection
from pymongo.database import Database
from abc import ABC, abstractmethod


class CollectorBase(ABC):
    PUBSUB_TOPIC_NAME = 'projects/stocker-300519/topics/diff-updates'
    LATEST_TAG = 'latest_'

    def __init__(self, mongo_db: Database, cache, date=None, debug=False):
        """
        :param mongo_db: mongo db connection
        :param ticker: current ticker
        :param date: date key
        :param debug: is debug?
        """
        self.name = inflection.underscore(self.__class__.__name__)
        self.collection = mongo_db.get_collection(self.name)
        self.collection_latest = mongo_db.get_collection(self.name + self.LATEST_TAG)
        self._raw_data = None
        self._mongo_db = mongo_db
        self._date = date if date else arrow.utcnow()
        self._debug = debug

        self.cache = cache

    @abstractmethod
    def collect(self):
        pass

    def decorate_diff(self, diff, *args, **kwargs) -> dict:
        diff = deepcopy(diff)

        diff.update({
            "date": self._date.format(),
            "source": self.name
        })

        return diff
