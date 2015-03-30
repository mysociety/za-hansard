from bs4 import BeautifulSoup
import csv
from datetime import date
import json
from optparse import make_option
from os.path import dirname, join, exists
import re
import requests
import sys
import time

from django.conf import settings
from django.core.management.base import BaseCommand

from ...models import PMGCommitteeReport

canonical_url_cache_filename = join(dirname(__file__), '.canonical-url-cache')
committee_mapping_filename = join(
    dirname(__file__),
    '..',
    '..',
    'data',
    'committee-meeting-mappings.csv'
)

def login_with_session(requests_session):
    login_url = 'http://legacy.pmg.org.za/user/login'
    response = requests_session.get(login_url)
    soup = BeautifulSoup(response.content)
    form = soup.find('form', {'name': 'login_user_form'})
    data = {
        i['name']: i['value']
        for i in
        form.find_all('input')
    }
    data['email'] = settings.PMG_COMMITTEE_USER
    data['password'] = settings.PMG_COMMITTEE_PASS
    r = requests_session.post(login_url, data=data)
    if 'Your password is incorrect' in r.content:
        raise Exception('Login to the legacy PMG website failed')

def login():
    session = requests.Session()
    login_with_session(session)
    return session

def get_canonical_url(legacy_url, canonical_url_cache, requests_session):
    # If we've got a cached result, then return it:
    if legacy_url in canonical_url_cache:
        return canonical_url_cache[legacy_url]
    # Otherwise we have to fetch the page (sometimes slow):
    legacy_response = None
    maximum_retries = 3
    retries_left = 3
    while (not legacy_response) and retries_left > 0:
        try:
            if retries_left < maximum_retries:
                print "Retries left:", retries_left
            legacy_response = requests_session.get(legacy_url)
            if legacy_response.status_code == 404:
                message = "Unexpected 404 for {0}".format(legacy_url)
                print >> sys.stderr, message.format(legacy_url)
                return None
            if not legacy_response:
                message = "Got no response for URL {0} legacy_response with {1} retries left"
                raise Exception, message.format(
                    legacy_url, retries_left
                )
            time.sleep(1)

            soup = BeautifulSoup(legacy_response.content)
            if soup.find('h1', text=re.compile(r'Please login first')):
                # Then try logging in again:
                print >> sys.stderr, "Trying logging in again before retrying"
                login_with_session(requests_session)
                retries_left -= 1
                continue
            legacy_response.raise_for_status()
        except requests.exceptions.HTTPError:
            retries_left -= 1
            continue
    if legacy_response is None:
        message = "Broken legacy URL: {0}"
        print >> sys.stderr, message.format(legacy_url)
        return None
    canonical_url_cache[legacy_url] = legacy_response.url
    return legacy_response.url


def row_as_utf8(row):
    return {k: unicode(v).encode('utf-8') for k, v in row.items()}


class Command(BaseCommand):

    help = 'Update old committee URLs to refer to legacy.pmg.org.za'

    option_list = BaseCommand.option_list + (
        make_option('--commit',
            default=False,
            action='store_true',
            help='Actually make changes to the database',
        ),
    )


    def handle(self, *args, **options):

        committee_mapping = {}

        with open(committee_mapping_filename) as f:
            for row in csv.DictReader(f):
                committee_mapping[row['old_url'] = row


        requests_session = login()

        if exists(canonical_url_cache_filename):
            with open(canonical_url_cache_filename) as f:
                canonical_url_cache = json.load(f)
        else:
            canonical_url_cache = {}

        try:
            fieldnames = [
                'committee',
                'meeting_date',
                'original_meeting_url',
                'legacy_meeting_url',
                'canonical_meeting_url',
                'committee_url',
            ]
            with open('committee-url-mapping.csv', 'w') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for pcr in PMGCommitteeReport.objects.all():
                    row = {k: '' for k in fieldnames}
                    row['original_meeting_url'] = pcr.meeting_url
                    row['meeting_date'] = pcr.meeting_date
                    # Only rewrite data for meetings before 2015
                    if pcr.meeting_date and (pcr.meeting_date >= date(2015, 1, 1)):
                        writer.writerow(row_as_utf8(row))
                        continue
                    # Rewrite any old URLs to refer to the legacy site:
                    print 'meeting_url', "was:", pcr.meeting_url
                    legacy_url = None
                    if pcr.meeting_url and ('www.pmg.org.za' in pcr.meeting_url):
                        legacy_url = re.sub(
                            r'www\.pmg\.org\.za',
                            'legacy.pmg.org.za',
                            pcr.meeting_url
                        )
                        row['legacy_meeting_url'] = legacy_url
                        if options['commit']:
                            print '  changing it to:', legacy_url
                            pcr.meeting_url = legacy_url
                            pcr.save()
                        else:
                            message = '  would change to {0} if --commit was specified'
                            print message.format(legacy_url)
                    # Also set the canonical version of the legacy URL:
                    if legacy_url and ('legacy.pmg.org.za' in legacy_url):
                        canonical_url = get_canonical_url(
                            legacy_url,
                            canonical_url_cache,
                            requests_session
                        )
                        row['canonical_meeting_url'] = canonical_url
                        print "   ... maps to canonical URL:", canonical_url
                        if canonical_url:
                            if canonical_url != pcr.canonical_meeting_url:
                                pcr.canonical_meeting_url = canonical_url
                                if options['commit']:
                                    print "  setting that canonical URL"
                                    pcr.save()
                                else:
                                    print '  would set that if --commit was specified'
                    writer.writerow(row_as_utf8(row))
        finally:
            with open(canonical_url_cache_filename, 'w') as f:
                json.dump(canonical_url_cache, f)
