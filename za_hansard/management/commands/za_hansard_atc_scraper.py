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
from django.core.mail import send_mail

from za_hansard.models import ATCDocument
from ... import atc_scraper

#Largely based on za_hansard_check_for_new_sources.py and za_hansard_run_parsing.py

class FailedToRetrieveSourceException (Exception):
    pass

class Command(BaseCommand):
    help = 'Scrapes ZA Parliament Announcements, Tablings and Committee Reports documents. Currently only monitors for mentions of changes to committee membership.'
    option_list = BaseCommand.option_list + (
        make_option('--check-all',
            default=False,
            action='store_true',
            help="Don't stop when when reaching a previously seen item (applies to checking contents and for new papers)",
        ),
        make_option('--check-all-papers',
            default=False,
            action='store_true',
            help="Don't stop when when reaching a previously seen item (applies only to new papers)",
        ),
        make_option('--retry',
            default=False,
            action='store_true',
            help='Retry attempted (but not completed) parses and previously 404\'d documents',
        ),
        make_option('--check-for-papers',
            default=False,
            action='store_true',
            help='Check for new ATC papers',
        ),
        make_option('--check-committees',
            default=False,
            action='store_true',
            help='Checks for changes to committee membership ',
        ),
        make_option('--historical-limit',
            default='2014-05-07',
            type='str',
            help='Limit earliest historical entry to check (in yyyy-mm-dd format, default 2014-05-07)',
        ),
        make_option('--limit',
            default=0,
            type='str',
            help='Limit number of entries to check (applies to checking contents and for new papers)',
        ),
        make_option('--run-all-steps',
            default=False,
            action='store_true',
            help='Check for new papers and for new committee memberships',
        ),
    )

    def handle(self, *args, **options):

        self.historical_limit = datetime.datetime.strptime(options['historical_limit'], '%Y-%m-%d').date()
        self.limit = options['limit']
        self.check_all = options['check_all']
        self.check_all_papers = options['check_all_papers']
        self.retry = options['retry']

        if options['check_for_papers']:
            self.check_for_papers(options)
        elif options['check_committees']:
            self.check_committees(options)
        elif options['run_all_steps']:
            self.check_for_papers(options)
            self.check_committees(options)

    def check_committees(self, options):
        sources = ATCDocument.objects.all()
        if not self.check_all:
            sources = sources.filter( last_processing_success=None )
        if (not self.retry) and (not self.check_all):
            sources = sources.filter(is404 = False).filter( last_processing_attempt=None )

        if not sources:
            print 'No documents to check.'

        for s in (sources[:self.limit] if self.limit else sources):

            if s.date < self.historical_limit:
                print "Reached historical limit. Stopping.\n"
                return

            s.last_processing_attempt = datetime.datetime.now()
            s.save()

            try:
                try:
                    filename = s.file()
                    if s.is404:
                        s.is404 = False
                        s.save()
                except SourceUrlCouldNotBeRetrieved as e:
                    s.is404 = True
                    s.save()
                    raise e

                if atc_scraper.ATCDocumentParser.check_committee_membership_announcement(filename):
                    self.stdout.write( "Committee announcement found %s (%d)\n" % (s.document_name, s.document_number) )
                    s.contains_committee_announcement = True

                    message = '''A committee announcement was found in the following ATC document:\n
                    \n
                    Document: %s\n
                    Date: %s\n
                    House: %s\n
                    Language: %s\n
                    URL: %s
                    ''' % (s.document_name, s.date, s.house, s.language, 'http://www.parliament.gov.za/live/' + s.url)

                    send_mail('New committee announcement found - People\'s Assembly', message, settings.FROM_EMAIL, settings.ZA_COMMITTEE_NOTIFICATION_EMAIL, fail_silently=False)

                s.last_processing_success = datetime.datetime.now()

                s.save()
                self.stdout.write( "Processed %s (%d)\n" % (s.document_name, s.document_number) )
            except Exception as e:
                # raise CommandError("Failed to run parsing: %s" % str(e))
                self.stderr.write("WARN: Failed to run parsing: %s" % str(e))

    def check_for_papers(self, options):
        sources = self.retrieve_sources(0, options)
        sources.reverse()
        sources_db = [ATCDocument.objects.get_or_create(**source) for source in sources]
        sources_count = len(sources)
        created_count = sum([1 for (_,created) in sources_db if created])
        self.stdout.write('ATC documents found: %d\nATC documents created: %d\n' % (
            sources_count, created_count))

    def retrieve_sources(self, start, options):

        try:
            url = 'http://www.parliament.gov.za/live/content.php?Category_ID=227&DocumentStart=%d' % (start or 0)
            self.stdout.write("Retrieving %s\n" % url)
            h = httplib2.Http( settings.HTTPLIB2_CACHE_DIR )
            response, content = h.request(url)
            assert response.status == 200
            self.stdout.write("OK\n")
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

            self.stdout.write( "Processing %d to %d\n" % (pstart, pend) )

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
                if ATCDocument.objects.filter(
                    document_name   = s['document_name'],
                    document_number = s['document_number']).exists():
                    if (not self.check_all) and (not self.check_all_papers):
                        print "Reached seen document. Stopping.\n"
                        return scraped
                if s['defaults']['date'] < self.historical_limit:
                    print "Reached historical limit. Stopping.\n"
                    return scraped

                # otherwise
                scraped.append(s)

            if pend < (self.limit or ptotal):
                # NB following isn't phrased as a tail call, could rewrite if
                # that becomes important
                scraped = scraped + self.retrieve_sources(pend, options)
            return scraped

        except Exception as e:
            print >> sys.stderr, "ERROR: %s" % str(e)
            return []
