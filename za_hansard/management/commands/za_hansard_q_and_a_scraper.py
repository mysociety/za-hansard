import urllib2
import sys
import re, os
import dateutil.parser
import string
import parslepy
import json
import time

import subprocess

from datetime import datetime, date, timedelta

from optparse import make_option

from django.conf import settings

from django.core.management.base import BaseCommand, CommandError
from za_hansard.models import Question, Answer, QuestionPaper
from speeches.importers.import_json import ImportJson
from instances.models import Instance

# ideally almost all of the parsing code would be removed from this management
# command and put into a module where it can be more easily tested and
# separated. This is the start of that process.
from ... import question_scraper

def strip_dict(d):
    return { k: v.strip() if 'strip' in dir(v) else v for k, v in d.items() }

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

        # detail here is a dictionary of the form:
        # {
        # "name":     row['cell'][0]['contents'],
        # "language": row['cell'][6]['contents'],
        # "url":      self.base_url + url,
        # "house":    row['cell'][4]['contents'],
        # "date":     row['cell'][2]['contents'],
        # "type":     types[2]
        # }
        
        for detail in details:
            count+=1

            source_url = detail['url']
            sys.stdout.write(
                "{count:5} {url} ".format(count=count, url=source_url))

            if detail['language']=='English' and detail['type']=='pdf':
                if QuestionPaper.objects.filter(source_url=source_url).exists():
                    self.stdout.write('SKIPPING as file already handled\n')
                    if not options['fetch_to_limit']:
                        self.stdout.write("Stopping as '--fetch-to-limit' not given\n")
                        break
                else:
                    try:
                        self.stdout.write('PROCESSING')
                        question_scraper.QuestionPaperParser(**detail).get_questions()
                    except Exception as e:
                        self.stdout.write('ERROR handling {}: {}\n'.format(source_url, str(e)))
                        errors += 1
                        pass

            elif detail['language']=='English':
                self.stdout.write('SKIPPING as not a pdf\n')
            else:
                # presumably non-English
                sys.stdout.write('SKIPPING presumably not English\n')

            if options['limit'] and count >= options['limit']:
                break

        self.stdout.write( "Processed %d documents (%d errors)\n" % (count, errors) )


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
                detail = strip_dict(detail)
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
            earliest_question_date = answer_date - timedelta( days = 183 ) # 6 months

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
            question_as_json = self.question_to_json(question)

            filename = os.path.join(
                settings.ANSWER_CACHE,
                "%d.json" % question.id)
            with open(filename, 'w') as outfile:
                outfile.write(question_as_json)
            self.stdout.write('Wrote %s\n' % filename)


    def question_to_json(self, question):
        question_as_json_data = self.question_to_json_data(question)

        return json.dumps(
            question_as_json_data,
            indent=1,
            sort_keys=True
        )


    def question_to_json_data(self, question):
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

        # As of Python 2.7.3, time.strftime can't be trusted to preserve
        # unicodeness, hence the extra calls to unicode.

        question_as_json = {
            u'parent_section_titles': [
                u'Questions',
                u'Questions asked to the ' + question.questionto,
            ],
            u'questionto': question.questionto,
            u'title': unicode(question.date.strftime(u'%d %B %Y')),
            u'date': unicode(question.date.strftime(u'%Y-%m-%d')),
            u'speeches': [
                {
                    u'personname': question.askedby,
                    # party?
                    u'text': question.question,
                    u'tags': [u'question'],


                    # unused for import
                    u'type': u'question',
                    u'intro': question.intro,
                    u'date': unicode(question.date.strftime(u'%Y-%m-%d')),
                    u'source': question.paper.source_url,
                    u'translated': question.translated,
                },
            ],

            # random stuff that is NOT used by the JSON import
            u'oral_number': question.oral_number,
            u'written_number': question.written_number,
            u'identifier': question.identifier,
            u'askedby': question.askedby,
            u'answer_type': question.answer_type,
            u'parliament': question.paper.parliament_number,
        }

        answer = question.answer
        if answer:
            question_as_json[u'speeches'].append(
                {
                    u'personname': question.questionto,
                    # party?
                    u'text': answer.text,
                    u'tags': [u'answer'],

                    # unused for import
                    u'name' : answer.name,
                    u'persontitle': question.questionto,
                    u'type': u'answer',
                    u'source': answer.url,
                    u'date': unicode(answer.date.strftime(u'%Y-%m-%d')),
                }
            )

        return question_as_json

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

