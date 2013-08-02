import pprint
import httplib2
import re
import datetime
import time
import sys

from bs4 import BeautifulSoup

from django.conf import settings


from django.core.management.base import BaseCommand, CommandError

from zah.models import Source

class FailedToRetrieveSourceException (Exception):
    pass

class Command(BaseCommand):
    args = '<start end>'
    help = 'Check for new sources'


    def handle(self, *args, **options):
        (start, end) = [int(x) for x in args]
        self.retrieve_sources(start, end)

    def retrieve_sources(self, start, end):

        url = 'http://www.parliament.gov.za/live/content.php?Category_ID=119&DocumentStart=%d' % (start or 0)
        self.stdout.write("Retrieving %s" % url)
        h = httplib2.Http( settings.HTTPLIB2_CACHE_DIR )
        response, content = h.request(url)
        assert response.status == 200
        self.stdout.write("OK")
        # content = open('test.html').read()

        # parse content
        soup = BeautifulSoup(
            content,
            'xml',
        )

        rx = re.compile(r'Displaying (\d+)  (\d+) of the most recent (\d+)')

        pager = soup.find('td', text=rx)
        match = rx.search(pager.text)
        (pstart, pend, ptotal) = [int(p) for p in match.groups()]

        self.stdout.write( "Processing %d to %d" % (pstart, pend) )

        nodes = soup.findAll( 'a', text="View Document" )
        for node in nodes:
            url = node['href']
            table = node.find_parent('table')
            rx = re.compile(r'>([^:<]*) : ([^<]*)<')
            data = { 'Title': table.find('b').text }
            for match in re.finditer(rx, str(table)):
                groups = match.groups()
                data[groups[0]] = groups[1]

            try:
                document_date = datetime.datetime.strptime(data['Date Published'], '%d %B %Y').date()
            except Exception as e:
                raise CommandError( "Date could not be parsed\n%s" % str(e) )
                # document_date = datetime.date.today()

            (obj, created) = Source.objects.get_or_create(
                document_name = data['Document Name'],
                document_number = data['Document Number'],
                defaults = {
                    'url': url,
                    'title':    data.get('Title', '(unknown)'),
                    'language': data.get('Language', 'English'),
                    'house':    data.get('House', '(unknown)'),
                    'date':     document_date,
                }
            )

        end = end or ptotal

        if pend < end:
            time.sleep(1)
            self.retrieve_sources(pend, end)
