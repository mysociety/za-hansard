from __future__ import with_statement

from datetime import datetime

from unittest import TestCase
from parse import ZAHansardParser
from lxml import etree

import itertools
import sys

class ZAHansardParsingTests(TestCase):

    def test_basic_parse(self):
        parser = ZAHansardParser()

        filename = 'zah/fixtures/test_inputs/502914_1.doc'
        document = parser.parse(filename)

        print >> sys.stderr, etree.tostring(document, pretty_print=True)
