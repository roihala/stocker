from typing import List, Dict

from src.collect.records.dynamic_records_collector import DynamicRecordsCollector
from src.collect.records.records_collector import RecordsCollector
from src.find.site import Site


class FilingsPdf(DynamicRecordsCollector):
    @property
    def url(self):
        return 'http://www.otcmarkets.com/financialReportViewer?id={id}'
