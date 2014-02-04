import parslepy
import urllib2
import httplib
import re
import pprint
import csv
import json
from za_hansard.datejson import DateEncoder
from bs4 import BeautifulSoup
import sys, os
import time
import cookielib
import urllib

from datetime import datetime, date

from optparse import make_option

from django.conf import settings

from django.core.management.base import BaseCommand, CommandError
from instances.models import Instance
from za_hansard.models import PMGCommitteeReport, PMGCommitteeAppearance
from speeches.importers.import_json import ImportJson

class StopFetchingException (Exception):
    # this is a control flow exception.
    pass

class Command(BaseCommand):

    help = 'Check for new sources'
    option_list = BaseCommand.option_list + (
        make_option('--instance',
            type='str',
            default='default',
            help='Instance to import into',
        ),
        make_option('--scrape',
            default=False,
            action='store_true',
            help='Scrape committee minutes',
        ),
        make_option('--scrape-with-json',
            default=False,
            action='store_true',
            help='Write JSON summaries (implies --scrape)',
        ),
        make_option('--save-json',
            default=False,
            action='store_true',
            help='Save JSON from already scraped ',
        ),
        make_option('--import-to-sayit',
            default=False,
            action='store_true',
            help='Import documents to sayit',
        ),
        make_option('--delete-existing',
            default=False,
            action='store_true',
            help='delete existing records (assuming --import-to-sayit)',
        ),
        make_option('--retries',
            type='int',
            default=3,
            help='Number of retries to make each http request (default 3)'
        make_option('--limit',
            default=0,
            action='store',
            type='int',
            help='How far to go back (default not set means all the way)',
            # note, this uses 'reportschecked'
        ),
        make_option('--fetch-to-limit',
            default=False,
            action='store_true',
            help="Don't stop when reaching seen questions, continue to --limit",
        ),
    )

    committees = []
    allmembers = []
    allreports = []
    allappearances = []
    numcommittees=0
    reportschecked=0
    reportsprocessed=0
    appearancesadded=0
    totalappearances=0 # seems to be reset later, not really a good global
    name_re = "(Mr|Mrs|Ms|Miss|Dr|Prof|Professor|Prince|Princess) ([- a-zA-Z]{1,50}) \(([-A-Z]+)([;,][- A-Za-z]+)?\)"
    instance = None
    limit = 0
    fetch_to_limit = False

    def handle(self, *args, **options):

        try:
            self.instance = Instance.objects.get(label=options['instance'])
        except Instance.DoesNotExist:
            raise CommandError("Instance specified not found (%s)" % options['instance'])

        self.retries = options['retries']

        self.limit          = options['limit']
        self.fetch_to_limit = options['fetch_to_limit']

        if options['scrape_with_json']:
            options['scrape'] = True

        if not len([ i for i in ['scrape', 'save_json', 'import_to_sayit'] if i]):
            raise CommandError('Supply --scrape, --save-json, or --import-to-sayit')

        if options['scrape']:
            self.scrape(*args, **options)

        if options['save_json']:
            self.save_json(*args, **options)

        if options['import_to_sayit']:
            self.import_to_sayit(*args, **options)

    def scrape(self, *args, **options):
        #before anything starts - login so that we can access premium content
        login_rules = {
            "heading": "h1.title",
            "form(#content input)": [{"value":"@value","name":"@name"}],
            }

        page=self.open_url_with_retries('http://www.pmg.org.za/user/login')
        contents = page.read()
        p = parslepy.Parselet(login_rules)
        login_data = p.parse_fromstring(contents)
        for attr in login_data['form']:
            if attr['name']=='form_build_id':
                form_build_id=attr['value']
            if attr['name']=='form_id':
                form_id=attr['value']
        cj = cookielib.CookieJar()
        opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cj))
        urllib2.install_opener(opener)
        data = {
            'form_id': form_id,
            'form_build_id': form_build_id,
            'name': settings.PMG_COMMITTEE_USER,
            'pass': settings.PMG_COMMITTEE_PASS,
            }
        encodedata = urllib.urlencode(data)
        req = urllib2.Request('http://www.pmg.org.za/user/login', encodedata)
        resp = self.open_url_with_retries(req)
        contents = resp.read()

        page=self.open_url_with_retries('http://www.pmg.org.za/committees')
        contents = page.read()

        committees_rules = {
            "heading": "h1.title",
            "committee_types(div.view-committees-all-list div.item-list)":
                [{
                "type":"h3",
                "committees(li.views-row a)":
                    [{
                    'name': '.',
                    'url': 'a @href',
                    }]
                }]
            }
        p = parslepy.Parselet(committees_rules)
        parsedcommittees = p.parse_fromstring(contents)

        self.stdout.write('Started\n')
        try:
            for ctype in parsedcommittees['committee_types']:
                for committee in ctype['committees']:
                    self.numcommittees = self.numcommittees + 1

                    try:
                        self.processCommittee(
                            'http://www.pmg.org.za'+committee['url'].replace(' ','%20'),
                            committee['name'])
                    except urllib2.HTTPError:
                        #if there is an http error, just ignore this committee this time
                        self.stderr.write('HTTPERROR '+committee['name'])
                        pass
                    finally:    
                        self.updateprocess()
                        self.committees.append({
                            "name": committee['name'],
                            "url": committee['url'],
                            "type": ctype['type']
                            })
        except StopFetchingException as e:
            self.stderr.write("STOPPED! %s\n" % e)

        if options['scrape_with_json']:
            with open('committees_json.json', 'w') as outfile:
              json.dump(self.committees, outfile)

            with open('members_json.json', 'w') as outfile:
              json.dump(self.allmembers, outfile)

            with open('reports_json.json', 'w') as outfile:
              json.dump(self.allreports, outfile)

            with open('appearances_json.json', 'w') as outfile:
              json.dump(self.allappearances, outfile)

    def updateprocess(self):
        self.stdout.write('Committee %d, Checked %d Reports, Processed %d, %d Appearances\n'
            % (self.numcommittees, self.reportschecked, self.reportsprocessed, self.appearancesadded))

    def open_url_with_retries(self, url):
        for i in range(0, self.retries):
            try:
                page=urllib2.urlopen(url)
                return page
            except Exception as e:
                print >> sys.stderr, "attempt %d: Exception caught '%s'" % (i, str(e))
                time.sleep(1)

        # we didn't ever return, so
        raise Exception("Cannot connect to server for url '%s' and max retries exceeded" % url)

    def processReport(self, row, url,committeeName,committeeURL,meetingDate):
        #get the appearances in the report

        meetingDate = datetime.strptime(meetingDate, '%d %b %Y')

        self.reportsprocessed = self.reportsprocessed + 1
        self.updateprocess()
        report_rules = {
            "heading": "h1.title",
            "chairperson": "div.field-field-chairperson",
            "paragraphs(.field-field-minutes p.MsoNormal)": ["."]
            }
        page=self.open_url_with_retries(url)
        contents = page.read()
        p = parslepy.Parselet(report_rules)
        report = p.parse_fromstring(contents)
        self.totalappearances=0

        soup = BeautifulSoup(contents)
        #use BeautifulSoup due to issues with <br/> divisions when using Parslepy
        text=(
            unicode(soup.find('div',class_='field-field-minutes'))
            .replace('<br/>','')
            .replace('<div>','')
            .replace('</div>','')
            .replace('<p>','')
            .replace('</p>','')
            .replace('\t','')
            .replace('<b><i>Discussion</i></b>',''))
        paragraphs = text.split("\n")

        if len(paragraphs)<3 and len(report['paragraphs'])>1:
            paragraphs = report['paragraphs']

        PMGCommitteeAppearance.objects.filter(report = row).delete()

        if 'chairperson' not in report:
            report['chairperson']=""

        chairs=re.findall(self.name_re, report['chairperson'])

        findchair=False

        if len(chairs)>1:
            for chair in chairs:
                save={
                    'report': row,
                    'meeting_date': meetingDate,
                    'committee_url': committeeURL,
                    'committee': committeeName,
                    'meeting': report['heading'],
                    'party':  chair[2],
                    'person': chair[1],
                    'meeting_url': url,
                    'text': re.sub('<[^>]*>', '',
                        '%s %s (%s) chaired the meeting.' % (
                            chair[0], chair[1], chair[2]))
                    }
                PMGCommitteeAppearance.objects.create(**save)

                self.appearancesadded = self.appearancesadded + 1

                self.allappearances.append(save)
                self.totalappearances = self.totalappearances + 1

        if len(chairs) is 1:
            findchair=True

        for paragraph in paragraphs:

            if (re.match('^(Apologies:)',paragraph) or
                'The Chairperson noted the apologies of' in paragraph):
                continue
            find = re.findall(self.name_re, paragraph)
            if find and len(find)>0:
                for found in find:
                    name=found[1]
                    party=found[2]

                    save={
                        'report': row,
                        'meeting_date': meetingDate,
                        'committee_url': committeeURL,
                        'committee': committeeName,
                        'meeting': report['heading'],
                        'party': party,
                        'person': name,
                        'meeting_url': url,
                        'text': re.sub('<[^>]*>', '', paragraph)
                            .replace("Discussion\n",'')
                            .replace("Apologies\n",'')
                            .replace("Minutes:\n",'')
                            .replace("\n",''),
                         }

                    (obj, created) = PMGCommitteeAppearance.objects.get_or_create(
                        person = name,
                        meeting_url = url,
                        defaults = save,
                        )

                    if created:
                        self.appearancesadded = self.appearancesadded + 1

                        self.allappearances.append(save)
                        self.totalappearances = self.totalappearances + 1

            if findchair:
                if "The Chairperson" in paragraph:
                    findchair=False

                    save={
                        'report': row,
                        'meeting_date': meetingDate,
                        'committee_url': committeeURL,
                        'committee': committeeName,
                        'meeting': report['heading'],
                        'party': chairs[0][2],
                        'person': chairs[0][1],
                        'meeting_url': url,
                        'text': re.sub('<[^>]*>', '', paragraph)
                            .replace("Apologies\n",'')
                            .replace("Minutes:\n",'')
                            .replace("\n",' '),
                        }

                    obj = PMGCommitteeAppearance.objects.create(**save)
                    self.appearancesadded = self.appearancesadded + 1
                    self.allappearances.append(save)
                    self.totalappearances = self.totalappearances + 1

        if self.totalappearances > 0:
            PMGCommitteeReport.objects.filter(meeting_url = url).update( processed = True)

        # finally sleep, to minimize load on PMG servers
        time.sleep(1)

    def processReports(self, url,processingcommitteeName,processingcommitteeURL):
        #get reports on this page, process them, proceed to next page

        page=self.open_url_with_retries(url)
        contents = page.read()

        reports_rules = {
            "heading":"h1.title",
            "reports(div.view-reports-by-committee table tr)": [{
                "date": "td.views-field-field-meeting-date-value",
                "meeting": "td.views-field-title",
                "url": "a @href",
                "image": "td.views-field-phpcode img @src"
                }],
            "next": "li.pager-next a @href"
        }
        p = parslepy.Parselet(reports_rules)
        reports = p.parse_fromstring(contents)

        for report in reports['reports']:

            if self.limit and (self.reportschecked > self.limit):
                raise StopFetchingException("Reached Limit")

            self.updateprocess()
            if "date" in report:
                self.reportschecked = self.reportschecked + 1
                if report['date'] != '' and report['date'] != '':
                    if (len(report)>0 and "date" in report
                        and "meeting" in report and "url" in report
                        and time.strptime(report['date'],'%d %b %Y')
                            > time.strptime('22 Apr 2009','%d %b %Y')):
                        self.allreports.append({
                            "date": report['date'],
                            "meeting": report['meeting'],
                            "url": report['url'],
                            "committee": processingcommitteeName})

                        meeting_url = 'http://www.pmg.org.za'+report['url']
                        try:
                            row = PMGCommitteeReport.objects.filter(
                                meeting_url = meeting_url)[0]
                        except IndexError:
                            row = None

                        if not row:

                            if not 'image' in report:
                                report['image']=''

                            if 'tick.png' in report['image']:
                                ispremium=0
                            else:
                                ispremium=1

                            row = PMGCommitteeReport.objects.create(
                                premium = ispremium,
                                processed = False,
                                meeting_url = meeting_url)

                            self.processReport(
                                row,
                                'http://www.pmg.org.za'+report['url'],
                                processingcommitteeName,
                                processingcommitteeURL,
                                report['date'])

                        elif not row.processed:

                            self.processReport(
                                row,
                                'http://www.pmg.org.za'+report['url'],
                                processingcommitteeName,
                                processingcommitteeURL,
                                report['date'])

                        elif not self.fetch_to_limit:
                            raise StopFetchingException("Reached previously seen report")

        if "next" in reports:

            self.processReports(
                'http://www.pmg.org.za'+reports['next'],
                processingcommitteeName,
                processingcommitteeURL)

    def processCommittee(self, url,processingcommitteeName):
        #opens the committee, gets the memberrs, starts retrieving reports
        page=self.open_url_with_retries(url)
        contents = page.read()

        members_rules = {
            "heading": "h1.title",
            "chairperson": "div.pane-views-panes div.view-id-committee_members div.views-field-title",
            "members(table.views-view-grid.col-4 div.views-field-title )":
                [{"name": ".",}],
        }
        p = parslepy.Parselet(members_rules)
        members = p.parse_fromstring(contents)

        for member in members['members']:
            if ' (ALT)' in member['name']:
                member['alternative']=True
                member['name']=member['name'].replace(' (ALT)','')
            else:
                member['alternative']=False
            if re.search(" \(([A-Z+]+)\)",member['name']):
                member['party']=re.search(" \(([A-Z+]+)\)",member['name']).group(1)
            else:
                member['party']=''

            member['name']=re.sub(" \(([A-Z+]+)\)","",member['name'])

            if members['chairperson'] in member['name']:
                member['isChairperson']=True
            else:
                member['isChairperson']=False

            member['committee']=processingcommitteeName
            self.allmembers.append(member)

        self.processReports( url, processingcommitteeName, url )

    def save_json(self, *args, **options):

        reports = PMGCommitteeReport.objects.all()

        for report in reports:

            appearances = report.appearances.all()

            if not len(appearances):
                continue

            first_appearance = appearances[0]

            speeches = []
            for row in appearances:
                speeches.append({
                        'party': row.party,
                        'personname': row.person,
                        'text': row.text,
                        'tags': ['committee']
                        })
            tosave={
                    # TODO, really these fields belong to report, not to first appearance row
                    'committee_url': first_appearance.committee_url,
                    'organization':  first_appearance.committee,
                    'title':         first_appearance.meeting,
                    'report_url':    first_appearance.meeting_url,
                    'date':          first_appearance.meeting_date,
                    'public':        bool(not report.premium),
                    'speeches':      speeches,
                    'parent_section_titles': [
                        'Committee Minutes',
                        first_appearance.committee,
                        first_appearance.meeting_date.strftime('%d %B %Y')
                        ]}


            filename = os.path.join(settings.COMMITTEE_CACHE, '%d.json' % report.id)
            with open(filename, 'w') as outfile:
                json.dump(tosave, outfile, indent=1, cls=DateEncoder)

    def import_to_sayit(self, *args, **options):

        sections = []
        sources = PMGCommitteeReport.objects
        if not options['delete_existing']:
            sources = sources.filter(sayit_section = None)

        sources_all = sources.all()

        for row in sources_all:
            filename = os.path.join(settings.COMMITTEE_CACHE, '%d.json' % row.id)
            if not os.path.exists(filename):
                continue

            importer = ImportJson( instance=self.instance, delete_existing = options['delete_existing'],
                popit_url='http://za-peoples-assembly.popit.mysociety.org/api/v0.1/')
            try:
                self.stdout.write("TRYING %d (%s)\n" % (row.id, filename))
                section = importer.import_document(filename)

                row.sayit_section = section
                row.last_sayit_import = datetime.now().date()
                row.save()

                sections.append(section)

            except Exception as e:
                self.stderr.write('WARN: failed to import %d: %s' %
                    (row.id, str(e)))

        self.stdout.write( str( [s.id for s in sections] ) )
        self.stdout.write( '\n' )

        self.stdout.write('Imported %d / %d sections\n' %
            (len(sections), len(sources_all)))
