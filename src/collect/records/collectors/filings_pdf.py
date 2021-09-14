import logging

from src.collect.records.dynamic_records_collector import DynamicRecordsCollector

logger = logging.getLogger('CollectRecords')


class FilingsPdf(DynamicRecordsCollector):
    CLOUD_STORAGE_BASE_PATH = 'https://storage.googleapis.com/{bucket}/{blob}'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._mongo__profile = self._mongo_db.get_collection("profile")

    @property
    def filing_base_url(self):
        return 'http://www.otcmarkets.com/financialReportViewer?id={id}'
