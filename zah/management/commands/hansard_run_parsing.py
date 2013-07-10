
# This script changed extensively when the Kenyan Parliament website changed after the 2013 Election.
#
# The previous version can be seen at:
#
#    https://github.com/mysociety/mzalendo/blob/7181e30519b140229e3817786e4a7440ac08288d/mzalendo/hansard/management/commands/hansard_check_for_new_sources.py

import pprint
import httplib2
import re
import datetime
import time
import sys

from bs4 import BeautifulSoup
from lxml import etree

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from optparse import make_option

from zah.models import Source
from zah.parse import ZAHansardParser

class FailedToRetrieveSourceException (Exception):
    pass

class Command(BaseCommand):
    help = 'Parse unparsed'
    option_list = BaseCommand.option_list + (
        make_option('--force',
            default=False,
            action='store_true',
            help='Refresh even successfully parsed documents'
        ),
        make_option('--limit',
            default=10,
            type='int',
            help='limit query (default 10)',
        ),
    )

    def handle(self, *args, **options):
        limit = options['limit']

        for s in Source.objects.all().requires_processing()[:limit]:
            if s.language != 'English':
                self.stdout.write("Skipping non-English for now...") # fails date parsing, hehehe
                continue
            s.last_processing_attempt = datetime.datetime.now().date()
            s.save()
            try:
                filename = s.file()
                obj = ZAHansardParser.parse(filename)
                s.xml = etree.tostring(obj.akomaNtoso)
                s.last_processing_success = datetime.datetime.now().date()
                s.save()
                self.stdout.write( "Processed %s (%d)" % (s.document_name, s.document_number) )
            except Exception as e:
                # raise CommandError("Failed to run parsing: %s" % str(e))
                self.stderr.write("WARN: Failed to run parsing: %s" % str(e))
