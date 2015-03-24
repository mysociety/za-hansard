from bs4 import BeautifulSoup
import csv
from datetime import date
import json
from optparse import make_option
from os.path import dirname, join, exists
import parslepy
import re
import requests
import sys
import time

from django.conf import settings
from django.core.management.base import BaseCommand

from ...models import PMGCommitteeAppearance, PMGCommitteeReport

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

    def handle(self, *args, **options):

        user_json = get_authenticated('https://api.pmg.org.za/user')
        print json.dumps(user_json, indent=4, sort_keys=True)

        committee_names = [c['name'] for c in all_committees()]
        committee_names.sort()
        with open('api-committees.txt', 'w') as f:
            for c in committee_names:
                f.write(u"{0}\n".format(c))

        # for committee in all_committees():
        #     self.check_committee(committee)
