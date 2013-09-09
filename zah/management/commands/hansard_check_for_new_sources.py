import pprint
import httplib2
import re
import datetime
import time
import sys

from optparse import make_option
from bs4 import BeautifulSoup

from django.conf import settings


from django.core.management.base import BaseCommand, CommandError

from zah.models import Source

class FailedToRetrieveSourceException (Exception):
    pass

class Command(BaseCommand):
    help = 'Check for new sources'
    option_list = BaseCommand.option_list + (
        make_option('--stop-on-seen',
            default=False,
            action='store_true',
            help='Stop when get as far back as first seen item',
        ),
        make_option('--limit',
            default=0,
            type='int',
            help='Limit number of entries checked'),
        )

    def handle(self, *args, **options):
        sources = self.retrieve_sources(0, options)
        sources.reverse()
        sources_db = [Source.objects.get_or_create(**source) for source in sources]
        sources_count = len(sources)
        created_count = sum([1 for (_,created) in sources_db if created])
        self.stdout.write('Sources found: %d\nSources created: %d\n' % (
            sources_count, created_count))

    def retrieve_sources(self, start, options):

        try:
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
            def scrape(node):
                url = node['href']
                table = node.find_parent('table')
                rx = re.compile(r'>([^:<]*) : ([^<]*)<')

                data = {}
                for match in re.finditer(rx, str(table)):
                    groups = match.groups()
                    data[groups[0]] = groups[1]

                title = ''
                try:
                    data['Title'] = table.find('b').text
                except:
                    data['Title'] = data.get('Document Summary', '(unknown)')

                try:
                    document_date = datetime.datetime.strptime(data['Date Published'], '%d %B %Y').date()
                except Exception as e:
                    raise CommandError( "Date could not be parsed\n%s" % str(e) )
                    # document_date = datetime.date.today()

                #(obj, created) = Source.objects.get_or_create(
                return {
                    'document_name':   data['Document Name'],
                    'document_number': data['Document Number'],
                    'defaults': {
                        'url':      url,
                        'title':    data['Title'],
                        'language': data.get('Language', 'English'),
                        'house':    data.get('House', '(unknown)'),
                        'date':     document_date,
                    }
                }
            scraped = []
            for node in nodes:
                s = scrape(node)
                if Source.objects.filter( 
                    document_name   = s['document_name'], 
                    document_number = s['document_number']).exists():
                    if options['stop_on_seen']:
                        return scraped
                else:
                    scraped.append(s)
                    
            if pend < (options['limit'] or ptotal):
                time.sleep(1)
                scraped.append( self.retrieve_sources(pend, options) )
            return scraped

        except Exception as e:
            print >> sys.stderr, "ERROR: %s" % str(e)
            return []
