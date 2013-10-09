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

class ZAQuestionTests(TestCase):

    def cache_file(self, name):
        tests_dir = os.path.dirname(os.path.abspath(__file__))
        cache_dir = os.path.join(tests_dir, 'test_inputs', 'questions_cache')
        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir)
        return os.path.join(cache_dir, name)


    def test_question_detail_iterator(self):
        # These tests should use cached data so that they are not subject to changes
        # to the HTML on the server. This cached data is committed to the repo. If you
        # delete the cache files they'll be regenerated on the next run, allowing you to
        # diff any changes to the server.

        # To delete all the cache files uncomment this line
        # shutil.rmtree(self.cache_file(''))

        details = question_scraper.QuestionDetailIterator("http://www.parliament.gov.za/live/content.php?Category_ID=236")

        # create a method to retrieve url contents from file
        def get_from_file_or_network(url):

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


        retrieved_details = []
        number_to_retrieve = 50

        with patch.object(details, "url_get", new=get_from_file_or_network):
            # Get the first number_to_retrieve questions
            for detail in details:
                retrieved_details.append( detail )
                if len(retrieved_details) >= number_to_retrieve: break


        self.assertEqual(len(retrieved_details), number_to_retrieve)
