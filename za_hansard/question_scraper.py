# -*- coding: utf-8 -*-
import distutils.spawn
import os
import sys
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

    # pdftohtml version 0.18.4 occasionally produces bad markup of the form <b>...<i>...</b> </i>
    # Since ee don't actually need <i> tags, we may as well get rid of them all now, which will fix this.
    # Note that we're working with a byte string version of utf-8 encoded data here.

    xmldata = re.sub(r'</?i>', '', xmldata)

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

page_header_regex= re.compile(ur"\s*(?:{}|{})\s*".format(
        ur'(?:\d+ \[)?[A-Z][a-z]+day, \d+ [A-Z][a-z]+ \d{4}(?:\] \d+)? INTERNAL QUESTION PAPER: (?:NATIONAL ASSEMBLY|NATIONAL COUNCIL OF PROVINCES) NO \d+[─-]\d{4}',
        ur'[A-Z][a-z]+day, \d+ [A-Z][a-z]+ \d{4} INTERNAL QUESTION PAPER: (?:NATIONAL ASSEMBLY|NATIONAL COUNCIL OF PROVINCES) NO \d+\s*[─-]\s*\d{4} \d+',
        )
                               )
    

def remove_headers_from_page(page):
    ur"""Remove unwanted headers at top of page.
    page must be a page element from the lxml etree of a
    question paper generated by pdftoxml.
    This function modifies page in place by removing

    1) The page number
    2) The date bit
    3) The title
    
    of the document which are are in the <text> elements at the at the top of
    every page.

    Note that the page number referred to here is the one in a text element
    from the original PDF, and not the one added in by pdftoxml as an attribute
    of each <page> element.

    For example, 559662_1.xml has a page which starts

    # <page number="2" position="absolute" top="0" left="0" height="1263" width="892">
    # <text top="80" left="85" width="750" height="16" font="1"> 273 </text>
    # <text top="80" left="607" width="205" height="16" font="1">[<i>Friday, 13 December 2013 </i></text>
    # <text top="1197" left="364" width="447" height="11" font="2">INTERNAL QUESTION PAPER: NATIONAL COUNCIL OF PROVINCES NO 37─2013 </text>

    We would like to get rid of these three text elements.

    # Check page_header_regex works
    >>> page_header_regex.match(u'Friday, 13 December 2013] 272 INTERNAL QUESTION PAPER: NATIONAL COUNCIL OF PROVINCES NO 37─2013 ') is not None
    True
    >>> page_header_regex.match(u' 273 [Friday, 13 December 2013 INTERNAL QUESTION PAPER: NATIONAL COUNCIL OF PROVINCES NO 37─2013 ') is not None
    True
    >>> page_header_regex.match(u'239 [Friday, 19 April 2013 INTERNAL QUESTION PAPER: NATIONAL ASSEMBLY NO 12─2013 ') is not None
    True
    >>> page_header_regex.match(u' Friday, 9 October 2009 INTERNAL QUESTION PAPER: NATIONAL ASSEMBLY NO 20 - 2009 533') is not None
    True

    """
    
    accumulated = ''
    
    # 10 text elements should be enough to catch all
    # the headers, and few enough to prevent us interfering
    # with more than one question if it all goes wrong.
    for text_el in page.xpath('text[position()<=10]'):
        accumulated += re.match(ur'(?s)<text.*?>(.*?)</text>', lxml.etree.tostring(text_el, encoding='unicode')).group(1)
        accumulated = re.sub(ur'<i>(.*?)</i>', ur'\1', accumulated, flags=re.UNICODE)
        accumulated = re.sub(ur'</i>(.*?)<i>', ur'\1', accumulated, flags=re.UNICODE)
        accumulated = re.sub(ur'(\s+)', ur' ', accumulated, flags=re.UNICODE)

        if page_header_regex.match(accumulated):
            for to_remove in text_el.itersiblings(preceding=True):
                page.remove(to_remove)

            page.remove(text_el)
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


    question_re = re.compile(
        ur"""
          (?P<intro>
            (?P<number1>\d+)\.?\s+ # Question number
            [-a-zA-z]+\s+(?P<askedby>[-\w\s]+?) # Name of question asker, dropping the title
            \s*\((?P<party>[-\w\s]+)\)?
            \s+to\s+ask\s+the\s+
            (?P<questionto>[-\w\s(),:.]+)[:.]
            [-\u2013\w\s(),\[\]/]*?
          ) # Intro
          (?P<translated>\u2020)?\s*</b>\s*
          (?P<question>.*?)\s* # The question itself.
          (?P<number2>[NC][WO]\d+E) # Number 2
        """,
        re.UNICODE | re.VERBOSE)

    session_re = re.compile(
        ur"\[No\s*(?P<issue_number>\d+)\s*[\u2013\u2014]\s*(?P<year>\d{4})\]\s+(?P<session>[a-zA-Z]+)\s+SESSION,\s+(?P<parliament>[a-zA-Z]+)\s+PARLIAMENT",
        re.UNICODE | re.IGNORECASE)

    def create_questions_from_xml(self, xmldata, url):
        """
        # Checks for question_re

        # Shows the need for - in the party
        >>> qn = u'144. Mr D B Feldman (COPE-Gauteng) to ask the Minister of Defence and Military Veterans: </b>Whether the deployment of the SA National Defence Force soldiers to the Central African Republic and the Democratic Republic of Congo is in line with our international policy with regard to (a) upholding international peace, (b) the promotion of constitutional democracy and (c) the respect for parliamentary democracy; if not, why not; if so, what are the (i) policies which underpin South African foreign policy and (ii) further relevant details? CW187E'
        >>> match = QuestionPaperParser.question_re.match(qn)
        >>> match.groups()
        (u'144. Mr D B Feldman (COPE-Gauteng) to ask the Minister of Defence and Military Veterans:', u'144', u'D B Feldman', u'COPE-Gauteng', u'Minister of Defence and Military Veterans', None, u'Whether the deployment of the SA National Defence Force soldiers to the Central African Republic and the Democratic Republic of Congo is in line with our international policy with regard to (a) upholding international peace, (b) the promotion of constitutional democracy and (c) the respect for parliamentary democracy; if not, why not; if so, what are the (i) policies which underpin South African foreign policy and (ii) further relevant details?', u'CW187E')

        # Shows the need for \u2013 (en-dash) and / (in the date) in latter part of the intro
        >>> qn = u'409. Mr M J R de Villiers (DA-WC) to ask the Minister of Public Works: [215] (Interdepartmental transfer \u2013 01/11) </b>(a) What were the reasons for a cut back on the allocation for the Expanded Public Works Programme to municipalities in the 2013-14 financial year and (b) what effect will this have on (i) job creation and (ii) service delivery? CW603E'
        >>> match = QuestionPaperParser.question_re.match(qn)
        >>> match.groups()
        (u'409. Mr M J R de Villiers (DA-WC) to ask the Minister of Public Works: [215] (Interdepartmental transfer \u2013 01/11)', u'409', u'M J R de Villiers', u'DA-WC', u'Minister of Public Works', None, u'(a) What were the reasons for a cut back on the allocation for the Expanded Public Works Programme to municipalities in the 2013-14 financial year and (b) what effect will this have on (i) job creation and (ii) service delivery?', u'CW603E')

        # Cope with missing close bracket
        >>> qn = u'1517. Mr W P Doman (DA to ask the Minister of Cooperative Governance and Traditional Affairs:</b> Which approximately 31 municipalities experienced service delivery protests as referred to in his reply to oral question 57 on 10 September 2009? NW1922E'
        >>> match = QuestionPaperParser.question_re.match(qn)
        >>> match.groups()
        (u'1517. Mr W P Doman (DA to ask the Minister of Cooperative Governance and Traditional Affairs:', u'1517', u'W P Doman', u'DA', u'Minister of Cooperative Governance and Traditional Affairs', None, u'Which approximately 31 municipalities experienced service delivery protests as referred to in his reply to oral question 57 on 10 September 2009?', u'NW1922E')

        # Check we cope with no space before party in parentheses
        >>> qn = u'1569. Mr M Swart(DA) to ask the Minister of Finance: </b>Test question? NW1975E'
        >>> match = QuestionPaperParser.question_re.match(qn)
        >>> match.groups()
        (u'1569. Mr M Swart(DA) to ask the Minister of Finance:', u'1569', u'M Swart', u'DA', u'Minister of Finance', None, u'Test question?', u'NW1975E')

        # Check we cope with a dot after the askee instead of a colon.
        >>> qn = u'1875. Mr G G Hill-Lewis (DA) to ask the Minister in the Presidency. National Planning </b>Test question? NW2224E'
        >>> match = QuestionPaperParser.question_re.match(qn)
        >>> match.groups()
        (u'1875. Mr G G Hill-Lewis (DA) to ask the Minister in the Presidency. National Planning', u'1875', u'G G Hill-Lewis', u'DA', u'Minister in the Presidency', None, u'Test question?', u'NW2224E')

        # Checks for session_re
        >>> session_string = u'[No 37\u20142013] FIFTH SESSION, FOURTH PARLIAMENT'
        >>> match = QuestionPaperParser.session_re.match(session_string)
        >>> match.groups()
        (u'37', u'2013', u'FIFTH', u'FOURTH')
        >>> session_string = u'[No 20 \u2013 2009] First Session, Fourth Parliament'
        >>> match = QuestionPaperParser.session_re.match(session_string)
        >>> match.groups()
        (u'20', u'2009', u'First', u'Fourth')
        """
        house = self.kwargs['house']
        date_published = datetime.datetime.strptime(self.kwargs['date'], '%d %B %Y')

        # FIXME - can this be replaced with a call to dateutil?
        date_re = re.compile(ur"(MONDAY|TUESDAY|WEDNESDAY|THURSDAY|FRIDAY|SATURDAY|SUNDAY), \d{1,2} (JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER) \d{4}")

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

        pages = text.iter('page')
        
        for page in pages:
            remove_headers_from_page(page)

        # pdftoxml produces an xml document with one <page> per page
        # of the original and <text> elements inside those. We're 
        # not actually interested in the pagination here so we may
        # as well just look at all the text elements.

        text_bits = [
            re.match(ur'(?s)<text.*?>(.*?)</text>', lxml.etree.tostring(el, encoding='unicode')).group(1)
            for el in text.iterfind('.//text')
            ]

        new_text = u''.join(text_bits)

        # We may as well git rid of bolding or unbolding around whitespace.
        new_text = re.sub(ur'</b>(\s*)<b>', ur'\1', new_text)
        new_text = re.sub(ur'<b>(\s*)</b>', ur'\1', new_text)

        # Replace all whitespace with single spaces.
        new_text = re.sub(r'\s+', ' ', new_text)

        # As we're using the </b> to tell us when the intro is over, it would be
        # helpful if we could always have the colon on the same side of it.
        new_text = new_text.replace('</b>:', ':</b>')

        # Sanity check on number of questions
        expected_question_count = len(re.findall(r'to\s+ask\s+the', new_text))

        # Sanity check on house
        assert house.upper() in new_text

        session_match = self.session_re.search(new_text)

        if session_match:
            question_paper.session_number = text_to_int.get(session_match.group('session').upper())
            question_paper.parliament_number = text_to_int.get(session_match.group('parliament').upper())
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

        questions = []

        for match in self.question_re.finditer(interesting_text):
            match_dict = match.groupdict()

            match_dict[u'paper'] = question_paper

            match_dict[u'translated'] = bool(match_dict[u'translated'])
            match_dict[u'questionto'] = match_dict[u'questionto'].replace(':', '')

            # FIXME - Note that the staging server has not a single question marked as oral
            #         questiontype = 'oral' if '&#204;' in intro else 'written'
            match_dict[u'type'] = u'written'

            # FIXME - Should be removed when we properly integrate QuestionPaper
            match_dict[u'date'] = date

            # Party isn't actually stored in the question, so drop it before saving
            # Perhaps we can eventually use it to make sure we have the right person.
            # (and to tidy up the missing parenthesis.)
            match_dict.pop(u'party')

            questions.append(Question(**match_dict))

        sys.stdout.write(' found {} questions'.format(len(questions)))

        if len(questions) != expected_question_count:
            sys.stdout.write(" expected {} - SUSPICIOUS".format(expected_question_count))
        
        sys.stdout.write('\n')
            
        Question.objects.bulk_create(questions)
