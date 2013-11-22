from mock import patch
import os
import re
import requests
import shutil
import datetime
import json
from django.utils.unittest import skipUnless

from django.test import TestCase
from django.template.defaultfilters import slugify

from .. import question_scraper
from ..management.commands.za_hansard_q_and_a_scraper import Command as QAScraperCommand
from ..models import Question

def sample_file(filename):
    tests_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(tests_dir, 'test_inputs', 'questions', filename)


class ZAAnswerTests(TestCase):

    def test_answer_parsing(self):
        input_doc_file       = sample_file('answer_1.doc')
        expected_output_file = sample_file('answer_1_expected.txt')

        text = question_scraper.extract_answer_text_from_word_document(input_doc_file)
        expected = open(expected_output_file).read().decode('UTF-8')

        # Handy for updating the expected data.
        # out = open(expected_output_file, 'w+')
        # out.write(text.encode('UTF-8'))
        # out.close()

        self.assertEqual(text, expected)



class ZAIteratorBaseMixin(object):

    def setUp(self):
        # These tests should use cached data so that they are not subject to changes
        # to the HTML on the server. This cached data is committed to the repo. If you
        # delete the cache files they'll be regenerated on the next run, allowing you to
        # diff any changes to the server.

        # To delete all the cache files uncomment this line
        # shutil.rmtree(self.cache_file(''))

        pass

    def cache_file(self, name):
        tests_dir = os.path.dirname(os.path.abspath(__file__))
        cache_dir = os.path.join(tests_dir, 'test_inputs', self.cache_dir_name)
        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir)
        return os.path.join(cache_dir, name)

    # create a method to retrieve url contents from file
    def get_from_file_or_network(self, url):

        # Reduce the url into something more manageable as a filename
        filename = slugify( re.sub( r'\W+', '-', re.sub(r'^.*/','', url))) + ".html"
        full_path = self.cache_file(filename)

        # Check for the file on disk. If found return it, else fetch and cache it
        if os.path.exists(full_path):
            with open(full_path) as read_from:
                return read_from.read()
        else:
            print "Retrieving and caching " + url
            response = requests.get( url )
            with open(full_path, 'w') as write_to:
                write_to.write(response.text)
            return response.text

    def fetch_details(self, details, number):
        retrieved_details = []

        with patch.object(details, "url_get", new=self.get_from_file_or_network):
            # Get the first number_to_retrieve questions
            for detail in details:
                retrieved_details.append( detail )
                if len(retrieved_details) >= number: break

        return retrieved_details

    def test_question_detail_iterator(self):

        details = self.iterator_model(self.start_url)
        number_to_retrieve = 50

        retrieved_details = self.fetch_details(details, number_to_retrieve)

        self.assertEqual(len(retrieved_details), number_to_retrieve)

        # Test that selected results are as we expect. 'expected_details' is a list of
        # tuples where the first item is the index in the expected details and the
        # second is what is expected. This allows interesting or edge case results to be
        # tested, skipping the dull or repeated ones.
        for index, expected in self.expected_details:
            self.assertEqual(retrieved_details[index], expected)


    def test_question_detail_iterator_stops_at_end(self):

        # Note that these tests rely on the cached html being as expected. If you update
        # that then please change the settings for the penultimate page of results, and
        # the number of questions expected after scraping.

        details = self.iterator_model(self.penultimate_url)
        number_to_retrieve = self.penultimate_expected_number + 20

        retrieved_details = self.fetch_details(details, number_to_retrieve)

        self.assertEqual(len(retrieved_details), self.penultimate_expected_number)




class ZAQuestionIteratorTests(ZAIteratorBaseMixin, TestCase):

    cache_dir_name = 'questions_cache'
    iterator_model = question_scraper.QuestionDetailIterator

    start_url = "http://www.parliament.gov.za/live/content.php?Category_ID=236"
    expected_details = (
        (0, {
            'date': u'20 September 2013',
            'house': u'National Council of Provinces',
            'language': u'Afrikaans',
            'name': u'QC130920.i28A',
            'type': 'pdf',
            'url': 'http://www.parliament.gov.za/live/commonrepository/Processed/20130926/541835_1.pdf'
        }),
    )

    penultimate_url = start_url + "&DocumentStart=830"
    penultimate_expected_number = 19


class ZAAnswerIteratorTests(ZAIteratorBaseMixin, TestCase):

    cache_dir_name = 'answers_cache'
    iterator_model = question_scraper.AnswerDetailIterator

    start_url = "http://www.parliament.gov.za/live/content.php?Category_ID=248"
    expected_details = (
        (0, {
            'date': datetime.datetime(2013, 10, 3, 0, 0),
            'house': u'National Assembly',
            'language': u'English',
            'name': u'RNW2356-131003',
            'number_oral': '',
            'number_written': u'2356',
            'type': 'doc',
            'url': 'http://www.parliament.gov.za/live/commonrepository/Processed/20131007/543139_1.doc'
        }),
    )

    penultimate_url = start_url + "&DocumentStart=5310"
    penultimate_expected_number = 16


class ZAQuestionParsing(TestCase):

    pdf_source_url = 'http://www.parliament.gov.za/live/commonrepository/Processed/20130529/517147_1.pdf'

    # The exact form of the XML returned depends on the version of pdftohtml
    # used. Use the version installed onto travis as the common ground (as of
    # this writing 0.18.4). Also run if we have this version locally.
    pdftohtml_version = os.popen('pdftohtml -v 2>&1 | head -n 1').read().strip()
    wanted_version = '0.18.4'
    @skipUnless(
        os.environ.get('TRAVIS') or wanted_version in pdftohtml_version,
        "Not on TRAVIS, or versions don't watch ('%s' != '%s')" % (wanted_version, pdftohtml_version)
    )
    def test_pdf_to_xml(self):
        command = QAScraperCommand()

        pdfdata      = open(sample_file("517147_1.pdf")).read()
        expected_xml = open(sample_file("517147_1.xml")).read()

        actual_xml = command.get_question_xml_from_pdf(pdfdata)

        self.assertEqual(actual_xml, expected_xml)


    def test_xml_to_json(self):
        # Would be nice to test the intermediate step of the data written to the database, but that is not as easy to access as the JSON. As a regression test this will work fine though.

        xmldata = open(sample_file("517147_1.xml")).read()
        command = QAScraperCommand()

        # Load xml to the database
        command.create_questions_from_xml(xmldata, self.pdf_source_url)

        # Turn questions in database into JSON. Order by id as that should
        # reflect the processing order.
        all_questions_as_data = []
        for question in Question.objects.order_by('id'):
            question_as_data = command.question_to_json_data(question)
            all_questions_as_data.append(question_as_data)


        expected_file = sample_file('expected_json_data_for_517147_1.json')
        # Uncomment to write out to the expected JSON file.
        # with open(expected_file, 'w') as writeto:
        #     json_to_write = json.dumps(all_questions_as_data, indent=1, sort_keys=True)
        #     writeto.write(re.sub(r' +$', '', json_to_write, flags=re.MULTILINE) + "\n")

        expected_json = open(expected_file).read()
        expected_data = json.loads(expected_json)

        self.assertEqual(all_questions_as_data, expected_data)

