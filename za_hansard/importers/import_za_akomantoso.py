# -*- coding: utf-8 -*-

from datetime import datetime
import re

from lxml import etree

from za_hansard.importers.import_base import ImportZAMixin
from speeches.importers.import_akomantoso import ImportAkomaNtoso
from speeches.models import Section, Speech

name_rx = re.compile(r'^(\w+) (.*?)( \((\w+)\))?$')

def title_case_heading(heading):
    titled = heading.title()
    titled = titled.replace("'S", "'s").replace("’S", "’s")
    return titled

class ImportZAAkomaNtoso (ImportZAMixin, ImportAkomaNtoso):
    def __init__(self, section_parent_titles=[], **kwargs):
        self.section_parent_titles = section_parent_titles
        super(ImportZAAkomaNtoso, self).__init__(**kwargs)

    def construct_title(self, node):
        title = super(ImportZAAkomaNtoso, self).construct_title(node)
        title = title_case_heading(title)
        return title

    def get_speaker(self, child):
        display_name = self.name_display(child['from'].text)
        speaker = self.get_person(display_name, None)
        return speaker, display_name

    def parse_document(self):
        """We know we only have one top level section, which we want to
        deal with differently, so do that here"""

        debate = self.xml.debate
        preface = debate.preface
        debateBody = debate.debateBody
        mainSection = debateBody.debateSection

        self.title = '%s (%s)' % (
                mainSection.heading.text,
                etree.tostring(preface.p, method='text'))

        # Get or create the sections above the one we just created and put it in there
        parent = Section.objects.get_or_create_with_parents(instance=self.instance, titles=self.section_parent_titles)

        section = self.make(Section, title=self.title, parent=parent)

        self.set_start_date(
            datetime.strptime(preface.p.docDate.get('date'), '%Y-%m-%d')
            )

        self.visit(mainSection, section)
        return section

    def name_display(self, name):
        if not name:
            return '(narrative)'
        match = name_rx.match(name)
        if match:
            honorific, fname, party, _ = match.groups()
            fname = fname.title()
            display_name = '%s %s%s' % (honorific, fname, party if party else '')
            # XXX Now the sayit project indexes stop words, this next line keeps
            # the test passing. This should be looked at at some point.
            # "The" is not an honorific anyway, should we be here?.
            display_name = re.sub('^The ', '', display_name)
            return display_name
        else:
            name = name.title()
            return name

    def handle_tag(self, node, section):
        """We handle anything coming in. In practice, this is currently
        <p>s as direct children of <debateSection>s."""

        text = self.get_text(node)
        speaker = self.get_person(None, None)
        speech = self.make(Speech,
            section = section,
            start_date = self.start_date,
            text = text,
            speaker = speaker,
        )
        return True
