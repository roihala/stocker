import json
import logging
import os
import unittest
import urllib

import arrow

from alert import alert_tickers, extract_tickers
from src.alert.ticker_history import TickerHistory
from src.find.site import InvalidTickerExcpetion

TWO_HUNDRED_TICKERS = ['ACLD', 'ADTC', 'AGDY', 'AGRS', 'SPQS', 'MGPC', 'AMLC', 'ARTM', 'AVOT', 'AGTT', 'ANTI', 'MRPI', 'TMEB', 'AMNL', 'GSPI', 'BPMI', 'BISA', 'BONTQ', 'BRER', 'CACH', 'CLCL', 'CBEX', 'CGIPQ', 'CRMK', 'DLPX', 'CIND', 'CBRI', 'CRLI', 'CLSI', 'CGAM', 'CDNO', 'CFCC', 'CYBD', 'OZON', 'SWWI', 'TRUA', 'DBRM', 'DION', 'AMTCQ', 'ENZH', 'FOYJ', 'FRCH', 'EOSI', 'GBEI', 'GFCJ', 'HERC', 'HCLC', 'ARWD', 'HMGN', 'SGLA', 'ESINQ', 'IGNE', 'WGEI', 'DEMO', 'ISTC', 'ILDO', 'EQUI', 'JACO', 'PCGR', 'LPPI', 'LCAR', 'PFND', 'LPTI', 'PMEA', 'MZEIQ', 'MPIN', 'MTRT', 'HNTM', 'NUTTQ', 'DESTQ', 'OPMC', 'PGAI', 'PMDL', 'PSBC', 'PTSC', 'NADA', 'PDNLA', 'PNBC', 'PSWR', 'RGUS', 'KIDBQ', 'SDAD', 'SHWK', 'SEIL', 'LDSI', 'SLSR', 'SGTN', 'STDE', 'TMMI', 'TALC', 'SIMC', 'FUNN', 'TCGN', 'CVST', 'TROG', 'USRC', 'UMCN', 'GNCC', 'UTRX', 'WGNR', 'INOW', 'PRLO', 'HABC', 'NFTI', 'PLNTQ', 'OMRX', 'MEGH', 'GSAC', 'SINX', 'EKWX', 'CZNB', 'WIRX', 'AACS', 'CHAG', 'MVAC', 'ULGX', 'ASNB', 'WAXS', 'MPEG', 'SLUP', 'SHGP', 'GRLF', 'EQTL', 'CNDL', 'MNSF', 'USEI', 'DPLS', 'IRNC', 'ITNF', 'PGUZ', 'BOTX', 'WWRL', 'SUNC', 'SKVY', 'MRPS', 'ADLI', 'GLEC', 'PSCO', 'AVXT', 'PRVU', 'GPTX', 'CLTY', 'EXSO', 'SEYE', 'IDIG', 'SGBI', 'QTXB', 'ENHT', 'BRCOQ', 'HWVI', 'ACCR', 'PHLI', 'FFPM', 'FPPP', 'BZWR', 'MHTX', 'SIII', 'AWSI', 'HUMT', 'TMOL', 'QPRC', 'CTBK', 'PFTI', 'GWIO', 'LFPI', 'APGI', 'CHWE', 'QENC', 'QNXC', 'ADNY', 'NOUV', 'IPLY', 'NLAB', 'IBSS', 'BSYI', 'TLLEQ', 'BLDV', 'IENT', 'BRTE', 'TRBX', 'CXCQ', 'CNVT', 'CYBA', 'KRFG', 'FUTS', 'ITLK', 'AWWC', 'SCTN', 'SYHO', 'GNLKQ', 'SGRZ', 'MCBP', 'ALIF', 'GSFD', 'XNNHQ', 'CHIF', 'ZULU', 'OSIN', 'ASPZ', 'USAM']
CSV_FILE_PATH = r"C:\Users\RoiHa\Downloads\Telegram Desktop\Stock_Screener (2).csv"
TEST_LOGGER_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'test_logs.log')


class TestAlertTime(unittest.TestCase):
    def setUp(self):
        self._start_date = arrow.now()
        logging.basicConfig(filename=TEST_LOGGER_PATH, level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

    def test_regular(self):
        tickers = extract_tickers(CSV_FILE_PATH)[:200]
        alert_tickers(tickers, True)
        logging.info('finished test_regular in: {time}'.format(time=arrow.now() - self._start_date))

    def test_no_pandas(self):
        """
        Those are a performance tests to figure out what is the bottleneck.
        Leaving them here until we find better location.
        """
        alert_tickers(TWO_HUNDRED_TICKERS, True)
        logging.info('finished test_no_pandas in: {time}'.format(time=arrow.now() - self._start_date))

    def test_no_history(self):
        tickers = extract_tickers(CSV_FILE_PATH)[:200]
        for ticker in tickers:
            try:
                print('running on {ticker}'.format(ticker=ticker))
                TickerHistory.BADGES_SITE.get_ticker_url(ticker)

                site = urllib.request.urlopen(TickerHistory.BADGES_SITE.get_ticker_url(ticker))
                response = json.loads(site.read().decode())
                print(response)
            except InvalidTickerExcpetion:
                logging.warning('Suspecting invalid ticker {ticker}'.format(ticker=ticker))

        logging.info('finished test_no_history in: {time}'.format(time=arrow.now() - self._start_date))

    def test_no_history_no_pandas(self):
        for ticker in TWO_HUNDRED_TICKERS:
            try:
                print('running on {ticker}'.format(ticker=ticker))
                TickerHistory.BADGES_SITE.get_ticker_url(ticker)

                site = urllib.request.urlopen(TickerHistory.BADGES_SITE.get_ticker_url(ticker))
                response = json.loads(site.read().decode())
                print(response)
            except InvalidTickerExcpetion:
                logging.warning('Suspecting invalid ticker {ticker}'.format(ticker=ticker))
        logging.info('finished test_no_history_no_pandas in: {time}'.format(time=arrow.now() - self._start_date))



if __name__ == '__main__':
    unittest.main()
