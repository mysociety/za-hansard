from __future__ import with_statement

from datetime import datetime

from unittest import TestCase
from parse_doc import ZAHansardParser2
from lxml import etree

import itertools
import sys

class ZAHansardParsingTests(TestCase):

    def test_basic_parse(self):
        parser = ZAHansardParser2()

        filename = 'zah/fixtures/test_inputs/502914_1.doc'
        document = parser.parse(filename)

        print >> sys.stderr, etree.tostring(document, pretty_print=True)
