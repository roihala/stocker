import unittest

import certifi
from pymongo import MongoClient

from common_runnable import CommonRunnable
from runnable import Runnable


class StockerTest(unittest.TestCase):
    def setUp(self):
        self._mongo_db = MongoClient('mongodb+srv://stocker:halamish123@cluster2.3nsz4.mongodb.net/stocker?retryWrites=true&w=majority', tlsCAFile=certifi.where()).dev


if __name__ == '__main__':
    unittest.main()
