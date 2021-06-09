import logging
import os
import re

import pymongo
import pandas

from alert import Alert
from runnable import Runnable
from src.factory import Factory
from src.find.site import Site
from src.read import readers
from src.read.reader_base import ReaderBase
from src.read.readers import Profile, Symbols, Securities

LOW_FLOATERS_001_1B_PATH = os.path.join(os.path.dirname(__file__), 'low_floaters001_1B.csv')
LOW_FLOATERS_001_500M_PATH = os.path.join(os.path.dirname(__file__), 'low_floaters001_500M.csv')
LOW_FLOATERS_003_250M_PATH = os.path.join(os.path.dirname(__file__), 'low_floaters003_250M.csv')
TICKERS_0006_3B_CURRENT_PATH = os.path.join(os.path.dirname(__file__), 'tickers_0006_3B_current.csv')
EV_TICKERS_PATH = os.path.join(os.path.dirname(__file__), 'ev_tickers.csv')
FLORIDA_TICKERS_PATH = os.path.join(os.path.dirname(__file__), 'florida_tickers.csv')


class Client(Runnable):
    LINK_EMOJI_UNICODE = u'\U0001F517'

    def __init__(self):
        super().__init__()
        pandas.set_option('display.expand_frame_repr', False)

    def run(self):
        if self.args.history:
            print(self.get_history(self._mongo_db, self.args.history).to_string())
        elif self.args.low_floaters:
            self.get_low_floaters(self._mongo_db, self.extract_tickers(self.args.csv))
            print('low floaters lists are ready')
        elif self.args.filter_past:
            self.filter_past()
        elif self.args.clear_diffs:
            self.clear_diffs()
        elif self.args.info:
            print(self.info(self._mongo_db, self.args.info))

    def create_parser(self):
        parser = super().create_parser()

        parser.add_argument('--history', dest='history', help='Print the saved history of a ticker')
        parser.add_argument('--low_floaters', dest='low_floaters', help='Get a list of light low float stocks',
                            default=False, action='store_true')
        parser.add_argument('--filter_past', dest='filter_past', help='Filter duplicate rows from mongo',
                            default=False, action='store_true')
        parser.add_argument('--clear_diffs', dest='clear_diffs', help='Clear diffs collection from alerted: true',
                            default=False, action='store_true')
        parser.add_argument('--info', dest='info', help='')
        return parser

    @staticmethod
    def info(mongo_db, ticker, escape_markdown=True):
        profile = Profile(mongo_db, ticker)
        latest_profile = profile.get_latest()

        sites = [Site("otcmarkets", '"https://www.otcmarkets.com/stock/{ticker}/profile"', is_otc=True),
                 Site("twitter", '"https://twitter.com/search?q=%24{ticker}&src=typed_query"', is_otc=True)]

        sites.append(latest_profile.get('website')) if latest_profile.get('website') else None

        links = '\n'.join(
            [f'{Client.LINK_EMOJI_UNICODE} ' + site.get_ticker_url(ticker, strip=True) if isinstance(site, Site) else site for site in sites])
        links = ReaderBase.escape_markdown(links) if escape_markdown else links

        return """{title}
{subtitle}

*Symbols*
{symbols}

*Company Profile*
{profile}

*Links*
{links}

*Security details*
{securities}
""".format(
            title=Alert.generate_title(ticker, mongo_db),
            subtitle=profile.get_latest().get('name'),
            symbols=Symbols(mongo_db, ticker).generate_msg(),
            profile=profile.generate_msg(['website', 'businessDesc'], escape_markdown) + f'\n_{latest_profile.get("businessDesc")}_',
            securities=Securities(mongo_db, ticker).generate_msg(),
            links=links)

    def filter_past(self):
        for ticker in self._tickers_list:
            self.logger.info('filtering {ticker}'.format(ticker=ticker))
            for collection_name in Factory.TICKER_COLLECTIONS.keys():
                try:
                    reader = Factory.readers_factory(collection_name, **{'mongo_db': self._mongo_db, 'ticker': ticker})
                    collection = self._mongo_db.get_collection(collection_name)

                    # get_sorted_history flattens nested keys in order to apply filters,
                    # we can't write this result because we don't want formatted data to be written to mongo.
                    filtered_history = reader.get_sorted_history(filter_rows=True)

                    dates = filtered_history['date']

                    # Therefore using dates as indexes for the unchanged data.
                    history = reader.get_sorted_history()
                    history = history[history['date'].isin(dates)]

                    collection.delete_many({"ticker": ticker})
                    collection.insert_many(history.to_dict('records'))
                except Exception as e:
                    self.logger.exception(
                        "Couldn't filter {ticker}.{collection}".format(ticker=ticker, collection=collection_name))
                    self.logger.exception(e)

    @staticmethod
    def get_history(mongo_db, ticker):
        history = pandas.DataFrame()

        for collection_name in Factory.TICKER_COLLECTIONS.keys():
            reader = Factory.readers_factory(collection_name, **{'mongo_db': mongo_db, 'ticker': ticker})
            current = reader.get_sorted_history(filter_rows=True, filter_cols=True)

            if current.empty:
                continue
            elif history.empty:
                history = current.set_index('date')
            else:
                history = history.join(current.set_index('date'),
                                       lsuffix='_Unknown', rsuffix='_' + collection_name, how='outer')

        return history

    @staticmethod
    def get_low_floaters(mongo_db, tickers_list):
        tickers_001_1B = pandas.DataFrame(columns=['Symbol'])
        tickers_001_500M = pandas.DataFrame(columns=['Symbol'])
        tickers_003_250M = pandas.DataFrame(columns=['Symbol'])
        tickers_0006_3B_current = pandas.DataFrame(columns=['Symbol'])
        ev_tickers = pandas.DataFrame(columns=['Symbol'])
        florida_tickers = pandas.DataFrame(columns=['Symbol', 'Price'])

        for ticker in tickers_list:
            try:
                logging.getLogger('Client').info('running on {ticker}'.format(ticker=ticker))

                securities = readers.Securities(mongo_db, ticker).get_latest()
                outstanding, tier_code = int(securities['outstandingShares']), securities['tierCode']
                last_price = ReaderBase.get_last_price(ticker)
                description = readers.Profile(mongo_db, ticker).get_latest()['businessDesc']

                if last_price <= 0.001 and outstanding <= 1000000000:
                    tickers_001_1B = tickers_001_1B.append({'Symbol': ticker}, ignore_index=True)
                if last_price <= 0.001 and outstanding <= 500000000:
                    tickers_001_500M = tickers_001_500M.append({'Symbol': ticker}, ignore_index=True)
                if last_price <= 0.003 and outstanding <= 250000000:
                    tickers_003_250M = tickers_003_250M.append({'Symbol': ticker}, ignore_index=True)
                if last_price <= 0.0006 and outstanding >= 3000000000 and tier_code == 'PC':
                    tickers_0006_3B_current = tickers_0006_3B_current.append({'Symbol': ticker}, ignore_index=True)
                if Client.is_substring(description, 'electric vehicle', 'golf car', 'lithium'):
                    ev_tickers = ev_tickers.append({'Symbol': ticker}, ignore_index=True)
                if last_price <= 0.003 and readers.Profile(mongo_db, ticker).get_latest().get('state') == 'FL':
                    florida_tickers.append({'Symbol': ticker, 'Price': last_price})

            except Exception as e:
                logging.getLogger('Client').exception('ticker: {ticker}'.format(ticker=ticker), e, exc_info=True)

        with open(LOW_FLOATERS_001_1B_PATH, 'w') as tmp:
            tickers_001_1B.to_csv(tmp)
        with open(LOW_FLOATERS_001_500M_PATH, 'w') as tmp:
            tickers_001_500M.to_csv(tmp)
        with open(LOW_FLOATERS_003_250M_PATH, 'w') as tmp:
            tickers_003_250M.to_csv(tmp)
        with open(TICKERS_0006_3B_CURRENT_PATH, 'w') as tmp:
            tickers_0006_3B_current.to_csv(tmp)
        with open(EV_TICKERS_PATH, 'w') as tmp:
            ev_tickers.to_csv(tmp)
        with open(FLORIDA_TICKERS_PATH, 'w') as tmp:
            florida_tickers.to_csv(tmp)

    @staticmethod
    def is_substring(text, *args):
        """
        Looking for substrings in text while ignoring case

        :param text: A text to look in
        :param args: substrings to look for in text
        :return:
        """
        for arg in args:
            if re.search(arg, text, re.IGNORECASE):
                return True
        return False

    @staticmethod
    def get_diffs(mongo_db, ticker):
        # Pulling from diffs collection
        alerts = pandas.DataFrame(
            mongo_db.diffs.find(({"ticker": ticker})).sort('date', pymongo.ASCENDING))

        pandas.set_option('display.expand_frame_repr', False)

        # Prettify timestamps
        alerts['new'] = alerts.apply(
            lambda row: ReaderBase.timestamp_to_datestring(row['new']) if row['changed_key'] == row['changed_key'] and 'date' in row['changed_key'].lower() else row['new'],
            axis=1)
        alerts['old'] = alerts.apply(
            lambda row: ReaderBase.timestamp_to_datestring(row['old']) if ['changed_key'] == row['changed_key'] and 'date' in row['changed_key'].lower() else row['old'],
            axis=1)

        return alerts

    def clear_diffs(self):
        diffs = pandas.DataFrame(self._mongo_db.diffs.find())
        diffs.sort_values(by='date')

        all_drop_keys = ['estimatedMarketCapAsOfDate', 'estimatedMarketCap', 'latestFilingDate', 'zip',
                         'numberOfRecordShareholdersDate', 'countryId', 'hasLatestFiling',
                         'profileVerifiedAsOfDate', 'id', 'numberOfEmployeesAsOf', 'reportingStandard',
                         'latestFilingType',
                         'latestFilingUrl', 'isUnsolicited', 'stateOfIncorporation', 'stateOfIncorporationName',
                         'venue',
                         'tierGroup', 'edgarFilingStatus', 'edgarFilingStatusId', 'deregistered',
                         'isAlternativeReporting',
                         'indexStatuses', 'otcAward', 'otherSecurities', 'corporateBrokers', 'notes',
                         'reportingStandardMin',
                         'auditStatus', 'auditedStatusDisplay'] + ['outstandingSharesAsOfDate', 'outstandingShares', 'authorizedShares',
                                                                   'authorizedSharesAsOfDate', 'dtcSharesAsOfDate', 'unrestrictedShares',
                                                                   'restrictedSharesAsOfDate',
                                                                   'unrestrictedSharesAsOfDate',
                                                                   'dtcShares', 'tierStartDate', 'tierId',
                                                                   'numOfRecordShareholdersDate', 'tierName',
                                                                   'categoryName',
                                                                   'categoryId', 'tierCode', 'shortInterest',
                                                                   'shortInterestDate', 'shortInterestChange',
                                                                   'publicFloatAsOfDate', 'isNoInfo',
                                                                   'currentCapitalChangePayDate',
                                                                   'currentCapitalChangeExDate', 'currentCapitalChange',
                                                                   'currentCapitalChangeRecordDate', 'cusip',
                                                                   'hasLevel2', 'isLevel2Entitled', 'primaryVenue',
                                                                   'tierGroupId', 'isPiggyBacked',
                                                                   'notes', 'otcAward', 'showTrustedLogo',
                                                                   'isUnsolicited', 'statusName', 'foreignExchangeTier',
                                                                   'foreignExchangeName', 'isOtcQX',
                                                                   'foreignExchangeId'] + ['isPennyStockExempt',
                                                                                           'verifiedDate']

        old_df = diffs[diffs['date'] < '2021-01-28 02:56:36+00:00']
        late_df = diffs[diffs['date'] > '2021-04-24 07:15:40+00:00']
        alerted_df = diffs[
            (diffs['date'] <= '2021-04-24 07:15:40+00:00') & (diffs['date'] >= '2021-01-28 02:56:36+00:00')]

        late_drop_ids = []

        for index, row in late_df.iterrows():
            oid = row.pop('_id')
            record = row.to_dict()
            record['_id'] = {'$oid': oid}

            try:
                alerter_args = {'mongo_db': self._mongo_db, 'telegram_bot': None,
                                'ticker': record.get('ticker'), 'debug': True}
                alerter = Factory.alerters_factory(record.get('source'), **alerter_args)

                _, msg = alerter.get_alert_msg([record])
                if not msg:
                    late_drop_ids.append(oid)
            except Exception as e:
                print('exception on', oid)
                print(e)

        old_drop_ids = []

        for index, row in old_df.iterrows():
            oid = row.pop('_id')
            record = row.to_dict()
            record['_id'] = {'$oid': oid}

            if any([record.get('changed_key').startswith(key) for key in all_drop_keys]):
                old_drop_ids.append(oid)

        self._mongo_db.diffs.delete_many({'_id': {'$in': late_drop_ids}})
        self._mongo_db.diffs.delete_many({'_id': {'$in': old_drop_ids}})
        self._mongo_db.diffs.delete_many({'_id': {'$in': alerted_df[alerted_df['alerted'] == False]['_id'].to_list()}})


def main():
    try:
        Client().run()
    except Exception as e:
        logging.exception(e)


if __name__ == '__main__':
    main()
