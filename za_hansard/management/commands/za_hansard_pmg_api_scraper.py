from bs4 import BeautifulSoup, NavigableString
import csv
from datetime import date, datetime, timedelta
import json
from optparse import make_option
from os.path import dirname, join, exists
import parslepy
import pytz
from pytz.tzinfo import StaticTzInfo
import re
import requests
import sys
import time

from django.conf import settings
from django.core.management.base import BaseCommand

import za_hansard.chairperson as chair
from ...models import PMGCommitteeAppearance, PMGCommitteeReport

committee_mapping_filename = join(
    dirname(__file__),
    '..',
    '..',
    'data',
    'committee-meeting-mappings.csv'
)

def get_authenticated(url):
    r = requests.get(
        url,
        headers={
            'Authentication-Token': settings.PMG_API_KEY,
        }
    )
    filename = re.sub(r'https?://', '', url)
    filename = re.sub(r'/', '-', filename)
    return r.json()

def all_committees():
    page = 0
    url_format = 'https://api.pmg.org.za/committee/?page={0}'
    while True:
        print "Fetching page", page
        results = get_authenticated(url_format.format(page))['results']
        if not results:
            break
        for result in results:
            yield result
        page += 1


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


def parse_api_datetime(s):
    """Turn a datetime string from the PMG API into a Python datetime"""
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


class Command(BaseCommand):

    help = 'Update old committee URLs to refer to legacy.pmg.org.za'

    option_list = BaseCommand.option_list + (
        make_option('--commit',
            default=False,
            action='store_true',
            help='Actually make changes to the database',
        ),
    )

    def check_committee(self, committee):
        print "========================================================================"
        print committee['name'], committee['url']
        full_committee_results = get_authenticated(committee['url'])
        full_committee_results.pop('events', None)
        full_committee_results.pop('tabled_committee_reports', None)
        full_committee_results.pop('questions_replies', None)
        full_committee_results.pop('calls_for_comments', None)
        print json.dumps(full_committee_results, indent=4, sort_keys=True)

    def handle_committee(self, committee):
        print "handling committee:", committee['name']
        full_committee_results = get_authenticated(committee['url'])
        # print json.dumps(full_committee_results, indent=4, sort_keys=True)

        for i, event in enumerate(full_committee_results['events']):
            # print "========================================================================"
            # print "url:", event['url']
            # print "id:", event['id']
            # api_meeting_id = event['id']
            meeting_report = self.get_meeting_report(
                committee, event
            )
            # Now parse the appearances out of the event body:
            if not event['body']:
                print "Skipping an entry with an empty body"
                continue
            # if event['id'] not in (8655, 8567):
            #     continue
            # if event['id'] != 8593:
            #     continue
            # if event['id'] != 6040:
            #     continue
            # if event['id'] != 6256:
            #     continue
            # if event['id'] != 5593:
            #     continue
            # if event['id'] != 8564:
            #     continue
            # if event['id'] != 8220:
            #     continue
            # if event['id'] != 10052:
            #     continue
            # if event['id'] != 9956:
            #     continue
            # if event['id'] != 7941:
            #     continue

            FIXME look at
            # if event['id'] != 7612:
            #     continue
            # if event['id'] != 8208:
            #     continue
            print "api_committee_id", committee['id'], "api_meeting_id", event['id']
            appearances = self.get_appearances(
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
            meeting_report = PMGCommitteeReport.objects.get(
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
                matching_report = PMGCommitteeReport.objects.get(
                    meeting_url__endswith=legacy_meeting_ids['old_url']
                )
                # Set the api_meeting_id and api_committee_id on that
                # old report:
                matching_report.api_meeting_id = api_meeting_id
                matching_report.api_committee_id = api_committee_id
            except PMGCommitteeReport.DoesNotExist:
                pass
        # Otherwise, this seems to be new, so create a new report for
        # the meeting:
        if not meeting_report:
            if 'url' not in committee_event:
                print "no URL in event with ID:", committee_event['id'], "skipping..."
                return None
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

    def find_chairperson(self, soup):
        chairperson = chair.get_split_across_spans(soup)
        if not chairperson:
            chairperson = chair.get_bold_and_sibling(soup)
        if not chairperson:
            chairperson = chair.get_from_text_version(soup)
        return chairperson

    def get_appearances(self, meeting_report, body, api_chairperson):
        soup = BeautifulSoup(re.sub(r'&nbsp;', ' ', body))
        chairperson = api_chairperson or self.find_chairperson(soup)
        print "got chairperson:", chairperson

        return





        report_rules = {
            "heading": "h1.title",
            "chairperson": "div.field-field-chairperson",
            "paragraphs(.field-field-minutes p.MsoNormal)": ["."]
            }
        if row.premium:
            page = self.premium_open_url_with_retries(url)
        else:
            page = self.open_url_with_retries(url)
        contents = page.read()
        p = parslepy.Parselet(report_rules)
        report = p.parse_fromstring(contents)
        self.totalappearances = 0

        soup = BeautifulSoup(contents)
        # Use BeautifulSoup due to issues with <br/> divisions when using Parslepy
        text = (
            unicode(soup.find('div',class_='field-field-minutes'))
            .replace('<br/>','')
            .replace('<div>','')
            .replace('</div>','')
            .replace('<p>','')
            .replace('</p>','')
            .replace('\t','')
            .replace('<b><i>Discussion</i></b>',''))
        paragraphs = text.split("\n")

        if len(paragraphs) < 3 and len(report['paragraphs']) > 1:
            paragraphs = report['paragraphs']

        PMGCommitteeAppearance.objects.filter(report=row).delete()

        if 'chairperson' not in report:
            report['chairperson'] = ""

        chairs = re.findall(self.name_re, report['chairperson'])

        findchair = False

        if len(chairs) > 1:
            for chair in chairs:
                save = {
                    'report': row,
                    'meeting_date': meetingDate,
                    'committee_url': committeeURL,
                    'committee': committeeName,
                    'meeting': report['heading'],
                    'party':  chair[2],
                    'person': chair[1],
                    'meeting_url': url,
                    'text': re.sub('<[^>]*>', '',
                        '%s %s (%s) chaired the meeting.' % (
                            chair[0], chair[1], chair[2]))
                    }
                PMGCommitteeAppearance.objects.create(**save)

                self.appearancesadded += 1

                self.allappearances.append(save)
                self.totalappearances += 1

        if len(chairs) is 1:
            findchair = True

        for paragraph in paragraphs:

            if (re.match('^(Apologies:)', paragraph) or
                'The Chairperson noted the apologies of' in paragraph):
                continue
            find = re.findall(self.name_re, paragraph)
            if find and len(find)>0:
                for found in find:
                    name = found[1]
                    party = found[2]

                    save = {
                        'report': row,
                        'meeting_date': meetingDate,
                        'committee_url': committeeURL,
                        'committee': committeeName,
                        'meeting': report['heading'],
                        'party': party,
                        'person': name,
                        'meeting_url': url,
                        'text': re.sub('<[^>]*>', '', paragraph)
                            .replace("Discussion\n", '')
                            .replace("Apologies\n", '')
                            .replace("Minutes:\n", '')
                            .replace("\n", ''),
                         }

                    obj, created = PMGCommitteeAppearance.objects.get_or_create(
                        person=name,
                        meeting_url=url,
                        defaults=save,
                        )

                    if created:
                        self.appearancesadded += 1

                        self.allappearances.append(save)
                        self.totalappearances += 1

            if findchair:
                if "The Chairperson" in paragraph:
                    findchair = False

                    save = {
                        'report': row,
                        'meeting_date': meetingDate,
                        'committee_url': committeeURL,
                        'committee': committeeName,
                        'meeting': report['heading'],
                        'party': chairs[0][2],
                        'person': chairs[0][1],
                        'meeting_url': url,
                        'text': re.sub('<[^>]*>', '', paragraph)
                            .replace("Apologies\n", '')
                            .replace("Minutes:\n", '')
                            .replace("\n", ' '),
                        }

                    obj = PMGCommitteeAppearance.objects.create(**save)
                    self.appearancesadded += 1
                    self.allappearances.append(save)
                    self.totalappearances += 1

        if self.totalappearances:
            PMGCommitteeReport.objects.filter(meeting_url=url).update(processed=True)








        pass




    def handle(self, *args, **options):

        self.meeting_from_old_url = {}
        self.meeting_from_old_node_id = {}
        self.meeting_from_api_id = {}

        with open(committee_mapping_filename) as f:
            for row in csv.DictReader(f):
                self.meeting_from_old_url[row['old_url']] = row
                self.meeting_from_old_node_id[row['old_node_id']] = row
                self.meeting_from_api_id[row['committee_meeting_id']] = row

        # user_json = get_authenticated('https://api.pmg.org.za/user')
        # print json.dumps(user_json, indent=4, sort_keys=True)

        # committee_names = [c['name'] for c in all_committees()]
        # committee_names.sort()
        # with open('api-committees.txt', 'w') as f:
        #     for c in committee_names:
        #         f.write(u"{0}\n".format(c))

        for committee in all_committees():
            if 'Agriculture' in committee['name']:
                self.handle_committee(committee)

        # for committee in all_committees():
        #     self.check_committee(committee)
