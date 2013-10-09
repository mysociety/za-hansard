from mock import patch
import os
import re
import requests
import shutil

from django.test import TestCase
from django.template.defaultfilters import slugify

from .. import question_scraper


class ZAAnswerTests(TestCase):

    def sample_file(self, filename):
        tests_dir = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(tests_dir, 'test_inputs', 'questions', filename)

    def test_answer_parsing(self):
        input_doc_file       = self.sample_file('answer_1.doc')
        expected_output_file = self.sample_file('answer_1_expected.txt')

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

    penultimate_url = start_url + "&DocumentStart=830"
    penultimate_expected_number = 19

