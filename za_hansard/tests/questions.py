import os

from django.test import TestCase

from .. import question_scraper

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
