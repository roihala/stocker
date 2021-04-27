import unittest

from src.collect.tickers.differ import Differ


class TestAlertTime(unittest.TestCase):
    def setUp(self):
        self.differ = Differ()

    def test_shallow(self):
        old = {"id": 626691, "name": "SMC Entertainment Inc.",
               "city": "San Francisco", "state": "CA", "zip": "94110     ", "countryId": "USA",
               "country": "United States",
               "address1": "3210 21st Street", "website": "http://www.smceinc.com", "phone": "3608586370",
               "fax": "213-232-3207",
               "email": "ron.hughes.operations@gmail.com"}
        new = {"id": 626691, "name": "SMC Entertainment Inc.",
               "city": "San Francisco", "state": "CA", "zip": "94110     ", "countryId": "USA",
               "country": "United States",
               "address1": "3210 21st Street", "website": "http://www.smcesolutions.com", "phone": "800-763-9598",
               "fax": "213-232-3207",
               "email": "info@smcesolutions.com",
               "stam": 'klum'}

        expected = [{'changed_key': 'email', 'old': 'ron.hughes.operations@gmail.com', 'new': 'info@smcesolutions.com',
                     'diff_type': 'change'},
                    {'changed_key': 'website', 'old': 'http://www.smceinc.com', 'new': 'http://www.smcesolutions.com',
                     'diff_type': 'change'},
                    {'changed_key': 'phone', 'old': '3608586370', 'new': '800-763-9598', 'diff_type': 'change'},
                    {'changed_key': 'stam', 'old': None, 'new': 'klum', 'diff_type': 'add'}]

        self.assertCountEqual(self.differ.get_diffs(old, new), expected)

    def test_dict_changes(self):
        old = {"id": 626691, "name": "SMC Entertainment Inc.",
               "city": "San Francisco", "state": "CA", "zip": "94110     ", "countryId": "USA",
               "country": "United States",
               "address1": "3210 21st Street", "website": "http://www.smceinc.com", "phone": "3608586370",
               "fax": "213-232-3207",
               "email": "ron.hughes.operations@gmail.com",
               "otcAward": {"symbol": "SMCE", "best50": True}}
        new = {"id": 626691, "name": "SMC Entertainment Inc.",
               "city": "San Francisco", "state": "CA", "zip": "94110     ", "countryId": "USA",
               "country": "United States",
               "address1": "3210 21st Street", "website": "http://www.smceinc.com", "phone": "3608586370",
               "fax": "213-232-3207",
               "email": "ron.hughes.operations@gmail.com",
               "otcAward": {"symbol": "SMCE", "best50": False}}

        expected_no_hierarchy = [{'changed_key': 'otcAward', 'old': {'symbol': 'SMCE', 'best50': True},
                                  'new': {'symbol': 'SMCE', 'best50': False}, 'diff_type': 'change'}]

        self.assertCountEqual(self.differ.get_diffs(old, new), expected_no_hierarchy)

        expected_with_hierarchy = [
            {'changed_key': ['otcAward', 'best50'], 'old': True, 'new': False, 'diff_type': 'change'}]

        self.assertCountEqual(self.differ.get_diffs(old, new, {'otcAward': [dict, 'best50']}), expected_with_hierarchy)

    def test_list_changes(self):
        old = {"id": 626691, "name": "SMC Entertainment Inc.",
               "city": "San Francisco", "state": "CA", "zip": "94110     ", "countryId": "USA",
               "country": "United States",
               "address1": "3210 21st Street", "website": "http://www.smceinc.com", "phone": "3608586370",
               "fax": "213-232-3207",
               "email": "ron.hughes.operations@gmail.com",
               "notes": ["Formerly=SMC Recordings Inc. until 5-2011", "Formerly=Action Energy Corp. until 9-2009",
                         "Formerly=ZooLink Corp. until 4-2009", "Formerly=NetJ.com Corp. until 11-02",
                         "Formerly=NetBanx.com Corp. until 11-99"]}
        new = {"id": 626691, "name": "SMC Entertainment Inc.",
               "city": "San Francisco", "state": "CA", "zip": "94110     ", "countryId": "USA",
               "country": "United States",
               "address1": "3210 21st Street", "website": "http://www.smceinc.com", "phone": "3608586370",
               "fax": "213-232-3207",
               "email": "ron.hughes.operations@gmail.com",
               "notes": ["Formerly=SMC Recordings Inc. until 5-2011", "Formerly=Action Energy Corp. until 9-2009",
                         "Formerly=ZooLink Corp. until 4-2009", "Formerly=NetJ.com Corp. until 11-02",
                         "Formerly=NetBanx.com Corp. until 11-99",
                         "Formerly=Professional Recovery Systems, Ltd. until 8-99"]}

        expected = [
            {'changed_key': ['notes'], 'old': None, 'new': 'Formerly=Professional Recovery Systems, Ltd. until 8-99',
             'diff_type': 'add'}]

        self.assertCountEqual(self.differ.get_diffs(old, new, {'notes': [list]}), expected)

    def test_nested_changes(self):
        old = {"id": 626691, "name": "SMC Entertainment Inc.",
               "otcAward": {"symbol": "SMCE", "best50": False},
               "officers": [{"name": "Rick Bjorklund", "title": "CEO", "boards": "",
                             "biography": "Mr. Bjorklund has over 40 years of international executive experience in entertainment, sport and facility management, and wireless industries. He has lead companies such as Wembley PLC, Arizona and Wisconsin State Fairs, Pontiac Silverdome, Three Rivers Stadium Authority and Rosemont Horizon Arena. He has advised clients such as Walt Disney Imagineering as well as numerous Olympic and national sporting associations around the world, including the NFL, MLB, FIFA, UEFA and the NBA. He deployed the first use of microwave and wireless communications to identify and combat European Football security risks. Prior to joining SMC, Mr. Bjorklund was Chairman of Sanwire Corporation, a company specializes in wireless communications. Mr. Bjorklund has served on Boards of Directors for the International Entertainment Buyers Association, Golden Triangle Development Association, Bridge Park Development Association, Association of Facility Design and Development, Variety Club Children's Charities and Toys for Tots. Mr. Bjorklund's education includes Arizona State University, Bachelor of Science Degree, U.S. Air Force Academy with commendations as National Facility Manager of the Year and International Facility of the Year."},
                            {"name": "Ronald Hughes-Halamish", "title": "COO", "boards": ""},
                            {"name": "Rachel Boulds", "title": "CFO", "boards": "",
                             "biography": "Ms. Boulds has been engaged in private practice as an accountant and consultant. She specializes in preparation of full disclosure financial statements for public companies to comply with GAAP and SEC requirements. From August 2004 through July 2009, she was employed as an audit senior for HJ & Associates, LLC, where she performed audits and reviews for public and private companies, including the preparation of financial statements to comply with GAAP and SEC requirements. From 2003 through 2004, Ms. Boulds was employed as an audit senior for Mohler, Nixon and Williams. From September 2001, through July 2003, Ms. Boulds worked as an ABAS associate for PriceWaterhouseCoopers. From April 2000 through February 2001, she was employed an an eCommerce accountant for the Walt Disney Group's GO.com division. Ms. Boulds holds a B.S. in accounting from San Jose State University, 2001 and is licensed as a CPA in the state of Utah."},
                            {"name": "Neil Mavis", "title": "CTO", "boards": "",
                             "biography": "With over twenty-five years in the telecommunications industry including fiber optics and wireless technologies, Mr. Mavis' career has included positions as a field engineer, product manager, sales engineer, sales account manager, and wireless architect. Mr. MavisÃ¢ÂÂ accomplishments include selling a $300 million contract for SONET DWDM EDFA. Mr. Mavis holds a B.S. in Electrical Engineering from Southern Tech Marietta, and an MBA Marketing degree from Atlanta-based Mercer University. Ms. Boulds has been engaged in private practice as an accountant and consultant."}]}

        new = {"id": 626691, "name": "SMC Entertainment Inc.",
               "otcAward": {"symbol": "SMCE", "best50": False},
               "officers": [{"name": "Ronald Hughes", "title": "COO", "boards": ""},
                            {"name": "Rachel Boulds", "title": "CFO", "boards": "",
                             "biography": "Ms. Boulds has been engaged in private practice as an accountant and consultant. She specializes in preparation of full disclosure financial statements for public companies to comply with GAAP and SEC requirements. From August 2004 through July 2009, she was employed as an audit senior for HJ & Associates, LLC, where she performed audits and reviews for public and private companies, including the preparation of financial statements to comply with GAAP and SEC requirements. From 2003 through 2004, Ms. Boulds was employed as an audit senior for Mohler, Nixon and Williams. From September 2001, through July 2003, Ms. Boulds worked as an ABAS associate for PriceWaterhouseCoopers. From April 2000 through February 2001, she was employed an an eCommerce accountant for the Walt Disney Group's GO.com division. Ms. Boulds holds a B.S. in accounting from San Jose State University, 2001 and is licensed as a CPA in the state of Utah."},
                            {"name": "Neil Mavis", "title": "CTO", "boards": "",
                             "biography": "With over twenty-five years in the telecommunications industry including fiber optics and wireless technologies, Mr. Mavis' career has included positions as a field engineer, product manager, sales engineer, sales account manager, and wireless architect. Mr. MavisÃ¢ÂÂ accomplishments include selling a $300 million contract for SONET DWDM EDFA. Mr. Mavis holds a B.S. in Electrical Engineering from Southern Tech Marietta, and an MBA Marketing degree from Atlanta-based Mercer University. Ms. Boulds has been engaged in private practice as an accountant and consultant."}]}
        expected = \
            [{'changed_key': ['officers', 'name'], 'old': 'Rick Bjorklund', 'new': 'Ronald Hughes',
              'diff_type': 'change'},
             {'changed_key': ['officers', 'name'], 'old': 'Ronald Hughes-Halamish', 'new': None, 'diff_type': 'remove'}]

        self.assertCountEqual(self.differ.get_diffs(old, new, {'officers': [list, dict, 'name']}), expected)

        old = {"id": 626691, "name": "SMC Entertainment Inc.",
               "otcAward": {"symbol": "SMCE", "best50": False},
               "descriptors": {'name': ['a', 'b', 'c'], 'kaki': ['aaa', 'bbb', 'ccc']}}

        new = {"id": 626691, "name": "SMC Entertainment Inc.",
               "otcAward": {"symbol": "SMCE", "best50": False},
               "descriptors": {'name': ['d', 'b', 'c', 'e'], 'kaki': ['aaa', 'bbb', 'ccc']}}

        expected = [{'changed_key': ['descriptors', 'name'], 'old': 'a', 'new': 'd', 'diff_type': 'change'}, {'changed_key': ['descriptors', 'name'], 'old': None, 'new': 'e', 'diff_type': 'add'}]

        self.assertCountEqual(self.differ.get_diffs(old, new, {'descriptors': [dict, 'name', list]}), expected)

    def test_all_together(self):
        old = {"id": 626691, "name": "SMC Entertainment Inc.",
               "city": "San Francisco", "state": "CA", "zip": "94110     ", "countryId": "USA",
               "country": "United States",
               "address1": "3210 21st Street", "website": "http://www.smceinc.com", "phone": "3608586370",
               "fax": "213-232-3207",
               "email": "ron.hughes.operations@gmail.com",
               "otcAward": {"symbol": "SMCE", "best50": True},
               "notes": ["Formerly=SMC Recordings Inc. until 5-2011", "Formerly=Action Energy Corp. until 9-2009",
                         "Formerly=ZooLink Corp. until 4-2009", "Formerly=NetJ.com Corp. until 11-02",
                         "Formerly=NetBanx.com Corp. until 11-99"],
               "officers": [{"name": "Rick Bjorklund", "title": "CEO", "boards": "",
                             "biography": "Mr. Bjorklund has over 40 years of international executive experience in entertainment, sport and facility management, and wireless industries. He has lead companies such as Wembley PLC, Arizona and Wisconsin State Fairs, Pontiac Silverdome, Three Rivers Stadium Authority and Rosemont Horizon Arena. He has advised clients such as Walt Disney Imagineering as well as numerous Olympic and national sporting associations around the world, including the NFL, MLB, FIFA, UEFA and the NBA. He deployed the first use of microwave and wireless communications to identify and combat European Football security risks. Prior to joining SMC, Mr. Bjorklund was Chairman of Sanwire Corporation, a company specializes in wireless communications. Mr. Bjorklund has served on Boards of Directors for the International Entertainment Buyers Association, Golden Triangle Development Association, Bridge Park Development Association, Association of Facility Design and Development, Variety Club Children's Charities and Toys for Tots. Mr. Bjorklund's education includes Arizona State University, Bachelor of Science Degree, U.S. Air Force Academy with commendations as National Facility Manager of the Year and International Facility of the Year."},
                            {"name": "Ronald Hughes-Halamish", "title": "COO", "boards": ""},
                            {"name": "Rachel Boulds", "title": "CFO", "boards": "",
                             "biography": "Ms. Boulds has been engaged in private practice as an accountant and consultant. She specializes in preparation of full disclosure financial statements for public companies to comply with GAAP and SEC requirements. From August 2004 through July 2009, she was employed as an audit senior for HJ & Associates, LLC, where she performed audits and reviews for public and private companies, including the preparation of financial statements to comply with GAAP and SEC requirements. From 2003 through 2004, Ms. Boulds was employed as an audit senior for Mohler, Nixon and Williams. From September 2001, through July 2003, Ms. Boulds worked as an ABAS associate for PriceWaterhouseCoopers. From April 2000 through February 2001, she was employed an an eCommerce accountant for the Walt Disney Group's GO.com division. Ms. Boulds holds a B.S. in accounting from San Jose State University, 2001 and is licensed as a CPA in the state of Utah."},
                            {"name": "Neil Mavis", "title": "CTO", "boards": "",
                             "biography": "With over twenty-five years in the telecommunications industry including fiber optics and wireless technologies, Mr. Mavis' career has included positions as a field engineer, product manager, sales engineer, sales account manager, and wireless architect. Mr. MavisÃ¢ÂÂ accomplishments include selling a $300 million contract for SONET DWDM EDFA. Mr. Mavis holds a B.S. in Electrical Engineering from Southern Tech Marietta, and an MBA Marketing degree from Atlanta-based Mercer University. Ms. Boulds has been engaged in private practice as an accountant and consultant."}],
               "descriptors": {'name': ['a', 'b', 'c'], 'kaki': ['aaa', 'bbb', 'ccc']}
               }
        new = {"id": 626691, "name": "SMC Entertainment Inc.",
               "city": "San Francisco", "state": "CA", "zip": "94110     ", "countryId": "USA",
               "country": "United States",
               "address1": "3210 21st Street", "website": "http://www.smcesolutions.com", "phone": "800-763-9598",
               "fax": "213-232-3207",
               "email": "info@smcesolutions.com",
               "otcAward": {"symbol": "SMCE", "best50": False},
               "notes": ["Formerly=SMC Recordings Inc. until 5-2011", "Formerly=Action Energy Corp. until 9-2009",
                         "Formerly=ZooLink Corp. until 4-2009", "Formerly=NetJ.com Corp. until 11-02",
                         "Formerly=NetBanx.com Corp. until 11-99",
                         "Formerly=Professional Recovery Systems, Ltd. until 8-99"],
               "officers": [{"name": "Ronald Hughes", "title": "COO", "boards": ""},
                            {"name": "Rachel Boulds", "title": "CFO", "boards": "",
                             "biography": "Ms. Boulds has been engaged in private practice as an accountant and consultant. She specializes in preparation of full disclosure financial statements for public companies to comply with GAAP and SEC requirements. From August 2004 through July 2009, she was employed as an audit senior for HJ & Associates, LLC, where she performed audits and reviews for public and private companies, including the preparation of financial statements to comply with GAAP and SEC requirements. From 2003 through 2004, Ms. Boulds was employed as an audit senior for Mohler, Nixon and Williams. From September 2001, through July 2003, Ms. Boulds worked as an ABAS associate for PriceWaterhouseCoopers. From April 2000 through February 2001, she was employed an an eCommerce accountant for the Walt Disney Group's GO.com division. Ms. Boulds holds a B.S. in accounting from San Jose State University, 2001 and is licensed as a CPA in the state of Utah."},
                            {"name": "Neil Mavis", "title": "CTO", "boards": "",
                             "biography": "With over twenty-five years in the telecommunications industry including fiber optics and wireless technologies, Mr. Mavis' career has included positions as a field engineer, product manager, sales engineer, sales account manager, and wireless architect. Mr. MavisÃ¢ÂÂ accomplishments include selling a $300 million contract for SONET DWDM EDFA. Mr. Mavis holds a B.S. in Electrical Engineering from Southern Tech Marietta, and an MBA Marketing degree from Atlanta-based Mercer University. Ms. Boulds has been engaged in private practice as an accountant and consultant."}],
               "descriptors": {'name': ['d', 'b', 'c', 'e'], 'kaki': ['aaa', 'bbb', 'ccc']}
               }

        expected_no_hierarchy = [{'changed_key': 'officers', 'old': [{'name': 'Rick Bjorklund', 'title': 'CEO', 'boards': '', 'biography': "Mr. Bjorklund has over 40 years of international executive experience in entertainment, sport and facility management, and wireless industries. He has lead companies such as Wembley PLC, Arizona and Wisconsin State Fairs, Pontiac Silverdome, Three Rivers Stadium Authority and Rosemont Horizon Arena. He has advised clients such as Walt Disney Imagineering as well as numerous Olympic and national sporting associations around the world, including the NFL, MLB, FIFA, UEFA and the NBA. He deployed the first use of microwave and wireless communications to identify and combat European Football security risks. Prior to joining SMC, Mr. Bjorklund was Chairman of Sanwire Corporation, a company specializes in wireless communications. Mr. Bjorklund has served on Boards of Directors for the International Entertainment Buyers Association, Golden Triangle Development Association, Bridge Park Development Association, Association of Facility Design and Development, Variety Club Children's Charities and Toys for Tots. Mr. Bjorklund's education includes Arizona State University, Bachelor of Science Degree, U.S. Air Force Academy with commendations as National Facility Manager of the Year and International Facility of the Year."}, {'name': 'Ronald Hughes-Halamish', 'title': 'COO', 'boards': ''}, {'name': 'Rachel Boulds', 'title': 'CFO', 'boards': '', 'biography': "Ms. Boulds has been engaged in private practice as an accountant and consultant. She specializes in preparation of full disclosure financial statements for public companies to comply with GAAP and SEC requirements. From August 2004 through July 2009, she was employed as an audit senior for HJ & Associates, LLC, where she performed audits and reviews for public and private companies, including the preparation of financial statements to comply with GAAP and SEC requirements. From 2003 through 2004, Ms. Boulds was employed as an audit senior for Mohler, Nixon and Williams. From September 2001, through July 2003, Ms. Boulds worked as an ABAS associate for PriceWaterhouseCoopers. From April 2000 through February 2001, she was employed an an eCommerce accountant for the Walt Disney Group's GO.com division. Ms. Boulds holds a B.S. in accounting from San Jose State University, 2001 and is licensed as a CPA in the state of Utah."}, {'name': 'Neil Mavis', 'title': 'CTO', 'boards': '', 'biography': "With over twenty-five years in the telecommunications industry including fiber optics and wireless technologies, Mr. Mavis' career has included positions as a field engineer, product manager, sales engineer, sales account manager, and wireless architect. Mr. MavisÃ¢Â\x80Â\x99 accomplishments include selling a $300 million contract for SONET DWDM EDFA. Mr. Mavis holds a B.S. in Electrical Engineering from Southern Tech Marietta, and an MBA Marketing degree from Atlanta-based Mercer University. Ms. Boulds has been engaged in private practice as an accountant and consultant."}], 'new': [{'name': 'Ronald Hughes', 'title': 'COO', 'boards': ''}, {'name': 'Rachel Boulds', 'title': 'CFO', 'boards': '', 'biography': "Ms. Boulds has been engaged in private practice as an accountant and consultant. She specializes in preparation of full disclosure financial statements for public companies to comply with GAAP and SEC requirements. From August 2004 through July 2009, she was employed as an audit senior for HJ & Associates, LLC, where she performed audits and reviews for public and private companies, including the preparation of financial statements to comply with GAAP and SEC requirements. From 2003 through 2004, Ms. Boulds was employed as an audit senior for Mohler, Nixon and Williams. From September 2001, through July 2003, Ms. Boulds worked as an ABAS associate for PriceWaterhouseCoopers. From April 2000 through February 2001, she was employed an an eCommerce accountant for the Walt Disney Group's GO.com division. Ms. Boulds holds a B.S. in accounting from San Jose State University, 2001 and is licensed as a CPA in the state of Utah."}, {'name': 'Neil Mavis', 'title': 'CTO', 'boards': '', 'biography': "With over twenty-five years in the telecommunications industry including fiber optics and wireless technologies, Mr. Mavis' career has included positions as a field engineer, product manager, sales engineer, sales account manager, and wireless architect. Mr. MavisÃ¢Â\x80Â\x99 accomplishments include selling a $300 million contract for SONET DWDM EDFA. Mr. Mavis holds a B.S. in Electrical Engineering from Southern Tech Marietta, and an MBA Marketing degree from Atlanta-based Mercer University. Ms. Boulds has been engaged in private practice as an accountant and consultant."}], 'diff_type': 'change'}, {'changed_key': 'website', 'old': 'http://www.smceinc.com', 'new': 'http://www.smcesolutions.com', 'diff_type': 'change'}, {'changed_key': 'phone', 'old': '3608586370', 'new': '800-763-9598', 'diff_type': 'change'}, {'changed_key': 'email', 'old': 'ron.hughes.operations@gmail.com', 'new': 'info@smcesolutions.com', 'diff_type': 'change'}, {'changed_key': 'otcAward', 'old': {'symbol': 'SMCE', 'best50': True}, 'new': {'symbol': 'SMCE', 'best50': False}, 'diff_type': 'change'}, {'changed_key': 'descriptors', 'old': {'name': ['a', 'b', 'c'], 'kaki': ['aaa', 'bbb', 'ccc']}, 'new': {'name': ['d', 'b', 'c', 'e'], 'kaki': ['aaa', 'bbb', 'ccc']}, 'diff_type': 'change'}, {'changed_key': 'notes', 'old': ['Formerly=SMC Recordings Inc. until 5-2011', 'Formerly=Action Energy Corp. until 9-2009', 'Formerly=ZooLink Corp. until 4-2009', 'Formerly=NetJ.com Corp. until 11-02', 'Formerly=NetBanx.com Corp. until 11-99'], 'new': ['Formerly=SMC Recordings Inc. until 5-2011', 'Formerly=Action Energy Corp. until 9-2009', 'Formerly=ZooLink Corp. until 4-2009', 'Formerly=NetJ.com Corp. until 11-02', 'Formerly=NetBanx.com Corp. until 11-99', 'Formerly=Professional Recovery Systems, Ltd. until 8-99'], 'diff_type': 'change'}]

        self.assertCountEqual(self.differ.get_diffs(old, new), expected_no_hierarchy)

        hierarchy = {
            'otcAward': [dict, 'best50'],
            'notes': [list],
            'officers': [list, dict, 'name'],
            'descriptors': [dict, 'name', list]
        }
        expected = [{'changed_key': 'phone', 'old': '3608586370', 'new': '800-763-9598', 'diff_type': 'change'}, {'changed_key': ['notes'], 'old': None, 'new': 'Formerly=Professional Recovery Systems, Ltd. until 8-99', 'diff_type': 'add'}, {'changed_key': ['descriptors', 'name'], 'old': 'a', 'new': 'd', 'diff_type': 'change'}, {'changed_key': ['descriptors', 'name'], 'old': None, 'new': 'e', 'diff_type': 'add'}, {'changed_key': 'email', 'old': 'ron.hughes.operations@gmail.com', 'new': 'info@smcesolutions.com', 'diff_type': 'change'}, {'changed_key': 'website', 'old': 'http://www.smceinc.com', 'new': 'http://www.smcesolutions.com', 'diff_type': 'change'}, {'changed_key': ['officers', 'name'], 'old': 'Rick Bjorklund', 'new': 'Ronald Hughes', 'diff_type': 'change'}, {'changed_key': ['officers', 'name'], 'old': 'Ronald Hughes-Halamish', 'new': None, 'diff_type': 'remove'}, {'changed_key': ['otcAward', 'best50'], 'old': True, 'new': False, 'diff_type': 'change'}]

        self.assertCountEqual(self.differ.get_diffs(old, new, hierarchy), expected)

    def test_empty_strings(self):
        old = {"id": 626691, "name": "SMC Entertainment Inc.",
               "city": "San Francisco", "state": "CA", "zip": "94110     ", "countryId": "USA",
               "country": "United States",
               "address1": "nan", "website": "http://www.smceinc.com", "phone": "3608586370",
               "fax": "nan",
               "email": "aaa@gmail",
               "otcAward": {"symbol": "SMCE", "best50": None}}
        new = {"id": 626691, "name": "SMC Entertainment Inc.",
               "city": "San Francisco", "state": "CA", "zip": "94110     ", "countryId": "USA",
               "country": "United States",
               "address1": None, "website": "http://www.smceinc.com", "phone": "3608586370",
               "fax": "213-232-3207",
               "email": None,
               "otcAward": {"symbol": "SMCE", "best50": ''}}

        # expected_with_hierarchy = [
        #     {'changed_key': ['otcAward', 'best50'], 'old': True, 'new': False, 'diff_type': 'change'}]

        expected = [
            {'changed_key': 'email', 'old': 'aaa@gmail', 'new': None, 'diff_type': 'remove'},
            {'changed_key': 'fax', 'old': 'nan', 'new': '213-232-3207', 'diff_type': 'add'}]

        self.assertCountEqual(self.differ.get_diffs(old, new, {'otcAward': [dict, 'best50']}), expected)


if __name__ == '__main__':
    unittest.main()
