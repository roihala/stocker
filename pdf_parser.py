import pandas as pd
import requests
import re
import fitz

BASE_URL = r"http://www.otcmarkets.com/financialReportViewer?id="
NAMES_CSV = r"C:\Users\RoiHa\PycharmProjects\stock-info\src\games\names.csv"
PDF_DIR = "pdfs/"

LAST_RECORD = 287747
MAX_PAGE_SEARCH = 3


def get_pdf(id: str) -> str:
    url = BASE_URL + id
    pdf_path = PDF_DIR + f"{id}.pdf"

    try:
        resp = requests.get(url)
        with open(pdf_path, 'wb') as f:
            f.write(resp.content)
    except:
        return None

    return pdf_path


def load_symbols(csv_path: str) -> dict:
    return pd.read_csv(csv_path, header=None, index_col=0, squeeze=True).to_dict()


def get_symbol_from_map(symbols_map: dict, comp_name: str) -> str:
    # TODO: Change names.csv company names to lower without commas or dots.
    # that will save us the name.lower().replace(',', '').replace('.', '') statement.
    if type(comp_name) is not str or not comp_name:
        return None

    # the exact same company name
    for symbol, name in symbols_map.items():
        if comp_name == name.lower().replace(',', '').replace('.', ''):
            return symbol

    return None


def extract_company_names_from_pdf(pdf_path: str, page_number: int) -> list:
    comp_abbreviations = ["inc", "ltd", "corp", "corporation", "incorporated"]
    companies = []

    try:
        with fitz.open(pdf_path) as doc:
            page = doc[page_number]
            txt = " ".join(page.getText().lower().split())
    except:
        return None

    for abr in comp_abbreviations:
        regex = fr"((?:[a-z\.,-]+ ){{1,4}}{abr}[\. ])"
        matches = re.findall(regex, txt)

        if matches:
            companies = companies + matches

    return (None if not companies else companies)


def get_symbol_from_pdf(id: str) -> str:
    pdf_path = get_pdf(id)

    if not pdf_path:
        return None

    for page_number in range(0, MAX_PAGE_SEARCH):

        # ['otc markets group inc', 'guidelines v group , inc']
        companies = extract_company_names_from_pdf(pdf_path, page_number)

        if not companies:
            continue

        # split to words & remove commas & dots
        companies_opt = [comp.replace(',', '').replace('.', '').split() for comp in companies]

        # [['otc', 'markets', 'group', 'inc'], ['guidelines', 'v', 'group', 'inc']] ->
        # [['otc markets group inc', 'markets group inc', 'group inc'], ['guidelines v group inc', 'v group inc', 'group inc']]
        optional_companies = [[" ".join(comp[i:]) for i in range(0, len(comp) - 1)] for comp in companies_opt]
        symbols = load_symbols(NAMES_CSV)
        """
        optional companies -> [["a b c", "b c"], ["d g b c", "g b c", "b c"]]
        search "a b c" -> "d g b c" -> "b c" -> "g b c" ...
        """
        for index in range(0, max(len(_) for _ in optional_companies)):
            for comp_name in optional_companies:
                if (index >= len(comp_name)):
                    continue

                result = get_symbol_from_map(symbols, comp_name[index])

                if result:
                    return result

    return None


def get_ticker_by_id(record_id):
    records_url = 'https://backend.otcmarkets.com/otcapi/company/financial-report/?pageSize=50&page={page}&sortOn=releaseDate&sortDir=DESC'

    estimeted_page = int((LAST_RECORD - record_id) / 50) + 1

    starting_at = 0 if (estimeted_page - 10 < 0) else estimeted_page - 10

    for page_counter in range(starting_at, estimeted_page):
        try:
            for record in requests.get(records_url.format(page=page_counter)).json().get('records'):
                if int(record.get('id')) == int(record_id):
                    return record.get('symbol')
        except Exception as e:
            print(f"Couldn't find record at page: {page_counter}")
            print(e)
    return None


def test():
    success = []
    fail = []

    current_record = LAST_RECORD
    tickers = pd.read_csv(NAMES_CSV)['Symbol']

    while (len(success) + len(fail)) < 100:
        ticker = get_ticker_by_id(current_record)

        if ticker in tickers.values:
            guess = get_symbol_from_pdf(str(current_record))

            print(current_record, 'guess', guess, 'ticker', ticker)
            if guess == ticker:
                success.append(current_record)
            else:
                fail.append(current_record)

        current_record -= 1

    print(f'success rate {len(success)}%')
    print(f'success {success}')
    print(f'fail {fail}')


if __name__ == '__main__':
    test()

# VGID = "283347" # working
# VGID_2 = "283346" # working
# DJIFF = "278949" # debug -> name in csv = Dajin Lithium Corp.     name in doc = Dajin Resources Corp.
# MOBO = "268911" # working
# SQTI = "172005" # working
# SQTI_2 = "172004" # working
# SQTI_3 = "164030" # company name appear first time in page 7, function stops after page 3.
# AHROQ = "129593" # working
# AHROQ_2 = "109651" # working
# AHROQ_3 = "101935" # working
# AHROQ_4 = "66698" # working
# PLFX = "220449" # debug -> name in csv = pulse evolution corp.    name in doc = pulse evolution corporation.
# CCTC = "277194" # working
# CCTC_2 = "219610" # working
# CCTC_3 = "13009" # debug -> company name does not appear in doc.
# EWRC = "283413" # debug -> name in csv = eWorld Companies, Inc.     name in doc = e-World Companies, Inc.
# EWRC_2 = "277262" # working
# EWRC_3 = "277263" # working
# COLUF = "114265" # working
# COLUF_2 = "109509" # working
# COLUF_3 = "108388" # working
# HMLA = "133193" # working

# print(get_symbol_from_pdf(HMLA))



