import distutils.spawn
import os
import re
import requests
import subprocess
import tempfile
import warnings
import datetime
import lxml.etree

import parslepy

from django.core.exceptions import ImproperlyConfigured

from za_hansard.models import Question

# from https://github.com/scraperwiki/scraperwiki-python/blob/a96582f6c20cc1897f410d522e2a5bf37d301220/scraperwiki/utils.py#L38-L54
# Copied rather than included as the scraperwiki __init__.py was having trouble
# loading the sqlite code, which is something we don't actually need.

def ensure_executable_found(name):
    if not distutils.spawn.find_executable(name):
        raise ImproperlyConfigured("Can't find executable '{0}' which is needed by this code".format(name))

ensure_executable_found("pdftohtml")
def pdftoxml(pdfdata):
    """converts pdf file to xml file"""
    pdffout = tempfile.NamedTemporaryFile(suffix='.pdf')
    pdffout.write(pdfdata)
    pdffout.flush()

    xmlin = tempfile.NamedTemporaryFile(mode='r', suffix='.xml')
    tmpxml = xmlin.name # "temph.xml"
    cmd = 'pdftohtml -xml -nodrm -zoom 1.5 -enc UTF-8 -noframes "%s" "%s"' % (pdffout.name, os.path.splitext(tmpxml)[0])
    cmd = cmd + " >/dev/null 2>&1" # can't turn off output, so throw away even stderr yeuch
    os.system(cmd)

    pdffout.close()
    #xmlfin = open(tmpxml)
    xmldata = xmlin.read()
    xmlin.close()
    return xmldata



ensure_executable_found("antiword")
def extract_answer_text_from_word_document(filename):
    text = check_output_wrapper(['antiword', filename]).decode('unicode-escape')

    # strip out lines that are just '________'
    bar_regex = re.compile(r'^_+$', re.MULTILINE)
    text = bar_regex.sub('', text)

    return text

def check_output_wrapper(*args, **kwargs):

    # Python 2.7
    if hasattr(subprocess, 'check_output'):
        return subprocess.check_output(*args)

    # Backport to 2.6 from https://gist.github.com/edufelipe/1027906
    else:
        process = subprocess.Popen(stdout=subprocess.PIPE, *args, **kwargs)
        output, unused_err = process.communicate()
        retcode = process.poll()
        if retcode:
            cmd = kwargs.get('args', args[0])
            error = subprocess.CalledProcessError(retcode, cmd)
            error.output = output
            raise error
        return output

class BaseDetailIterator(object):
    
    base_url = 'http://www.parliament.gov.za/live/'

    def __init__(self, start_list_url):

        self.details = []  # Question URLs that we have collected from tha list
        self.next_list_url = start_list_url  # The next list page to fetch urls from

    def __iter__(self):
        return self

    def next(self):
    
        # If needed and possible try to fetch more urls from the next list page
        while len(self.details) == 0 and self.next_list_url:
            self.get_details()
    
        # Return a url if we can.
        if len(self.details):
            return self.details.pop(0)
        else:
            raise StopIteration

    def url_get(self, url):
        """Super simple method to retrieve url and return content. Intended to be easily mocked in tests"""
        response = requests.get( url )
        return response.text


class QuestionDetailIterator(BaseDetailIterator):

    question_parsing_rules = {
        "papers(table.tableOrange_sep tr)":
            [{"cell(td)":[{"contents":".","url(a)":"@href"}]}],
        "next(table.tableOrange_sep table table td a)":
            [{"contents":".","url":"@href"}]
    }

    def get_details(self):

        print 'Questions (%s)\n' % self.next_list_url

        contents = self.url_get( self.next_list_url )

        p = parslepy.Parselet(self.question_parsing_rules)
        page = p.parse_fromstring(contents)


        for row in page['papers']:
            if len(row['cell'])==11:
                url = row['cell'][8]['url']
                types = url.partition(".")
                self.details.append({
                    "name":     row['cell'][0]['contents'],
                    "language": row['cell'][6]['contents'],
                    "url":      self.base_url + url,
                    "house":    row['cell'][4]['contents'],
                    "date":     row['cell'][2]['contents'],
                    "type":     types[2]
                    })

        # check for next page of links (or None if not found)
        self.next_list_url = None
        for cell in page['next']:
            if cell['contents']=='Next':
                next_url = self.base_url + cell['url']
                if self.next_list_url == next_url:
                    raise Exception("Possible url loop detected, next url '{0}' has not changed.".format(next_url))
                self.next_list_url = next_url
                break

        return True



class AnswerDetailIterator(BaseDetailIterator):

    answer_parsing_rules = {
        "papers(table.tableOrange_sep tr)" : [{"cell(td)":[{"contents":".","url(a)":"@href"}]}],
        "next(table.tableOrange_sep table table td a)": [{"contents":".","url":"@href"}]
    }

    def get_details(self):

        print 'Answers (%s)\n' % self.next_list_url
        
        contents = self.url_get( self.next_list_url )
        
        p = parslepy.Parselet(self.answer_parsing_rules)
        page = p.parse_fromstring(contents)
        
        for row in page['papers']:
            if len(row['cell']) == 11:
                url=row['cell'][8]['url']
                types=url.partition(".")
                number_oral=''
                number_written=''
                #check for written/oral question numbers
                # (using apparent convention - a question can have one of each number)
                if re.match('[A-Za-z0-9]+[oO]([0-9]+)[ wW-]',row['cell'][0]['contents']):
                    number_oral=re.match(
                        '[A-Za-z0-9]+[oO]([0-9]+)[ wW-]',row['cell'][0]['contents']).group(1)
                if re.match('[A-Za-z0-9]+[wW]([0-9]+)[ oO-]',row['cell'][0]['contents']):
                    number_written=re.match(
                        '[A-Za-z0-9]+[wW]([0-9]+)[ oO-]',row['cell'][0]['contents']).group(1)
            
                date = row['cell'][2]['contents']
                parsed_date = None
                try:
                    parsed_date = datetime.datetime.strptime(date, '%d %B %Y')
                except:
                    warnings.warn("Failed to parse date (%s)" % date)
                    continue

                self.details.append(dict(
                    number_oral = number_oral,
                    name        = row['cell'][0]['contents'],
                    language    = row['cell'][6]['contents'],
                    url         = 'http://www.parliament.gov.za/live/'+url,
                    house       = row['cell'][4]['contents'],
                    number_written = number_written,
                    date        = parsed_date,
                    type        = types[2]                
                ))
        
        # check for next page of links (or None if not found)
        self.next_list_url = None
        for cell in page['next']:
            if cell['contents']=='Next':
                next_url = self.base_url + cell['url']
                if self.next_list_url == next_url:
                    raise Exception("Possible url loop detected, next url '{0}' has not changed.".format(next_url))
                self.next_list_url = next_url
                break

class QuestionPaperParser(object):
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def get_questions(self):
        url = self.kwargs['url']

        pdfdata = self.get_question_pdf_from_url(url)
        xmldata = self.get_question_xml_from_pdf(pdfdata)

        if not xmldata:
            return False

        #self.stderr.write("URL %s\n" % url)
        #self.stderr.write("PDF len %d\n" % len(pdfdata))
        #self.stderr.write("XML %s\n" % xmldata)

        return self.create_questions_from_xml(xmldata, url)


    def get_question_pdf_from_url(self, url):
        return urllib2.urlopen(url).read()


    def get_question_xml_from_pdf(self, pdfdata):
        return pdftoxml(pdfdata)


    def create_questions_from_xml(self, xmldata, url):
        count=0

        root = lxml.etree.fromstring(xmldata)
        #except Exception as e:
            #self.stderr.write("OOPS")
            #raise CommandError( '%s failed (%s)' % (url, e))
        # self.stderr.write("XML parsed...\n")

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
                            asked=re.sub(r'\[.*$','',asked)
                            askedby=''
                            if pattern6.search(intro):
                                askedby = pattern6.search(intro).group(1)

                            parsed_date = None
                            #try:
                                # Friday, 20 September 2013
                            parsed_date = datetime.datetime.strptime(date, '%A, %d %B %Y')
                            #except:
                                #pass

                            data = strip_dict({
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
                                    })
                            # self.stdout.write("Writing object %s\n" % str(data))
                            q = Question.objects.create( **data )
                            # self.stdout.write("Wrote question #%d\n" % q.id)
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

        # self.stdout.write( 'Saved %d\n' % count )
        return True

