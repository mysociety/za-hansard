from bs4 import BeautifulSoup, NavigableString
import csv
from datetime import datetime, timedelta
import errno
import json
from optparse import make_option
import os
from os.path import dirname, join, exists
from pytz.tzinfo import StaticTzInfo
import re
import requests

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from instances.models import Instance

import za_hansard.chairperson as chair
from za_hansard.chairperson import strip_tags_from_html
from za_hansard.datejson import DateEncoder
from za_hansard.importers.import_json import ImportJson
from za_hansard.models import PMGCommitteeAppearance, PMGCommitteeReport

committee_mapping_filename = join(
    dirname(__file__),
    '..',
    '..',
    'data',
    'committee-meeting-mappings.csv'
)

source_cache_directory = join(settings.COMMITTEE_CACHE, 'meetings')

name_part_re_str = r'(?:[A-Z][-a-zA-Z]*|van|de|den|der)'

name_re_str = r'''
    # All names are prefixed with a title:
    (?P<title>Mr|Mrs|Ms|Miss|Dr|Prof|Professor|Prince|Princess|Adv|Advocate)\.?
    \s+
    # Let's say a name is 1 to 5 words ech beginning with a capital:
    (?P<name>(?:{name_part}\s+){{0,4}}{name_part})
'''.format(name_part=name_part_re_str)

name_only_re = re.compile(name_re_str, re.VERBOSE)

name_and_party_re = re.compile(
    name_re_str + r'''
    # Then there's (usually, but not always) an optional party afterwards
    (?:\s+\((?P<party>[-A-Z]+)(?:[;,]\s*(?P<region>[-\sA-Za-z]+))?\))
''',
    re.VERBOSE
)

# From: http://stackoverflow.com/q/600268/223092

def mkdir_p(path):
    try:
        os.makedirs(path)
    except OSError as exc: # Python >2.5
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else:
            raise

mkdir_p(source_cache_directory)

def get_authenticated(url):
    """A wrapper for python-requests's get, but with the API auth header"""

    return requests.get(
        url,
        headers={
            'Authentication-Token': settings.PMG_API_KEY,
        }
    )

def get_authenticated_json(url, cache_filename=None):
    """Return parsed JSON from an authenticated GET request"""

    return get_authenticated(url).json()

def all_committees():
    """A generator function to yield all committees from the PMG API"""

    page = 0
    url_format = 'https://api.pmg.org.za/committee/?page={0}'
    while True:
        results = get_authenticated_json(url_format.format(page))['results']
        if not results:
            break
        for result in results:
            yield result
        page += 1

def parse_api_datetime(s):
    """Turn a datetime string from the PMG API into a Python datetime

    This also makes sure it's a non-naive datetime, with the timezone
    offset set."""

    m = re.search(
        r'''^
            (?P<date_and_time>
                (?P<date>\d{4}-\d{2}-\d{2})
                T
                (?P<time>\d{2}:\d{2}:\d{2}))
            (?P<tz_sign>[-+])
            (?P<tz_hours>\d{2}):(?P<tz_minutes>\d{2})
        $''',
        s,
        re.VERBOSE
    )
    if not m:
        message = u"Failed to parse the date and time string: '{0}'"
        raise ValueError(message.format(s))
    dt = datetime.strptime(m.group('date_and_time'), "%Y-%m-%dT%H:%M:%S")
    tzoffset = TimezoneOffset(
        m.group('tz_sign'), m.group('tz_hours'), m.group('tz_minutes')
    )
    return tzoffset.localize(dt)

def find_chairpeople(soup):
    """Given BeautifulSoup of the page, find any named chairperson(s)

    This is largely delegated to the the chairperson module."""

    chairpeople = chair.get_from_text_version(soup)
    if chairpeople:
        # Sometimes newlines get into names; replace any run of
        # whitespace with a single space:
        chairpeople = re.sub(r'(?ms)\s+', ' ', chairpeople)
        return chairpeople.strip()

def write_prettified_html(html, meeting_id, dump_type):
    """For dumping a prettified version of some HTML

    This is for debugging; it dumps the prettified HTML in
    the committee cache."""

    soup = BeautifulSoup(html)
    filename = "{meeting_id}-{dump_type}.html".format(
        dump_type=dump_type,
        meeting_id=meeting_id,
    )
    with open(join(source_cache_directory, filename), 'w') as f:
        f.write(soup.prettify().encode('utf-8'))
    return soup

def get_names_from_appearance(appearance_text):
    """Given some text, find all names of people within it

    If you specify allow_no_party to be True, then a party in
    parentheses isn't required:

    >>> matches = get_names_from_appearance('also, Ms J Doe was present', True)
    >>> len(matches)
    1
    >>> matches[0].groups()
    ('Ms', 'J Doe')

    Otherwise, it is:

    >>> matches = get_names_from_appearance('also, Ms J Doe was present')
    >>> len(matches)
    0

    Parties must appear in brackets, and can have an optional region:

    >>> matches = get_names_from_appearance('Mr A van der B (ANC) said that...')
    >>> len(matches)
    1
    >>> matches[0].groups()
    ('Mr', 'A van der B', 'ANC', None)

    >>> matches = get_names_from_appearance(
    ...    'In addition, Adv. Alice Bob (DA; Gauteng) asked'
    ... )
    >>> len(matches)
    1
    >>> matches[0].groups()
    ('Adv', 'Alice Bob', 'DA', 'Gauteng')
    """

    name_matches = []
    match_indices = set()
    for name_match in name_and_party_re.finditer(appearance_text):
        match_indices.add(name_match.span()[0])
        name_matches.append(name_match)
    # for name_match in name_only_re.finditer(appearance_text):
    #     match_index = name_match.span()[0]
    #     if match_index not in match_indices:
    #         name_matches.append(name_match)
    return name_matches

def format_name_match(name_match):
    """Given a regex match object of a name, format it human-readably"""

    d = name_match.groupdict()
    title = d.get('title')
    name = d.get('name')
    party = d.get('party')
    result = u''
    if title:
        result += title
    if name:
        result += u' {0}'.format(name)
    if party:
        result += u' ({0})'.format(party)
    return result.strip()

def is_apologies_statement(appearance_text):
    """A predicate to test if some text represents apologies for the meeting"""

    return re.search(r'^\[?Apologies', appearance_text) or \
        ('The Chairperson noted the apologies of' in appearance_text)


# Modified from http://stackoverflow.com/a/15516170/223092
class TimezoneOffset(StaticTzInfo):

    def __init__(self, offset_sign, offset_hours, offset_minutes):
        hours = int(offset_hours, 10)
        if offset_sign == '-':
            hours *= -1
        elif offset_sign == '+':
            pass
        else:
            raise Exception, u"Unknown sign {0}".format(offset_sign)
        minutes = int(offset_minutes, 10)
        self._utcoffset = timedelta(hours=hours, minutes=minutes)


class Command(BaseCommand):

    help = 'Find committee appearances from the PMG API'

    option_list = BaseCommand.option_list + (
        make_option('--commit',
            default=False,
            action='store_true',
            help='Actually make changes to the database',
        ),
        make_option('--sayit-instance',
            type='str',
            default='default',
            help='SayIt instance to import into (only applies to --import-to-sayit',
        ),
        make_option('--scrape',
            default=False,
            action='store_true',
            help='Scrape committee minutes into the database',
        ),
        make_option('--save-json',
            default=False,
            action='store_true',
            help='Save JSON files from already scraped minutes in the database',
        ),
        make_option('--import-to-sayit',
            default=False,
            action='store_true',
            help='Import JSON files to SayIt',
        ),
        make_option('--delete-existing',
            default=False,
            action='store_true',
            help='Delete existing SayIt speeches (with --import-to-sayit)',
        ),
    )

    def handle_committee(self, committee):
        self.stdout.write("=======================================\n")
        self.stdout.write("handling committee: {0}\n".format(committee['name']))
        full_committee_results = get_authenticated_json(committee['url'])

        if 'events' not in full_committee_results:
            self.stdout.write("No events for that committee!\n")
            return

        for i, event in enumerate(full_committee_results['events']):
            self.stdout.write("committee {0}\n".format(committee['name']))
            msg = "api_committee_id {0} api_meeting_id {1}\n"
            self.stdout.write(msg.format(committee['id'], event['id']))
            meeting_report = self.get_meeting_report(
                committee, event
            )
            if not meeting_report:
                continue
            if self.options['commit']:
                meeting_report.save()
            # Now parse the appearances out of the event body:
            if not event['body']:
                self.stdout.write("Skipping an entry with an empty body\n")
                continue
            self.get_appearances(
                meeting_report,
                event['body'],
                event['chairperson']
            )

    def get_meeting_report(self, committee, committee_event):
        api_committee_id = committee['id']
        api_meeting_id = committee_event['id']
        meeting_report = None
        # See if there's already a report with these API IDs:
        try:
            return PMGCommitteeReport.objects.get(
                api_meeting_id=api_meeting_id,
                api_committee_id=api_committee_id,
            )
        except PMGCommitteeReport.DoesNotExist:
            pass
        # ... or, see if it's a report we scraped with the old scraper
        # that hasn't been updated with new API IDs yet:
        legacy_meeting_ids = self.meeting_from_api_id.get(str(api_meeting_id))
        api_datetime = parse_api_datetime(committee_event['date'])
        if legacy_meeting_ids:
            try:
                meeting_report = PMGCommitteeReport.objects.get(
                    meeting_url__endswith=legacy_meeting_ids['old_url']
                )
                # Set the api_meeting_id and api_committee_id on that
                # old report:
                meeting_report.api_meeting_id = api_meeting_id
                meeting_report.api_committee_id = api_committee_id
                # FIXME: listen to the commit option
                meeting_report.save()
            except PMGCommitteeReport.DoesNotExist:
                pass
        # Otherwise, this seems to be new, so create a new report for
        # the meeting:
        if not meeting_report:
            if 'url' not in committee_event:
                msg = "no URL in event with ID: {0} skipping...\n"
                self.stdout.write(msg.format(committee_event['id']))
                return None
            # FIXME: listen to the commit option
            meeting_report = PMGCommitteeReport.objects.create(
                premium=committee['premium'],
                processed=False,
                meeting_url=committee_event['url'],
                meeting_name=committee_event['title'],
                committee_url=committee['url'],
                committee_name=committee['name'],
                meeting_date=api_datetime.date(),
                api_committee_id=api_committee_id,
                api_meeting_id=api_meeting_id,
            )
        return meeting_report

    def get_appearances(self, meeting_report, body, api_chairperson):
        meeting_id = meeting_report.api_meeting_id
        write_prettified_html(body, meeting_id, 'meeting-body')
        body = re.sub(r'&nbsp;', ' ', body)
        body = strip_tags_from_html(body)
        soup = write_prettified_html(body, meeting_id, 'meeting-body-bleached')
        chairpeople = api_chairperson or find_chairpeople(soup)

        appearances = []

        if chairpeople:
            # Create a pseudo appearance for anyone who's down as the
            # chairperson of the meeting. (There's usually just one, but
            # sometimes someone else takes over later.)
            for name_match in get_names_from_appearance(chairpeople):
                full_name = format_name_match(name_match)
                self.stdout.write("  chair => {0}\n".format(full_name))
                appearances.append(
                    PMGCommitteeAppearance(
                        report=meeting_report,
                        party=name_match.groupdict().get('party', ''),
                        person=name_match.group('name'),
                        text=u'{0} chaired the meeting.'.format(full_name)
                    )
                )

        # Consider as a (real) appearance any navigable string right
        # under a <p>:
        for p in soup.find_all('p'):
            for appearance in p.children:
                if not isinstance(appearance, NavigableString):
                    continue
                # Ignore whitespace only:
                appearance = appearance.strip()
                if not appearance:
                    continue
                # Don't try to match names in a list of apologies;
                # it'll make an appearance for that person when they
                # weren't there:
                if is_apologies_statement(appearance):
                    continue
                for name_match in get_names_from_appearance(appearance):
                    self.stdout.write(
                        "  appearance from => {0}\n".format(
                            format_name_match(name_match)
                        )
                    )
                    appearances.append(
                        PMGCommitteeAppearance(
                            report=meeting_report,
                            party=name_match.groupdict().get('party', ''),
                            person=name_match.group('name'),
                            text=appearance
                        )
                    )

        self.stdout.write("{0} appearances found\n".format(len(appearances)))

        save_appearances = True
        if meeting_report.old_meeting_url():
            previous_number_of_appearances = meeting_report.appearances.count()
            if previous_number_of_appearances > len(appearances):
                save_appearances = False
                msg = "WARNING: ended up with fewer appearances ({0} previously)\n"
                self.stdout.write(msg.format(
                    previous_number_of_appearances
                ))
                self.stdout.write("So not saving the new appearances...\n")

        if save_appearances and self.options['commit']:
            # Remove all old appearances:
            PMGCommitteeAppearance.objects.filter(
                report=meeting_report
            ).delete()
            for appearance in appearances:
                appearance.save()

    def handle(self, *args, **options):

        command_options = ('scrape', 'save_json', 'import_to_sayit')
        if not any(options[k] for k in command_options):
            raise CommandError("You must specify one of --scrape, --save-json or --import-to-sayit")

        if options['scrape']:

            self.meeting_from_api_id = {}
            self.options = options

            with open(committee_mapping_filename) as f:
                for row in csv.DictReader(f):
                    self.meeting_from_api_id[row['committee_meeting_id']] = row

            for committee in all_committees():
                self.handle_committee(committee)

        if options['save_json']:

            for report in PMGCommitteeReport.objects.all():

                non_api_url = re.sub(
                    r'api.pmg.org.za', 'www.pmg.org.za', report.meeting_url
                )
                result = {
                    'committee_url': report.committee_url,
                    'organization': report.committee_name,
                    'title': report.meeting_name,
                    'report_url': non_api_url,
                    'date': report.meeting_date,
                    'public': bool(not report.premium),
                    'parent_section_titles': [
                        'Committee Minutes',
                        report.committee_name,
                        report.meeting_date.strftime('%d %B %Y'),
                    ],
                    'speeches': [
                        {
                            'party': a.party,
                            'personname': a.person,
                            'text': a.text,
                            'tags': ['committee']
                        }
                        for a in report.appearances.all()
                    ]
                }

                filename = join(
                    settings.COMMITTEE_CACHE,
                    '{0}.json'.format(report.id)
                )
                with open(filename, 'w') as f:
                    json.dump(result, f, indent=1, cls=DateEncoder)

        if options['import_to_sayit']:

            try:
                sayit_instance = Instance.objects.get(
                    label=options['sayit_instance']
                )
            except Instance.DoesNotExist:
                raise CommandError("SayIt instance (%s) not found".format(
                    options['syait_instance']
                ))

            reports = reports_all = PMGCommitteeReport.objects.all()
            section_ids = []

            if not options['delete_existing']:
                reports = reports_all.filter(sayit_section=None)

            for report in reports.iterator():

                filename = os.path.join(
                    settings.COMMITTEE_CACHE,
                    '{0}.json'.format(report.id)
                )
                if not exists(filename):
                    message = "WARNING: couldn't find a JSON file for report with ID {0}\n"
                    self.stdout.write(message.format(report.id))
                    continue

                importer = ImportJson(
                    instance=sayit_instance,
                    delete_existing=options['delete_existing'],
                    popit_url='http://za-new-import.popit.mysociety.org/api/v0.1/'
                )
                try:
                    message = "Importing {0} ({1})\n"
                    self.stdout.write(message.format(report.id, filename))
                    # FIXME: make the importer have a 'commit' option
                    section = importer.import_document(filename)

                    report.sayit_section = section
                    report.last_sayit_import = datetime.now().date()
                    if options['commit']:
                        report.save()

                    section_ids.append(section.id)

                except Exception as e:
                    message = 'WARNING: failed to import {0}: {1}'
                    self.stderr.write(message.format(report.id, e))

            self.stdout.write(str(section_ids))
            self.stdout.write('\n')

            self.stdout.write(
                'Imported {0} / {1} sections\n'.format(
                    len(section_ids),
                    len(reports_all)
                )
            )