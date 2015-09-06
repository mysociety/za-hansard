# -*- coding: utf-8 -*-

import os

from django.core.management import call_command
from django.utils.unittest import skip

from instances.tests import InstanceTestCase
from popit.models import ApiInstance
from popit_resolver.resolve import SetupEntities, EntityName

from speeches.models import Speaker
from za_hansard.importers.import_za_akomantoso import ImportZAAkomaNtoso, title_case_heading

import logging
logging.disable(logging.WARNING)

popit_url = 'http://za-new-import.popit.mysociety.org/api/v0.1/'


class ImportZAAkomaNtosoTests(InstanceTestCase):

    @classmethod
    def setUpClass(cls):
        cls._in_fixtures = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'test_inputs', 'hansard')

        call_command('clear_index', interactive=False, verbosity=0)

        if not EntityName.objects.count():
            # calling an external API during tests is a bad idea, it's not
            # reliable and makes the tests very slow
            # XXX: disabled this test
            return
            SetupEntities(popit_url).init_popit_data()
            call_command('update_index', verbosity=0)

    @classmethod
    def tearDownClass(cls):
        EntityName.objects.all().delete()
        ApiInstance.objects.all().delete()
        call_command('clear_index', interactive=False, verbosity=0)

    @skip("Depends on external API data")
    def test_import(self):
        return
        document_path = os.path.join(self._in_fixtures, 'NA200912.xml')

        an = ImportZAAkomaNtoso(instance=self.instance, commit=True, popit_url=popit_url)
        section = an.import_document(document_path)

        self.assertTrue(section is not None)

        # Check that all the sections have correct looking titles
        for sub in section.children.all():
            self.assertFalse("Member'S" in sub.title)

        speakers = Speaker.objects.all()
        resolved = filter(lambda s: s.person != None, speakers)
        THRESHOLD = 48

        logging.info(
                "%d above threshold %d/%d?"
                % (len(resolved), THRESHOLD, len(speakers)))

        self.assertTrue(
                len(resolved) >= THRESHOLD,
                "%d above threshold %d/%d"
                % (len(resolved), THRESHOLD, len(speakers)))

    def test_title_casing(self):
        tests = (
            # initial, expected
            ("ALL CAPS", "All Caps"),
            ("MEMBER'S Statement", "Member's Statement"),
            ("member’s", "Member’s"),
        )

        for initial, expected in tests:
            self.assertEqual(title_case_heading(initial), expected)
