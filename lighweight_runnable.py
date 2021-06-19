import argparse
import logging
import os
import pandas
from abc import abstractmethod, ABC

LOG_DIR = os.path.join(os.path.dirname(__file__), 'logs')
DEFAULT_CSV_PATH = os.path.join(os.path.dirname(__file__), os.path.join('csv', 'tickers.csv'))


class LightRunnable(ABC):

    def __init__(self, args=None):
        if os.getenv("ENV") == "production":
            self._debug = os.getenv('DEBUG', 'false').lower() == 'true'
            self._write = False
            self._tickers_list = self.extract_tickers()

            logger = logging.getLogger(self.__class__.__name__)
            handler = logging.StreamHandler()
            logger.setLevel(logging.INFO)
            handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
            logger.addHandler(handler)
            self.logger = logger
            self.disable_apscheduler_logs()

        else:
            self.args = args if args else self.create_parser().parse_args()
            self._debug = self.args.debug
            self._write = self.args.write
            self._tickers_list = self.extract_tickers()
            os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = os.path.join(os.path.dirname(__file__),
                                                                        'credentials/stocker.json')

            if self.args.verbose:
                logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
            else:
                logging.basicConfig(filename=os.path.join(LOG_DIR, self.__class__.__name__), level=logging.INFO,
                                    format='%(asctime)s %(levelname)s %(message)s')

            self.logger = logging.getLogger(self.__class__.__name__)

        self.logger.info('running {cls}'.format(cls=self.__class__))

    @abstractmethod
    def run(self):
        pass

    def create_parser(self):
        parser = argparse.ArgumentParser()
        parser.add_argument('--debug', dest='debug', help='debug_mode', default=False, action='store_true')
        parser.add_argument('--write', dest='write', help='do you want to write? (overrides debug)', default=False,
                            action='store_true')
        parser.add_argument('--verbose', dest='verbose', help='Print logs', default=False, action='store_true')

        return parser

    @staticmethod
    def extract_tickers(csv=None, all_columns=False):
        try:
            if not csv:
                csv = DEFAULT_CSV_PATH

            df = pandas.read_csv(csv)
            df.Symbol = df.Symbol.apply(lambda ticker: ticker.upper())
            if all_columns:
                return df
            else:
                return df.Symbol
        except Exception:
            raise ValueError(
                'Invalid csv file - validate the path and that the tickers are under a column named symbol')

    @staticmethod
    def disable_apscheduler_logs():
        logging.getLogger('apscheduler.executors.default').setLevel(logging.ERROR)
