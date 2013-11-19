import urllib2
import lxml.etree
import sys
import re, os
import lxml.html
import dateutil.parser
import string
import parslepy
import json
from za_hansard.datejson import DateEncoder
from lxml import etree
import time

import subprocess

from datetime import datetime, date, timedelta

from optparse import make_option

from django.conf import settings

from django.core.management.base import BaseCommand, CommandError
from za_hansard.models import Question, Answer
from speeches.importers.import_json import ImportJson
from instances.models import Instance

# ideally almost all of the parsing code would be removed from this management
# command and put into a module where it can be more easily tested and
# separated. This is the start of that process.
from ... import question_scraper

class Command(BaseCommand):

    help = 'Check for new sources'
    option_list = BaseCommand.option_list + (
        make_option('--scrape-questions',
            default=False,
            action='store_true',
            help='Scrape questions (step 1)',
        ),
        make_option('--scrape-answers',
            default=False,
            action='store_true',
            help='Scrape answers (step 2)',
        ),
        make_option('--process-answers',
            default=False,
            action='store_true',
            help='Process answers (step 3)',
        ),
        make_option('--match-answers',
            default=False,
            action='store_true',
            help='Match answers (step 4)',
        ),
        make_option('--save',
            default=False,
            action='store_true',
            help='Save Q&A as json (step 5)',
        ),
        make_option('--import-into-sayit',
            default=False,
            action='store_true',
            help='Import saved json to sayit (step 6)',
        ),
        make_option('--run-all-steps',
            default=False,
            action='store_true',
            help='Run all of the steps',
        ),        
        make_option('--instance',
            type='str',
            default='default',
            help='Instance to import into',
        ),
        make_option('--limit',
            default=0,
            action='store',
            type='int',
            help='How far to go back (not set means all the way)',
        ),
        make_option('--fetch-to-limit',
            default=False,
            action='store_true',
            help="Don't stop when reaching seen questions, continue to --limit",
        ),
    )

    start_url_q = ('http://www.parliament.gov.za/live/', 'content.php?Category_ID=236')
    start_url_a = ('http://www.parliament.gov.za/live/', 'content.php?Category_ID=248')

    def handle(self, *args, **options):
        if options['scrape_questions']:
            self.scrape_questions(*args, **options)
        elif options['scrape_answers']:
            self.scrape_answers(*args, **options)
        elif options['process_answers']:
            self.process_answers(*args, **options)
        elif options['match_answers']:
            self.match_answers(*args, **options)
        elif options['save']:
            self.qa_to_json(*args, **options)
        elif options['import_into_sayit']:
            self.import_into_sayit(*args, **options)
        elif options['run_all_steps']:
            self.scrape_questions(*args, **options)
            self.scrape_answers(*args, **options)
            self.process_answers(*args, **options)
            self.match_answers(*args, **options)
            self.qa_to_json(*args, **options)
            self.import_into_sayit(*args, **options)
        else:
            raise CommandError("Please supply a valid option")

    def scrape_questions(self, *args, **options):

        start_url = self.start_url_q[0] + self.start_url_q[1]
        details = question_scraper.QuestionDetailIterator(start_url)

        count = 0
        errors = 0

        for detail in details:
            count+=1
            print "Document ", count

            source_url = detail['url']
            if detail['language']=='English' and detail['type']=='pdf':

                if Question.objects.filter( source=source_url ).count():
                    self.stderr.write('Already exists\n')
                    if not options['fetch_to_limit']:
                        self.stderr.write("Stopping as '--fetch-to-limit' not given\n")
                        break
                else:
                    try:
                        self.stderr.write('Processing %s' % source_url)
                        pages = self.get_question( source_url )
                    except Exception as e:
                        self.stderr.write( str(e) )
                        errors += 1
                        pass

            elif detail['language']=='English':
                self.stderr.write('%s is not a pdf\n' % source_url)

            else:
                pass
                # presumably non-English

            if options['limit'] and count >= options['limit']:
                break

        self.stdout.write( "Processed %d documents (%d errors)" % (count, errors) )

    def get_question(self, url):
        count=0
        pdfdata = urllib2.urlopen(url).read()
        xmldata = question_scraper.pdftoxml(pdfdata)

        if not xmldata:
            return False

        #self.stderr.write("URL %s\n" % url)
        #self.stderr.write("PDF len %d\n" % len(pdfdata))
        #self.stderr.write("XML %s\n" % xmldata)

        root = lxml.etree.fromstring(xmldata)
        #except Exception as e:
            #self.stderr.write("OOPS")
            #raise CommandError( '%s failed (%s)' % (url, e))
        self.stderr.write("XML parsed...\n")

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
                            # self.stdout.write("Writing object %s\n" % str(data))
                            q = Question.objects.create( **data )
                            self.stdout.write("Wrote question #%d\n" % q.id)
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


    def scrape_answers(self, *args, **options):

        start_url = self.start_url_a[0] + self.start_url_a[1]
        details = question_scraper.AnswerDetailIterator(start_url)

        count = 0

        for detail in details:
            count+=1

            if Answer.objects.filter( url = detail['url'] ).exists():
                self.stderr.write('Already exists\n')
                if not options['fetch_to_limit']:
                    self.stderr.write("Stopping as '--fetch-to-limit' not given\n")
                    break
            else:
                self.stderr.write('Adding answer for {0}\n'.format(detail['url']))
                answer = Answer.objects.create(**detail)

            if options['limit'] and count >= options['limit']:
                break


    def process_answers(self, *args, **options):

        answers = Answer.objects.exclude( url = None )
        unprocessed = answers.exclude( processed_code=Answer.PROCESSED_OK )

        self.stderr.write( "Processing %d records" % len(unprocessed) )

        for row in unprocessed:
            self.stdout.write('.')
            try:
                download = urllib2.urlopen( row.url )
                filename = os.path.join(
                        settings.ANSWER_CACHE,
                        '%d.%s' % (row.id, row.type))
                save = open( filename, 'wb' )
                save.write( download.read() )
                save.close()

                try:
                    text = question_scraper.extract_answer_text_from_word_document(filename)
                    row.processed_code = Answer.PROCESSED_OK
                    row.text = text
                    row.save()
                except subprocess.CalledProcessError:
                    self.stderr.write( 'ERROR in antiword processing %d' % row.id )
                    pass

            except urllib2.HTTPError:
                row.processed_code = Answer.PROCESSED_HTTP_ERROR
                row.save()
                self.stderr.write( 'ERROR HTTPError while processing %d' % row.id )
                pass

            except urllib2.URLError:
                self.stderr.write( 'ERROR URLError while processing %d' % row.id )
                pass

    def match_answers(self, *args, **options):

        #get all the answers for processing (this should change to all not already processed)

        # for row in c.execute('SELECT id,number_written,number_oral,date FROM answers'):
        answers = Answer.objects.all()

        count = 0

        for answer in answers:
            answer_date = answer.date
            earliest_question_date = answer_date - timedelta( days = 365 )

            if answer.number_written:
                questions = Question.objects.filter(
                        number1 = answer.number_written,
                        type = 'written',
                        date__lte = answer_date,
                        date__gte = earliest_question_date
                    ).order_by('-date')

                if questions.exists():
                    question = questions[0]

                    question.answer = answer
                    question.save()
                    answer.matched_to_question = 1
                    answer.save()
                    count += 1

            # now oral (answer can be to both a written and oral question)
            # TODO refactor with above
            if answer.number_oral:
                questions = Question.objects.filter(
                        number1 = answer.number_oral,
                        type = 'oral',
                        date__lte = answer_date,
                        date__gte = earliest_question_date
                    ).order_by('-date')

                if questions.exists():
                    question = questions[0]

                    question.answer = answer
                    question.save()
                    answer.matched_to_question = 1
                    answer.save()
                    count += 1

        self.stdout.write('Matched %d answers\n' % count)

    def qa_to_json(self, *args, **options):
        questions = (Question.objects
                .filter( answer__isnull = False)
                .prefetch_related('answer')
                .filter(answer__processed_code = Answer.PROCESSED_OK)
                )

        for question in questions:
            answer = question.answer
            #{
            # "speeches": [
            #  {
            #   "personname": "M Johnson",
            #   "party": "ANC",
            #   "text": "Mr M Johnson (ANC) chaired the meeting."
            #  },
            #  ...
            #  ],
            # "date": "2013-06-21",
            # "organization": "Agriculture, Forestry and Fisheries",
            # "reporturl": "http://www.pmg.org.za/report/20130621-report-back-from-departments-health-trade-and-industry-and-agriculture-forestry-and-fisheries-meat-inspection",
            # "title": "Report back from Departments of Health, Trade and Industry, and Agriculture, Forestry and Fisheries on meat inspection services and labelling in South Africa",
            ## "committeeurl": "http://www.pmg.org.za/committees/Agriculture,%20Forestry%20and%20Fisheries"
            tosave = {
                'parent_section_titles': [
                    'Questions',
                    'Questions asked to ' + question.questionto,
                ],
                'questionto': question.questionto,
                'title': question.date.strftime('%d %B %Y'),
                'date': question.date,
                'speeches': [
                    {
                        'personname': question.askedby,
                        # party?
                        'text':       question.question,
                        'tags': ['question'],


                        # unused for import
                        'type':       'question',
                        'intro':      question.intro,
                        'date':       question.date,
                        'source':     question.source,
                        'translated': question.translated
                    },
                    {
                        'personname':   question.questionto,
                        # party?
                        'text':   answer.text,
                        'tags': ['answer'],

                        # unused for import
                        'name' : answer.name,
                        'persontitle': question.questionto,
                        'type':   'answer',
                        'source': answer.url,
                        'date':   answer.date,
                    }
                ],

                # random stuff that is NOT used by the JSON import
                'number1': question.number1,
                'number2': question.number2,
                'askedby': question.askedby,
                'type': question.type,
                'house': question.house,
                'parliament': question.parliament,
            }
            filename = os.path.join(
                settings.ANSWER_CACHE,
                "%d.json" % question.id)
            with open(filename, 'w') as outfile:
                json.dump(
                    tosave,
                    outfile,
                    indent=1,
                    cls=DateEncoder)
            self.stdout.write('Wrote %s\n' % filename)

    def import_into_sayit(self, *args, **options):
        instance = None
        try:
            instance = Instance.objects.get(label=options['instance'])
        except Instance.NotFound:
            raise CommandError("Instance specified not found (%s)" % options['instance'])

        questions = (Question.objects
                .filter( sayit_section = None ) # not already imported
                .filter( answer__isnull = False)
                .prefetch_related('answer')
                .filter(answer__processed_code = Answer.PROCESSED_OK)
                )

        sections = []
        for question in questions:
            path = os.path.join(
                settings.ANSWER_CACHE,
                "%d.json" % question.id)
            if not os.path.exists(path):
                continue

            importer = ImportJson( instance=instance,
                popit_url='http://za-peoples-assembly.popit.mysociety.org/api/v0.1/')
            #try:
            self.stderr.write("TRYING %s\n" % path)
            section = importer.import_document(path)
            sections.append(section)
            question.sayit_section = section
            question.last_sayit_import = datetime.now().date()
            question.save()
            #except Exception as e:
                #self.stderr.write('WARN: failed to import %d: %s' %
                    #(question.id, str(e)))

        self.stdout.write( str( [s.id for s in sections] ) )
        self.stdout.write( '\n' )
        self.stdout.write('Imported %d / %d sections\n' %
            (len(sections), len(questions)))

