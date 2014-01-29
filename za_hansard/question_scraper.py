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

from za_hansard.models import Question, QuestionPaper

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

        print 'Questions (%s)' % self.next_list_url

        contents = self.url_get( self.next_list_url )

        p = parslepy.Parselet(self.question_parsing_rules)
        page = p.parse_fromstring(contents)


        for row in page['papers']:
            if len(row['cell']) == 11:
                url = row['cell'][8]['url']
                root, ext = os.path.splitext(os.path.split(url)[1])
                self.details.append({
                    "name": row['cell'][0]['contents'],
                    "language": row['cell'][6]['contents'],
                    "url": self.base_url + url,
                    "house": row['cell'][4]['contents'],
                    "date": row['cell'][2]['contents'],
                    "type": ext[1:],

                    # This is also in the pdf's metadata, but it's easier to
                    # get it from here
                    "document_number": int(root.split('_')[0]),
                    })

        # check for next page of links (or None if not found)
        self.next_list_url = None
        for cell in page['next']:
            if cell['contents'] == 'Next':
                next_url = self.base_url + cell['url']
                if self.next_list_url == next_url:
                    raise Exception("Possible url loop detected, next url '{0}' has not changed.".format(next_url))
                self.next_list_url = next_url
                break


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
                url = row['cell'][8]['url']
                document_name = row['cell'][0]['contents']
                types = url.partition(".")
                number_oral = ''
                number_written = ''
                #check for written/oral question numbers
                # (using apparent convention - a question can have one of each number)
                if re.match('[A-Za-z0-9]+[oO]([0-9]+)[ wW-]', document_name):
                    number_oral = re.match(
                        '[A-Za-z0-9]+[oO]([0-9]+)[ wW-]', document_name).group(1)
                if re.match('[A-Za-z0-9]+[wW]([0-9]+)[ oO-]', document_name):
                    number_written = re.match(
                        '[A-Za-z0-9]+[wW]([0-9]+)[ oO-]', document_name).group(1)
            
                date = row['cell'][2]['contents']
                parsed_date = None
                try:
                    parsed_date = datetime.datetime.strptime(date, '%d %B %Y')
                except:
                    warnings.warn("Failed to parse date (%s)" % date)
                    continue

                self.details.append(dict(
                    number_oral = number_oral,
                    name = document_name,
                    language = row['cell'][6]['contents'],
                    url = 'http://www.parliament.gov.za/live/'+url,
                    house = row['cell'][4]['contents'],
                    number_written = number_written,
                    date = parsed_date,
                    type = types[2],
                ))
        
        # check for next page of links (or None if not found)
        self.next_list_url = None
        for cell in page['next']:
            if cell['contents'] == 'Next':
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

        self.create_questions_from_xml(xmldata, url)

    def get_question_pdf_from_url(self, url):
        return requests.get(url).content

    def get_question_xml_from_pdf(self, pdfdata):
        return pdftoxml(pdfdata)

    def create_questions_from_xml(self, xmldata, url):
        house = self.kwargs['house']
        date_published = datetime.datetime.strptime(self.kwargs['date'], '%d %B %Y')

        question_re = re.compile(
            ur"""
              (?P<intro>
                (?P<number1>\d+)\.?\s+ # Question number
                [-a-zA-z]+\s+(?P<askedby>[-\w\s]+) # Name of question asker, dropping the title
                \s+\([\w\s]+\)
                \ to\ ask\ the\ 
                (?P<questionto>[-\w\s(),:]+):
                [-\w\s(),\[\]]*?
              ) # Intro
              (?P<translated>\u2020)?\s*</b>\s*
              (?P<question>.*?)\s* # The question itself.
              (?P<number2>[NC][WO]\d+E) # Number 2
            """,
            re.UNICODE | re.VERBOSE)

        # FIXME - can this be replaced with a call to dateutil?
        date_re = re.compile(ur"(MONDAY|TUESDAY|WEDNESDAY|THURSDAY|FRIDAY|SATURDAY|SUNDAY), \d{1,2} (JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER) \d{4}")
        session_re = re.compile(
            ur"\[No\s*(?P<issue_number>\d+)\u2014(?P<year>\d{4})\]\s+(?P<session>[a-zA-Z]+)\s+SESSION,\s+(?P<parliament>[a-zA-Z]+)\s+PARLIAMENT",
            re.UNICODE)

        text_to_int = {
            'FIRST': 1,
            'SECOND': 2,
            'THIRD': 3,
            'FOURTH': 4,
            'FOURH': 4, # Yes, really.
            'FIFTH': 5,
            'SIXTH': 6,
            'SEVENTH': 7,
            'EIGHTH': 8,
            'NINTH': 9,
            'TENTH': 10,
            }

        text = lxml.etree.fromstring(xmldata)

        question_paper = QuestionPaper(
            document_name=self.kwargs['name'],
            date_published=date_published,
            house=house,
            language=self.kwargs['language'],
            document_number=self.kwargs['document_number'],
            source_url=self.kwargs['url'],
            text=lxml.etree.tostring(text, pretty_print=True),
            )

        # pdftoxml produces an xml document with one <page> per page
        # of the original and <text> elements inside those. We're 
        # not actually interested in the pagination here so we may
        # as well just look at all the text elements.

        text_bits = [
            re.match(ur'(?s)<text.*?>(.*?)</text>', lxml.etree.tostring(el, encoding='unicode')).group(1)
            for el in text.iterfind('.//text')
            ]

        new_text = u''.join(text_bits)
        new_text = re.sub(ur'</?i>', '', new_text)
        new_text = re.sub(ur'</b>(\s*)<b>', ur'\1', new_text)
        new_text = re.sub(ur'<b>(\s*)</b>', ur'\1', new_text)

        # As we're using the </b> to tell us when the intro is over, it would be
        # helpful if we could always have the colon on the same side of it.
        new_text = new_text.replace('</b>:', ':</b>')

        # Sanity check on house
        assert house.upper() in new_text

        match = question_re.findall(new_text)

        session_match = session_re.search(new_text)

        if session_match:
            question_paper.session_number = text_to_int.get(session_match.group('session'))
            question_paper.parliament_number = text_to_int.get(session_match.group('parliament'))
            question_paper.issue_number = int(session_match.group('issue_number'))
            question_paper.year = int(session_match.group('year'))
        else:
            print "Failed to find session, etc."

        # FIXME - This causes an error on files with only oral questions.
        # We haven't actually collected any oral questions yet, but when we do,
        # this will need sorting out.
        start_pos = re.search(ur'QUESTIONS FOR WRITTEN REPLY', new_text).end()
        # You might think that ending at the start of the summary of questions not yet replied to is a good
        # thing, but there are a couple of random questions right at the end of the file
        # which it would be good to catch.
        # end_pos = re.search(ur'SUMMARY OF QUESTIONS NOT YET REPLIED TO', new_text).start()
        
        interesting_text = new_text[start_pos:]#end_pos]

        date_match = date_re.search(interesting_text)

        if date_match:
            date = datetime.datetime.strptime(date_match.group(0), '%A, %d %B %Y')
        else:
            print "Failed to find date"

        question_paper.save()

        for match in question_re.finditer(interesting_text):
            match_dict = match.groupdict()

            match_dict[u'paper'] = question_paper

            match_dict[u'translated'] = bool(match_dict[u'translated'])
            match_dict[u'questionto'] = match_dict[u'questionto'].replace(':', '')

            # FIXME - Note that the staging server has not a single question marked as oral
            #         questiontype = 'oral' if '&#204;' in intro else 'written'
            match_dict[u'type'] = u'written'

            # FIXME - Should be removed when we properly integrate QuestionPaper
            match_dict[u'date'] = date

            Question.objects.create(**match_dict)
