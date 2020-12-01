import unittest

from src.collect.differ import Differ


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
               "email": "info@smcesolutions.com"}

        expected = [{'changed_key': 'email', 'old': 'ron.hughes.operations@gmail.com', 'new': 'info@smcesolutions.com',
                     'diff_type': 'change'},
                    {'changed_key': 'website', 'old': 'http://www.smceinc.com', 'new': 'http://www.smcesolutions.com',
                     'diff_type': 'change'},
                    {'changed_key': 'phone', 'old': '3608586370', 'new': '800-763-9598', 'diff_type': 'change'}]

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

        # print('zehu', self.differ.get_diffs(old, new, {'otcAward': [dict, 'best50']}))

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

if __name__ == '__main__':
    unittest.main()


def x():
    {"_id": {"$oid": "5fc3c33775e93f8dd403a51a"}, "id": 626691, "name": "SMC Entertainment Inc.",
     "city": "San Francisco", "state": "CA", "zip": "94110     ", "countryId": "USA", "country": "United States",
     "address1": "3210 21st Street", "website": "http://www.smceinc.com", "phone": "3608586370", "fax": "213-232-3207",
     "businessDesc": "Our primary business is to provide media and wireless internet service to under-served markets, globally. Our strategy is to acquire under-capitalized WISPs and other communication service providers, whereby we bring additional investments to upgrade their infrastructure (towers, antennas, radios, etc.) to a higher capacity and speed. This strategy will help us achieve a much faster revenue growth at a lower cost.",
     "stateOfIncorporation": "NV ", "stateOfIncorporationName": "Nevada", "countryOfIncorporation": "USA",
     "countryOfIncorporationName": "United States", "yearOfIncorporation": "1998", "premierDirectorList": [
        {"name": "Rick Bjorklund", "title": "Chairman", "boards": "",
         "biography": "Mr. Bjorklund has over 40 years of international executive experience in entertainment, sport and facility management, and wireless industries. He has lead companies such as Wembley PLC, Arizona and Wisconsin State Fairs, Pontiac Silverdome, Three Rivers Stadium Authority and Rosemont Horizon Arena. He has advised clients such as Walt Disney Imagineering as well as numerous Olympic and national sporting associations around the world, including the NFL, MLB, FIFA, UEFA and the NBA. He deployed the first use of microwave and wireless communications to identify and combat European Football security risks. Prior to joining SMC, Mr. Bjorklund was Chairman of Sanwire Corporation, a company specializes in wireless communications. Mr. Bjorklund has served on Boards of Directors for the International Entertainment Buyers Association, Golden Triangle Development Association, Bridge Park Development Association, Association of Facility Design and Development, Variety Club Children's Charities and Toys for Tots. Mr. Bjorklund's education includes Arizona State University, Bachelor of Science Degree, U.S. Air Force Academy with commendations as National Facility Manager of the Year and International Facility of the Year."}],
     "standardDirectorList": [], "officers": [{"name": "Rick Bjorklund", "title": "CEO", "boards": "",
                                               "biography": "Mr. Bjorklund has over 40 years of international executive experience in entertainment, sport and facility management, and wireless industries. He has lead companies such as Wembley PLC, Arizona and Wisconsin State Fairs, Pontiac Silverdome, Three Rivers Stadium Authority and Rosemont Horizon Arena. He has advised clients such as Walt Disney Imagineering as well as numerous Olympic and national sporting associations around the world, including the NFL, MLB, FIFA, UEFA and the NBA. He deployed the first use of microwave and wireless communications to identify and combat European Football security risks. Prior to joining SMC, Mr. Bjorklund was Chairman of Sanwire Corporation, a company specializes in wireless communications. Mr. Bjorklund has served on Boards of Directors for the International Entertainment Buyers Association, Golden Triangle Development Association, Bridge Park Development Association, Association of Facility Design and Development, Variety Club Children's Charities and Toys for Tots. Mr. Bjorklund's education includes Arizona State University, Bachelor of Science Degree, U.S. Air Force Academy with commendations as National Facility Manager of the Year and International Facility of the Year."},
                                              {"name": "Ronald Hughes", "title": "COO", "boards": ""},
                                              {"name": "Rachel Boulds", "title": "CFO", "boards": "",
                                               "biography": "Ms. Boulds has been engaged in private practice as an accountant and consultant. She specializes in preparation of full disclosure financial statements for public companies to comply with GAAP and SEC requirements. From August 2004 through July 2009, she was employed as an audit senior for HJ & Associates, LLC, where she performed audits and reviews for public and private companies, including the preparation of financial statements to comply with GAAP and SEC requirements. From 2003 through 2004, Ms. Boulds was employed as an audit senior for Mohler, Nixon and Williams. From September 2001, through July 2003, Ms. Boulds worked as an ABAS associate for PriceWaterhouseCoopers. From April 2000 through February 2001, she was employed an an eCommerce accountant for the Walt Disney Group's GO.com division. Ms. Boulds holds a B.S. in accounting from San Jose State University, 2001 and is licensed as a CPA in the state of Utah."},
                                              {"name": "Neil Mavis", "title": "CTO", "boards": "",
                                               "biography": "With over twenty-five years in the telecommunications industry including fiber optics and wireless technologies, Mr. Mavis' career has included positions as a field engineer, product manager, sales engineer, sales account manager, and wireless architect. Mr. MavisÃ¢ÂÂ accomplishments include selling a $300 million contract for SONET DWDM EDFA. Mr. Mavis holds a B.S. in Electrical Engineering from Southern Tech Marietta, and an MBA Marketing degree from Atlanta-based Mercer University. Ms. Boulds has been engaged in private practice as an accountant and consultant."}],
     "fiscalYearEnd": "12/31", "filingCycle": "Q", "edgarFilingStatus": "Alternative Reporting Standard",
     "edgarFilingStatusId": "A", "reportingStandard": "Dark: Alternative Reporting Standard",
     "reportingStandardMin": "Dark or Defunct", "deregistered": true,
     "deregistrationDate": {"$numberLong": "1160107200000"}, "is12g32b": false, "cik": "0001094806",
     "isAlternativeReporting": true, "isBankThrift": false, "isNonBankRegulated": false,
     "isInternationalReporting": false, "isOtherReporting": false, "auditedStatusDisplay": "Not Available",
     "auditStatus": "N", "audited": false, "email": "ron.hughes.operations@gmail.com", "numberOfEmployees": 6,
     "numberOfEmployeesAsOf": {"$numberLong": "1583211600000"},
     "numberOfRecordShareholdersDate": {"$numberLong": "1583211600000"},
     "primarySicCode": "3652 - Prerecorded records and tapes", "auditors": [
        {"id": 5096, "type": "AD", "typeId": 5, "typeName": "Accounting/Auditing Firm", "name": "Rachel Boulds, CPA",
         "phone": "801-230-3945", "countryId": "USA", "country": "United States", "address1": "6371 Glen Oaks Street",
         "city": "Murray", "stateId": "UT", "zip": "84107", "roles": ["Accounting/Auditing Firm"], "isPublic": true,
         "hasLogo": false, "isGoodStanding": true, "isProhibited": false, "isQuestionable": false, "isAttorney": false,
         "isSponsor": false, "public": true}], "investorRelationFirms": [], "legalCounsels": [
        {"id": 3113, "type": "LC", "typeId": 3, "typeName": "Securities Counsel", "name": "Vic Devlaeminck PC",
         "phone": "(360) 993-0201", "email": "jevic321@aol.com", "countryId": "USA", "country": "United States",
         "address1": "10013 N.E. Hazel Dell Avenue", "address2": "Suite 317", "city": "Vancouver", "stateId": "WA",
         "zip": "98685", "roles": ["Securities Counsel", "Accounting/Auditing Firm"], "isPublic": true,
         "hasLogo": false, "isGoodStanding": false, "isProhibited": false, "isQuestionable": true, "isAttorney": true,
         "isSponsor": false, "public": true}], "investmentBanks": [], "corporateBrokers": [],
     "notes": ["Formerly=SMC Recordings Inc. until 5-2011", "Formerly=Action Energy Corp. until 9-2009",
               "Formerly=ZooLink Corp. until 4-2009", "Formerly=NetJ.com Corp. until 11-02",
               "Formerly=NetBanx.com Corp. until 11-99", "Formerly=Professional Recovery Systems, Ltd. until 8-99"],
     "otherSecurities": [], "estimatedMarketCap": 1074543.6194,
     "estimatedMarketCapAsOfDate": {"$numberLong": "1606453200000"}, "blankCheck": false, "blindPool": false,
     "spac": false, "hasLatestFiling": true, "latestFilingType": "Annual Report",
     "latestFilingDate": {"$numberLong": "1577768400000"},
     "latestFilingUrl": "/company/financial-report/265009/content", "tierGroup": "PS", "hasLogo": true,
     "companyLogoUrl": "/company/logo/SMCE", "otcAward": {"symbol": "SMCE", "best50": false}, "indexStatuses": [],
     "venue": "OTC Link", "isUnsolicited": false, "ticker": "SMCE", "date": "2020-11-29 15:50:11+00:00"}
