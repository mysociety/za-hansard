from __future__ import with_statement

from datetime import datetime

from unittest import TestCase
from parse import ZAHansardParser
from lxml import etree

import itertools
import sys

class ZAHansardParsingTests(TestCase):

    def test_basic_parse(self):

        filename = 'zah/fixtures/test_inputs/502914_1.doc'
        obj = ZAHansardParser.parse(filename)
        document = obj.akomaNtoso

        print >> sys.stderr, etree.tostring(document, pretty_print=True)
