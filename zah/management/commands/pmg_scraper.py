import parslepy
import urllib2
import re
import pprint
import csv
import json
from bs4 import BeautifulSoup
import sys
import sqlite3
import time
import cookielib
import urllib

from optparse import make_option

from django.conf import settings

from django.core.management.base import BaseCommand, CommandError

class Command(BaseCommand):

    committees = []
    allmembers = []
    allreports = []
    allappearances = []
    numcommittees=0
    reportschecked=0
    reportsprocessed=0
    appearancesadded=0
    c = None
    name_re = "(Mr|Mrs|Ms|Miss|Dr|Prof|Professor|Prince|Princess) ([- a-zA-Z]{1,50}) \(([-A-Z]+)([;,][- A-Za-z]+)?\)"

    help = 'Check for new sources'
    option_list = BaseCommand.option_list + (
        make_option('--foo',
            default=False,
            action='store_true',
            help='etc.',
        ),
    )

    def handle(self, *args, **options):

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
        print >> sys.stderr, str(data)
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

        print 'Started'
        for ctype in parsedcommittees['committee_types']: 
            for committee in ctype['committees']:
                self.numcommittees = self.numcommittees + 1
                
                conn = sqlite3.connect('pmg.sqlite')
                self.c = conn.cursor()
                
                try:
                    self.processCommittee(
                        'http://www.pmg.org.za'+committee['url'].replace(' ','%20'),
                        committee['name'])
                except urllib2.HTTPError: 
                    #if there is an http error, just ignore this committee this time
                    print 'HTTPERROR '+committee['name']
                    pass
                self.updateprocess()
                self.committees.append({
                    "name": committee['name'],
                    "url": committee['url'],
                    "type": ctype['type']
                    })
                
                conn.commit()
                conn.close()
                #break
            #break

        with open('committees_json.json', 'w') as outfile:
          json.dump(self.committees,outfile)
          
        with open('members_json.json', 'w') as outfile:
          json.dump(self.allmembers,outfile)

        with open('reports_json.json', 'w') as outfile:
          json.dump(self.allreports,outfile)
          
        with open('appearances_json.json', 'w') as outfile:
          json.dump(self.allappearances,outfile)

    def updateprocess(self):
        print ('\rCommittee %d, Checked %d Reports, Processed %d, %d Appearances' 
            % (self.numcommittees, self.reportschecked, self.reportsprocessed, self.appearancesadded))
        #sys.stdout.flush()

    def processReport(self, url,committeeName,committeeURL,meetingDate): 
        #get the appearances in the report
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
        totalappearances=0
        
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
            
        t = (url,)
        self.c.execute('DELETE FROM appearances WHERE meeting_url=?', t)
        
        if 'chairperson' not in report:
            report['chairperson']=""
        
        chairs=re.findall(self.name_re, report['chairperson'])
        
        findchair=False
        
        if len(chairs)>1:
            for chair in chairs:
                save={
                    'meetingdate': meetingDate,
                    'committeeurl': committeeURL,
                    'committeename': committeeName,
                    'report': report['heading'],
                    'party': chair[2],
                    'personname': chair[1],
                    'reporturl': url,
                    'text': re.sub('<[^>]*>', '', 
                        '%s %s (%s) chaired the meeting.' % (
                            chair[0], chair[1], chair[2]))
                    }
                t = (
                    None, 
                    save['meetingdate'], 
                    save['committeeurl'],
                    save['committeename'],
                    save['report'],
                    save['party'],
                    save['personname'],
                    save['reporturl'],
                    save['text'],
                    )
                self.c.execute(
                    'INSERT INTO appearances VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)', t)

                self.appearancesadded = self.appearancesadded + 1

                self.allappearances.append(save)
                self.totalappearances=self.totalappearances + 1
                
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
                    
                    t = (name, url)
                    self.c.execute(
                        "SELECT * FROM appearances WHERE person=? and meeting_url=?",
                        t)
                    check=self.c.fetchone()
                    if check:
                        break
                    save={
                        'meetingdate': meetingDate,
                        'committeeurl': committeeURL,
                        'committeename': committeeName,
                        'report': report['heading'],
                        'party': party,
                        'personname': name,
                        'reporturl': url,
                        'text': re.sub('<[^>]*>', '', paragraph)
                            .replace("Discussion\n",'')
                            .replace("Apologies\n",'')
                            .replace("Minutes:\n",'')
                            .replace("\n",''),
                         }
                    
                    t = (
                        None, 
                        save['meetingdate'], 
                        save['committeeurl'],
                        save['committeename'],
                        save['report'],
                        save['party'],
                        save['personname'],
                        save['reporturl'],
                        save['text'],
                        )
                    self.c.execute(
                        'INSERT INTO appearances VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
                        t)

                    self.appearancesadded = appearancesadded + 1

                    self.allappearances.append(save)
                    self.totalappearances = self.totalappearances + 1
            
            if findchair:
                if "The Chairperson" in paragraph:
                    findchair=False
                    save={
                        'meetingdate': meetingDate,
                        'committeeurl': committeeURL, 
                        'committeename': committeeName, 
                        'report': report['heading'],
                        'party': chairs[0][2],
                        'personname': chairs[0][1],
                        'reporturl': url,
                        'text': re.sub('<[^>]*>', '', paragraph)
                            .replace("Apologies\n",'')
                            .replace("Minutes:\n",'')
                            .replace("\n",' '),
                        }
                    t = (
                        None, 
                        save['meetingdate'], 
                        save['committeeurl'],
                        save['committeename'],
                        save['report'],
                        save['party'],
                        save['personname'],
                        save['reporturl'],
                        save['text'],
                        )
                    self.c.execute('INSERT INTO appearances VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',t)
                    self.appearancesadded = self.appearancesadded + 1
                    self.allappearances.append(save)
                    self.totalappearances = self.totalappearances + 1
                
        t = (1,url,)
        if totalappearances>0:
            self.c.execute("UPDATE reports SET processed=? WHERE meeting_url=?",t)
        

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
                #print report['date']
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
                        t = ('http://www.pmg.org.za'+report['url'],)
                        self.c.execute(
                            "SELECT processed FROM reports WHERE meeting_url=?", t)
                        row=self.c.fetchone()
                        if not row:
                            if not 'image' in report:
                                report['image']=''
                            if 'tick.png' in report['image']:
                                ispremium=0
                            else:
                                ispremium=1
                            t = (
                                ispremium,
                                # None,
                                0,
                                'http://www.pmg.org.za'+report['url']
                                )
                            self.c.execute(
                                "INSERT INTO reports (premium, processed, meeting_url) VALUES (?,?, ?)", t)
                            self.processReport(
                                'http://www.pmg.org.za'+report['url'],
                                processingcommitteeName,
                                processingcommitteeURL,
                                report['date'])
                        elif row[0] is 0:
                            self.processReport(
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
