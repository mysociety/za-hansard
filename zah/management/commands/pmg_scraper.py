import parslepy
import urllib2
import re
import pprint
import csv
import json
from bs4 import BeautifulSoup
import sys
import time
import cookielib
import urllib

from datetime import datetime, date

from optparse import make_option

from django.conf import settings

from django.core.management.base import BaseCommand, CommandError
from zah.models import PMGCommitteeReport, PMGCommitteeAppearance

class Command(BaseCommand):

    help = 'Check for new sources'
    option_list = BaseCommand.option_list + (
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
        make_option('--import-new-to-sayit',
            default=False,
            action='store_true',
            help='Import newly processed documents to ',
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

    def handle(self, *args, **options):

        if options['scrape_with_json']:
            options['scrape'] = True
        if options['import_new_to_sayit']:
            options['save_json'] = True

        if options['scrape']:
            self.scrape(*args, **options)
        elif options['save_json']:
            self.save_json(*args, **options)
        else:
            raise CommandError('Supply either --scrape or --save-json')

    def scrape(self, *args, **options):
        #before anything starts - login so that we can access premium content
        login_rules = {
            "heading": "h1.title",
            "form(#content input)": [{"value":"@value","name":"@name"}],
            }

        page=urllib2.urlopen('http://www.pmg.org.za/user/login')
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
        resp = urllib2.urlopen(req)
        contents = resp.read()

        page=urllib2.urlopen('http://www.pmg.org.za/committees')
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

        self.stdout.write('Started')
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
                self.updateprocess()
                self.committees.append({
                    "name": committee['name'],
                    "url": committee['url'],
                    "type": ctype['type']
                    })
                
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
        self.stdout.write('\rCommittee %d, Checked %d Reports, Processed %d, %d Appearances' 
            % (self.numcommittees, self.reportschecked, self.reportsprocessed, self.appearancesadded))

    def processReport(self, row, url,committeeName,committeeURL,meetingDate): 
        #get the appearances in the report

        meetingDate = datetime.strptime(meetingDate, '%d %b %Y').strftime('%Y-%m-%d').date()

        self.reportsprocessed = self.reportsprocessed + 1
        self.updateprocess()
        report_rules = {
            "heading": "h1.title",
            "chairperson": "div.field-field-chairperson",
            "paragraphs(.field-field-minutes p.MsoNormal)": ["."]
            }
        page=urllib2.urlopen(url)
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

    def processReports(self, url,processingcommitteeName,processingcommitteeURL): 
        #get reports on this page, process them, proceed to next page
        page=urllib2.urlopen(url)
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
                
        if "next" in reports:
            self.processReports(
                'http://www.pmg.org.za'+reports['next'],
                processingcommitteeName,
                processingcommitteeURL)

    def processCommittee(self, url,processingcommitteeName):
        #opens the committee, gets the memberrs, starts retrieving reports
        page=urllib2.urlopen(url)
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
            tosave={
                    'committee_url': '',
                    'committee': '',
                    'meeting': '',
                    'meeting_url': '',
                    'meeting_date': '',
                    'premium':''
                    }

            speeches = []
            for row in report.appearances.all():

                if (tosave['committee_url'] not in ['', row.committee_url] or 
                    tosave['committee'] not in ['', row.committee] or 
                    tosave['meeting'] not in ['', row.meeting] or 
                    tosave['meeting_url'] not in ['', row.meeting_url] or  
                    tosave['meeting_date'] not in ['', row.meeting_date]):

                    self.stderr.write('ERROR: unexpected data')

                # slightly odd logic, we're updating this every time..., will rewrite
                tosave={
                        'committee_url': row.committee_url,
                        'committee': row.committee,
                        'meeting': row.meeting,
                        'meeting_url': row.meeting_url,
                        'meeting_date': row.meeting_date,
                        'premium': report.premium,
                        }

                speech = {
                        'party': row.party,
                        'person': row.person,
                        'text': row.text,
                        }
                speeches.append(speech)

            filename= 'data/%d.json' % row.id
            tosave['speeches'] = speeches

            with open(filename, 'w') as outfile:
                json.dump(tosave, outfile, indent=1, cls=DateEncoder)

class DateEncoder (json.JSONEncoder):

    def default (self, obj):

        if isinstance(obj, date):
            return obj.strftime('%Y-%m-%d')

        return json.JSONEncoder.default(self, obj)
