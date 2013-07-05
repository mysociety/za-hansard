
# This script changed extensively when the Kenyan Parliament website changed after the 2013 Election.
#
# The previous version can be seen at:
#
#    https://github.com/mysociety/mzalendo/blob/7181e30519b140229e3817786e4a7440ac08288d/mzalendo/hansard/management/commands/hansard_check_for_new_sources.py

import pprint
import httplib2
import re
import datetime
import sys

from bs4 import BeautifulSoup

from django.conf import settings


from django.core.management.base import NoArgsCommand

from zah.models import Source

class Command(NoArgsCommand):
    help = 'Check for new sources'

    # http://www.parliament.go.ke
    # /plone/national-assembly/business/hansard/copy_of_official-report-28-march-2013-pm/at_multi_download/item_files
    # ?name=Hansard%20National%20Assembly%2028.03.2013P.pdf


    def handle_noargs(self, **options):


        if False:
            url = 'http://www.parliament.gov.za/live/content.php?Category_ID=119'
            h = httplib2.Http( settings.HTTPLIB2_CACHE_DIR )
            response, content = h.request(url)
            # print content
        else:
            url = './test.html'
            content = open(url).read()

        # parse content
        soup = BeautifulSoup(
            content,
            'xml',
        )

        nodes = soup.findAll( 'a', text="View Document" )
        for node in nodes:
            print node['href']
            table = node.find_parent('table')
            # print node.find_parent('table')['onMouseOver'] # parses wrong thing due to dodgy HTML
            title = table.find('b').text
            print title
            rx = re.compile(r'>([^:<]*) : ([^<]*)<')
            dict = {}
            for match in re.finditer(rx, str(table)):
                groups = match.groups()
                dict[groups[0]] = groups[1]
            print dict

    def __FOR_LATER__():
        # I don't trust that we can accurately create the download link url with the
        # details that we have. Instead fetche the page and extract the url.
        download_response, download_content = h.request(href)
        download_soup = BeautifulSoup(
            download_content,
            'xml',
        )
        download_url = download_soup.find( id="archetypes-fieldname-item_files" ).a['href']
        # print download_url
        
        # create/update the source entry
        Source.objects.get_or_create(
            name = name,
            defaults = dict(
                url = download_url,
                date = source_date,
            )
        )
