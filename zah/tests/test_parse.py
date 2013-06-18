from __future__ import with_statement

from datetime import datetime

from unittest import TestCase
from parse import ZAHansardParser

class ZAHansardParsingTests(TestCase):

    def test_basic_parse(self):
        parser = ZAHansardParser()

        filename = 'zah/fixtures/test_inputs/20130522-na-debate-use-air-force-base-waterkloof-gupta-family-matters-public-importance.html'
        with open(filename) as f: html = f.read()

        ret = parser.parse(html)

        self.assertEqual( ret['title'], u'NA: Debate on Use of Air Force Base Waterkloof by GUPTA Family: Matters of Public Importance')
        self.assertEqual( ret['date_string'], u'Date of Meeting:21 May 2013' )
        self.assertEqual( ret['date'], datetime(2013,5,21) )


