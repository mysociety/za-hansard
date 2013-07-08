
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

from django.conf import settings


from django.core.management.base import BaseCommand, CommandError

from zah.models import Source

class FailedToRetrieveSourceException (Exception):
    pass

class Command(BaseCommand):
    args = '<start end>'
    help = 'Check for new sources'

    # http://www.parliament.go.ke
    # /plone/national-assembly/business/hansard/copy_of_official-report-28-march-2013-pm/at_multi_download/item_files
    # ?name=Hansard%20National%20Assembly%2028.03.2013P.pdf


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


    def __FOR_LATER__():
        # I don't trust that we can accurately create the download link url with the
        # details that we have. Instead fetche the page and extract the url.
        download_response, download_content = h.request(href)
        download_soup = BeautifulSoup(
            download_content,
            'xml',
        )
        download_url = download_soup.find( id="archetypes-fieldname-item_files" ).a['href']
        
        # create/update the source entry
