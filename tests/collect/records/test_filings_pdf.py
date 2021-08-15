import unittest

import requests

from tests.stocker_test import StockerTest


class TestFilingsPdf(StockerTest):
    FILINGS_BACKEND = 'https://backend.otcmarkets.com/otcapi/company/financial-report/?pageSize=50&page={page_number}&sortOn=releaseDate'

    def setUp(self):
        super().setUp()
        # latest_mongo_record = self._mongo_db.filings_pdf.find().sort('record_id', -1).limit(1)
        backend_records = self.__get_backend_records(1000)
        mongo_records = list(self._mongo_db.filings_pdf.find().sort('record_id', -1).limit(1000))
        self.zipped_records = [(backend_record, mongo_record) for backend_record in backend_records for mongo_record in mongo_records if backend_record['id'] == mongo_record['record_id']]

        if len(self.zipped_records) < 100:
            raise ValueError("Please update mongo records in dev collection")

    def __get_backend_records(self, records_count):
        records = []

        for i in range(1, int(records_count / 50) + 1):
            try:
                records += requests.get(self.FILINGS_BACKEND.format(page_number=i)).json().get('records')
            except Exception:
                print(f'Failed to get backend records page: {i}')

        return records

    def test_guessed_ticker(self):
        errors = [(mongo_record['record_id'], backend_record['symbol'], mongo_record['ticker']) for backend_record, mongo_record in self.zipped_records if backend_record['symbol'] != mongo_record['ticker']]
        # If there is 'ticker' in mongo_record (it's not empty)
        falses = {error for error in errors if error[2]}

        success_rate = (1 - len(errors) / len(self.zipped_records)) * 100
        self.assertFalse(bool(falses), msg=f'Found false positives: {falses}')

        print(f'guessed ticker test passed with {success_rate}% success rate on {len(self.zipped_records)} entries')


if __name__ == '__main__':
    unittest.main()
