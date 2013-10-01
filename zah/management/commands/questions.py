import scraperwiki
import urllib2
import lxml.etree
import sys
import re, os
import lxml.html  
import json 
import dateutil.parser 
import string 
import parslepy
import json
from lxml import etree
import time

from datetime import datetime, date

from optparse import make_option

from django.conf import settings

from django.core.management.base import BaseCommand, CommandError
from zah.models import Question, Answer
from speeches.importers.import_json import ImportJson

class Command(BaseCommand):

    help = 'Check for new sources'
    option_list = BaseCommand.option_list + (
        make_option('--scrape',
            default=False,
            action='store_true',
            help='Scrape questions',
        ),
    )

    def handle(self, *args, **options):
        if options['scrape']:
            self.scrape_questions(*args, **options)
        else:
            raise CommandError("Please supply a valid option")

    def scrape_questions(self, *args, **options):
        urls = self.getdocs('http://www.parliament.gov.za/live/content.php?Category_ID=236') #get the first page

        print "Processing ",len(urls), " documents"

        count=0
        for url in urls:
            count+=1
            print "Document ", count

            source_url = url['url']
            if url['language']=='English' and url['type']=='pdf':

                if Question.objects.filter( source=source_url ).count():
                    self.stderr.write('Already exists')
                else:
                    self.stderr.write('Going for it!')
                    #try:
                    pages = self.getdocument( source_url )
                    #except Exception as e:
                        #self.stderr.write( str(e) )
                        #pass

            elif url['language']=='English':
                self.stderr.write('%s is not a pdf' % source_url)

            else:
                self.stderr.write('wuh? %s' % str(url) )

    def getdocument(self, url):
        count=0
        pdfdata = urllib2.urlopen(url).read()
        xmldata = scraperwiki.pdftoxml(pdfdata)
        
        #try:
        self.stderr.write("URL %s" % url)
        self.stderr.write("PDF len %d" % len(pdfdata))
        self.stderr.write("XML %s" % xmldata)

        if not xmldata:
            return False

        root = lxml.etree.fromstring(xmldata)
        #except Exception as e:
            #self.stderr.write("OOPS")
            #raise CommandError( '%s failed (%s)' % (url, e))
        self.stderr.write("ok so far...")

        pages = list(root)
        
        inquestion = 0
        intro      = ''
        question   = ''
        number1    = ''
        number2    = ''
        started    = 0
        questiontype = ''
        translated = 0
        document   = ''
        house      = ''
        session    = ''
        date       = ''
        questionto = '' #for multi line question intros
        startintro = False
        startquestion = False
        details1   = False
        details2   = False
        summer     = ''
        questions  = []
        parliament = ''

        pattern  = re.compile("(&#204;){0,1}[0-9]+[.]?[ \t\r\n\v\f]+[-a-zA-z() ]+ to ask [-a-zA-Z]+")
        pattern2 = re.compile("(N|C)(W|O)[0-9]+E")
        pattern3 = re.compile("[0-9]+")
        pattern4 = re.compile("(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday), [0-9]{1,2} (January|February|March|April|May|June|July|August|September|October|November|December) [0-9]{4,4}")
        pattern5 = re.compile("[a-zA-Z]+ SESSION, [a-zA-Z]+ PARLIAMENT")
        pattern6 = re.compile("[0-9]+[.]?[ \t\r\n\v\f]+[-a-zA-z]+ {1,2}([-a-zA-z ]+) \(")
        
        for page in pages:
            for el in list(page): #for el in list(page)[:300]:
                if el.tag == "text":
                    part=re.match('(?s)<text.*?>(.*?)</text>', lxml.etree.tostring(el)).group(1)
                    summer=summer+part.replace('<b>','').replace('</b>','')
                    if not details1 or not details2:
                        
                        if not details1 and pattern5.search(summer): #search for session and parliament numbers

                            session = pattern5.search(summer).group(0).partition(' SESSION')[0]
                            parliament = (
                                    pattern5
                                    .search(summer)
                                    .group(0)
                                    .partition('SESSION, ')[2]
                                    .partition(' PARLIAMENT')[0])
                            details1=True

                        if house=='' and 'NATIONAL ASSEMBLY' in summer:
                            house = 'National Assembly'
                            details2=True

                        if house=='' and 'NATIONAL COUNCIL OF PROVINCES' in summer:
                            house = 'National Council of Provinces'
                            details2 = True

                    if pattern4.search(part):
                        date=pattern4.search(part).group(0)

                    if ('QUESTION PAPER: NATIONAL COUNCIL OF PROVINCES' in part or 
                       'QUESTION PAPER: NATIONAL ASSEMBLY' in part or 
                       pattern4.search(part)):
                        continue

                    if startquestion and not startintro:
                        if pattern.search(summer) or pattern2.search(part):
                            if pattern2.search(part):
                                number2=part.replace('<b>','').replace('</b>','')
                            startquestion=False
                            numbertmp=pattern3.findall(intro)
                            if numbertmp:
                                number1=numbertmp[0]
                            else:
                                number1=''
                            
                            if '&#8224;' in intro:
                                translated=1
                            else:
                                translated=0
                            if '&#204;' in intro:
                                questiontype='oral'
                            else:
                                questiontype='written'
                            intro=intro.replace('&#8224;','')
                            intro=intro.replace('&#204;','')
                            asked=(
                                    intro
                                    .partition(' to ask the ')[2]
                                    .replace(':','')
                                    .replace('.','')
                                    .replace('<i>','')
                                    .replace('</i>','')
                                    .replace('<b>','')
                                    .replace('</b>',''))
                            asked=re.sub(' \[[-a-zA-Z0-9 ]+\]','',asked)
                            askedby=''
                            if pattern6.search(intro):
                                askedby = pattern6.search(intro).group(1)

                            parsed_date = None
                            #try:
                                # Friday, 20 September 2013
                            parsed_date = datetime.strptime(date, '%A, %d %B %Y')
                            #except:
                                #pass
                            
                            data = {
                                    'intro': intro.replace('<b>','').replace('</b>',''), 
                                    'question': question.replace('&#204;',''), 
                                    'number2': number2,
                                    'number1': number1,
                                    'source': url,
                                    'questionto': asked, 
                                    'askedby': askedby,
                                    'date': parsed_date,
                                    'translated': translated,
                                    'session': session,
                                    'parliament': parliament, 
                                    'house': house,
                                    'type': questiontype
                                    }
                            self.stdout.write("Writing object %s\n" % str(data))
                            Question.objects.create( **data )
                            summer=''
                        else:
                            question = question + part
                    if startintro:
                        if "<b>" in part:
                            intro=intro+part.replace('<b>','').replace('</b>','')
                        else:
                            startintro=False
                            question=part

                    if pattern.search(summer):
                        intro = pattern.search(summer).group(0) + summer.partition(pattern.search(summer).group(0))[2]
                        startintro=True
                        startquestion=True
                        summer=''
                    
        self.stdout.write( 'Saved %d\n' % count )
        return True

    def getdocs(self, url):
        urls = []
        print 'start ',url
        page=urllib2.urlopen(url)
        contents = page.read()
        rules = {
                "papers(table.tableOrange_sep tr)" : [{"cell(td)":[{"contents":".","url(a)":"@href"}]}],
                "next(table.tableOrange_sep table table td a)": [{"contents":".","url":"@href"}]
                }
        p = parslepy.Parselet(rules)

        page = p.parse_fromstring(contents)

        for row in page['papers']:
            if len(row['cell'])==11:
                url=row['cell'][8]['url']
                types=url.partition(".")
                urls.append({
                    "name":     row['cell'][0]['contents'],
                    "language": row['cell'][6]['contents'],
                    "url":      'http://www.parliament.gov.za/live/'+url,
                    "house":    row['cell'][4]['contents'],
                    "date":     row['cell'][2]['contents'],
                    "type":     types[2]
                    })

        for cell in page['next']: #check for next page of links
            if cell['contents']=='Next':
                urls += self.getdocs('http://www.parliament.gov.za/live/'+cell['url'])

        return urls

