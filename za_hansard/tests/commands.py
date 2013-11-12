from datetime import date, time

from django.test import TestCase
from django.core.management import call_command

from speeches.tests.helpers import create_sections
from speeches.models import Speech, Tag


class OneOffTagSpeechesTests(TestCase):

    def setUp(self):

        subsections = [
            {   'title': "Nested section",
                'subsections': [
                    {   'title': "Section with speeches",
                        'speeches': [ 4, date(2013, 3, 25), time(9, 0) ],
                    },
                    {   'title': "Bill on Silly Walks",
                        'speeches': [ 2, date(2013, 3, 25), time(12, 0) ],
                    },
                ]
            },
            {
                'title': "Another nested section (but completely empty)",
                'subsections': []
            },
        ]

        create_sections([
            {
                'title': "Hansard",
                'subsections': subsections,
            },
            {
                'title': "Committee Minutes",
                'subsections': subsections,
            },
            {
                'title': "Some Other Top Level Section",
                'subsections': subsections,
            },
        ])

    def test_tagging(self):
        # check that no speeches are tagged
        self.assertEqual(Speech.objects.filter(tags=None).count(), 18)

        call_command('za_hansard_one_off_tag_speeches')

        hansard = Tag.objects.get(name='hansard')
        committee = Tag.objects.get(name='committee')

        self.assertEqual(Speech.objects.filter(tags=None).count(), 6)
        self.assertEqual(Speech.objects.filter(tags=hansard).count(), 6)
        self.assertEqual(Speech.objects.filter(tags=committee).count(), 6)
