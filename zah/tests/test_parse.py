from __future__ import with_statement

from datetime import datetime

from unittest import TestCase
from parse import ZAHansardParser, ZAHansardSpeech

import itertools
import sys

class ZAHansardParsingTests(TestCase):

    def setUp(self):
        def _hansard_equality(a, b, msg):
            self.assertEqual(type(a), type(b), 'Types must be the same')
            self.assertEqual(a.speaker, b.speaker, 'speaker must be the same')
            self.assertEqual(a.from_, b.from_, 'from_ must be the same')
            self.assertEqual(a.p, b.p, 'p must be the same')

        self.addTypeEqualityFunc(ZAHansardSpeech, _hansard_equality)
    
    def test_basic_parse(self):
        parser = ZAHansardParser()

        filename = 'zah/fixtures/test_inputs/20130522-na-debate-use-air-force-base-waterkloof-gupta-family-matters-public-importance.html'
        with open(filename) as f: html = f.read()

        ret = parser.parse(html)

        self.assertEqual( ret['title'], u'NA: Debate on Use of Air Force Base Waterkloof by GUPTA Family: Matters of Public Importance')
        self.assertEqual( ret['date_string'], u'Date of Meeting:21 May 2013' )
        self.assertEqual( ret['date'], datetime(2013,5,21) )

        expected = (
                 ZAHansardSpeech(
                     speaker = "The CHIEF WHIP OF THE OPPOSITION", 
                     from_ = "The CHIEF WHIP OF THE OPPOSITION", 
                     p = [
                         u' Hon Speaker, at the outset, I wish to convey my sincere gratitude to you for acceding to my request for the debate on this important issue.', 
                         u'This is the first debate of public importance since the year 2000. So, it is chilling to think that in the 19\xa0years of our young democracy, the people of South Africa, who we all collectively represent, were denied such debates for 13\xa0years.', 
                         u'I know the ANC did not want this debate ... [Interjections.] ... and tried to delay it. However, Parliament cannot only debate what the ANC wants to debate, which, as we all know, is consistently dedicated to commemorations, celebrations, congratulations and ceremonies. Those are issues that do not touch the everyday lives of South Africans, while steering clear of the most important things of all, namely, scandals and controversies.', 
                         u'I ask you, Sir, is this the democracy that was envisaged for the new South Africa, where debate is now suppressed rather than encouraged; and where senior politicians use the country ... [Interjections.]'
                    ],
                 ),
                )

        for (got, exp) in zip(ret['speeches'], expected):
            self.assertEqual( got, exp )
