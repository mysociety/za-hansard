import os
import datetime

import requests
import requests_cache
from UserDict import DictMixin

from django.test import TestCase

from .. import question_scraper

class FileBasedRequestsCacheResponses(DictMixin, dict):

    def cache_file(self, name):
        tests_dir = os.path.dirname(os.path.abspath(__file__))
        cache_dir = os.path.join(tests_dir, 'test_inputs', 'questions_cache')
        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir)
        return os.path.join(cache_dir, name)

    def __getitem__(self, name):
        filename = self.cache_file(name)
        if os.path.exists(filename):
            print "HIT  {0} --> {1}".format(name, filename)
            response = open(filename, 'rb').read()
            return (response, datetime.utcnow())
        else:
            print "MISS {0} --> {1}".format(name, filename)
            raise KeyError
    
    def __setitem__(self, name, value):
        (response, timestamp) = value
        filename = self.cache_file(name)
        print "SET  {0} --> {1}".format(name, filename)
        print value
        fh = open(filename, 'wb')
        fh.write(response)
        fh.close()

class FileBasedRequestsCache(requests_cache.backends.base.BaseCache):

    def __init__(self, *args, **kwargs):
        print "Creating FileBasedRequestsCache"
        self.keys_map = {}
        self.responses = FileBasedRequestsCacheResponses()


class ZAQuestionTests(TestCase):

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

    def test_question_detail_iterator(self):
        # These tests should use cached data so that they are not subject to changes
        # to the HTML on the server. This cached data is committed to the repo. If you
        # delete the cache files they'll be regenerated on the next run, allowing you to
        # diff any changes to the server.

        requests_cache.install_cache(backend=FileBasedRequestsCache())
        # with requests_cache.enabled(backend=FileBasedRequestsCache()):

        details = question_scraper.QuestionDetailIterator("http://www.parliament.gov.za/live/content.php?Category_ID=236")
        
        for detail in details:
            print detail
            break
        
        self.assertTrue(False)
