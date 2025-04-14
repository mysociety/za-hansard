# -*- coding: utf-8 -*-
import distutils.spawn
import hashlib
import os
import sys
import re
import requests
import subprocess
import tempfile
import warnings
import datetime
import lxml.etree

import parslepy

from django.core.exceptions import ImproperlyConfigured
from django.conf import settings

from za_hansard.models import ATCDocument

#Largely based on question_scraper.py

# from https://github.com/scraperwiki/scraperwiki-python/blob/a96582f6c20cc1897f410d522e2a5bf37d301220/scraperwiki/utils.py#L38-L54
# Copied rather than included as the scraperwiki __init__.py was having trouble
# loading the sqlite code, which is something we don't actually need.

def ensure_executable_found(name):
    if not distutils.spawn.find_executable(name):
        raise ImproperlyConfigured("Can't find executable '{0}' which is needed by this code".format(name))

ensure_executable_found("pdftohtml")
def pdftoxml(pdfdata):
    """converts pdf file to xml file"""
    pdffout = tempfile.NamedTemporaryFile(suffix='.pdf')
    pdffout.write(pdfdata)
    pdffout.flush()

    xmlin = tempfile.NamedTemporaryFile(mode='r', suffix='.xml')
    tmpxml = xmlin.name # "temph.xml"
    cmd = 'pdftohtml -xml -nodrm -zoom 1.5 -enc UTF-8 -noframes "%s" "%s"' % (pdffout.name, os.path.splitext(tmpxml)[0])
    cmd = cmd + " >/dev/null 2>&1" # can't turn off output, so throw away even stderr yeuch
    os.system(cmd)

    pdffout.close()
    #xmlfin = open(tmpxml)
    xmldata = xmlin.read()
    xmlin.close()

    # pdftohtml version 0.18.4 occasionally produces bad markup of the form <b>...<i>...</b> </i>
    # Since ee don't actually need <i> tags, we may as well get rid of them all now, which will fix this.
    # Note that we're working with a byte string version of utf-8 encoded data here.

    xmldata = re.sub(r'</?i>', '', xmldata)

    return xmldata

class ATCDocumentParser(object):
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    @classmethod
    def check_committee_membership_announcement(cls, document_path):

        if os.path.exists(document_path):
            with open(document_path) as f:
                contents = f.read()

        if not contents:
            return

        xmldata = pdftoxml(contents)

        if not xmldata:
            sys.stdout.write(' SKIPPING - Got no XML data\n')
            return

        text = lxml.etree.fromstring(xmldata)

        for el in text.iterfind('.//text'):
            if 'Membership of Committees' in re.match(ur'(?s)<text.*?>(.*?)</text>', lxml.etree.tostring(el, encoding='unicode')).group(1):
                return True

        #committee announcement not found
        return False


