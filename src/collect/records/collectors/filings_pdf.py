from src.collect.records.dynamic_records_collector import DynamicRecordsCollector


class FilingsPdf(DynamicRecordsCollector):
    @property
    def url(self):
        return 'http://www.otcmarkets.com/financialReportViewer?id={id}'
