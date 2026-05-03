import unittest

import certifi
from pymongo import MongoClient

from common_runnable import CommonRunnable
from runnable import Runnable


class StockerTest(unittest.TestCase):
    def setUp(self):
        self._mongo_db = MongoClient('mongodb+srv://doadmin:dYUhqv4V9H057681@db-mongodb-nyc3-51884-ccd4f7da.mongo.ondigitalocean.com/admin?retryWrites=true&w=majority?retryWrites=true&w=majority', tlsCAFile=certifi.where()).dev


if __name__ == '__main__':
    unittest.main()
