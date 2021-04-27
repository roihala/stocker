from typing import Dict

import arrow
from pymongo.database import Database
from abc import ABC, abstractmethod


class CollectorBase(ABC):
    PUBSUB_TOPIC_NAME = 'projects/stocker-300519/topics/diff-updates'

    def __init__(self, mongo_db: Database, cache: Dict, date=None, debug=False, write=False):
        """
        :param mongo_db: mongo db connection
        :param ticker: current ticker
        :param date: date key
        :param debug: is debug?
        """
        self.name = self.__class__.__name__.lower()
        self.collection = mongo_db.get_collection(self.name)
        self._raw_data = None
        self._mongo_db = mongo_db
        self._date = date if date else arrow.utcnow()
        self._debug = debug
        self._write = write

        self.cache = cache

    @abstractmethod
    def collect(self):
        pass
