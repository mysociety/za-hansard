import os, sys
import re
import httplib2
import calendar

from django.db import models
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from speeches.models import Section

# NOTE: cargo culting from https://github.com/mysociety/mzalendo/blob/master/mzalendo/hansard/models/source.py
# TODO refactor these routines, unsure how to do that in Python

# check that the cache is setup and the directory exists
try:
    if not os.path.exists( settings.HANSARD_CACHE ):
        os.makedirs( settings.HANSARD_CACHE )
except AttributeError:
    raise ImproperlyConfigured("Could not find HANSARD_CACHE setting - please set it")

try:
    if not os.path.exists( settings.COMMITTEE_CACHE ):
        os.makedirs( settings.COMMITTEE_CACHE )
except AttributeError:
    raise ImproperlyConfigured("Could not find COMMITTEE_CACHE setting - please set it")

try:
    if not os.path.exists( settings.ANSWER_CACHE ):
        os.makedirs( settings.ANSWER_CACHE )
except AttributeError:
    raise ImproperlyConfigured("Could not find ANSWER_CACHE setting - please set it")

# EXCEPTIONS

class SourceUrlCouldNotBeRetrieved(Exception):
    pass

class SourceCouldNotParseTimeString(Exception):
    pass


class SourceQuerySet(models.query.QuerySet):
    def requires_processing(self):
        return self.filter( last_processing_attempt=None )

    def requires_completion(self, retry_download=False):
        objects = self.filter( last_processing_success=None )
        if not retry_download:
            objects = objects.filter( is404=False )
        return objects


class SourceManager(models.Manager):
    def get_query_set(self):
        return SourceQuerySet(self.model)


class Source(models.Model):
    """
    Sources of the hansard transcripts

    For example a Word transcript.
    """

    title           = models.CharField(max_length=200)
    document_name   = models.CharField(max_length=200) # bah, SHOULD be unique, but apparently isn't
    document_number = models.IntegerField(unique=True)
    date            = models.DateField()
    url             = models.URLField(max_length=1000)
    is404           = models.BooleanField( default=False )
    house           = models.CharField(max_length=200)
    language        = models.CharField(max_length=200)

    last_processing_attempt = models.DateTimeField(blank=True, null=True)
    last_processing_success = models.DateTimeField(blank=True, null=True)

    last_sayit_import = models.DateTimeField(blank=True, null=True)
    sayit_section = models.ForeignKey(Section, blank=True, null=True, on_delete=models.PROTECT,
        help_text='Associated Sayit section object, if imported')

    objects = SourceManager()

    class Meta:
        ordering = [ '-date', 'document_name' ]


    def __unicode__(self):
        return self.document_name


    def delete(self):
        """After deleting from db, delete the cached file too"""
        cache_file_path = self.cache_file_path()
        super( Source, self ).delete()

        if os.path.exists( cache_file_path ):
            os.remove( cache_file_path )


    def file(self, debug=False):
        """
        Return as a file object the resource that the url is pointing to.

        Should check the local cache first, and fetch and store if it is not
        found there.

        Raises a SourceUrlCouldNotBeRetrieved exception if URL could not be
        retrieved.
        """
        cache_file_path = self.cache_file_path()

        found = os.path.isfile(cache_file_path)

        if debug:
            print >> sys.stderr, "%s (%s)" % (cache_file_path, found)

        # If the file exists open it, read it and return it
        if found:
            return cache_file_path

        # If not fetch the file, save to cache and then return fh
        h = httplib2.Http()
        url = 'http://www.parliament.gov.za/live/' + self.url

        def request_url(url):
            if debug:
                print >> sys.stderr, 'Requesting %s' % url
            (response, content) = h.request(url)
            if response.status != 200:
                raise SourceUrlCouldNotBeRetrieved("status code: %s, url: %s" % (response.status, self.url) )
            self.is404 = False
            self.save()
            return (response, content)

        try:
            (response, content) = request_url(url)
        except SourceUrlCouldNotBeRetrieved as e:
            try:
                if not url[-4:] == '.doc':
                    (response, content) = request_url(url + '.doc')
                    self.url = self.url + '.doc'
                    self.save()
                else:
                    raise e
            except:
                raise e

        if not content:
            raise SourceUrlCouldNotBeRetrieved("WTF?")
        with open(cache_file_path, "w") as new_cache_file:
            new_cache_file.write(content)

        return cache_file_path

    @property
    def section_parent_titles(self):
        return [
            "Hansard",
            str(self.date.year),
            calendar.month_name[self.date.month],
            "%02d" % self.date.day,
        ]

    def cache_file_path(self):
        """Absolute path to the cache file for this source"""

        id_str= "%05u" % self.id

        # do some simple partitioning
        # FIXME - put in something to prevent the test suite overwriting non-test files.
        aaa = id_str[-1]
        bbb = id_str[-2]
        cache_dir = os.path.join(settings.HANSARD_CACHE, aaa, bbb)

        # check that the dir exists
        if not os.path.exists( cache_dir ):
            os.makedirs( cache_dir )

        d = self.date.strftime('%Y-%m-%d')

        # create the path to the file
        cache_file_path = os.path.join(cache_dir, '-'.join([d, id_str, self.document_name]))
        return cache_file_path

    def xml_file_path(self):
        xml_file_path = '%s.xml' % self.cache_file_path()
        if os.path.isfile(xml_file_path):
            return xml_file_path
        return None

class PMGCommitteeReport(models.Model):
    """
    Committe reports, scraped from PMG site
    """
    # CREATE TABLE reports (id integer primary key autoincrement, premium BOOL,
    # processed NUMERIC, meeting_url TEXT);
    premium         = models.BooleanField()
    processed       = models.BooleanField()
    meeting_url     = models.TextField()

    last_sayit_import = models.DateTimeField(blank=True, null=True)
    sayit_section = models.ForeignKey(Section, blank=True, null=True, on_delete=models.PROTECT,
        help_text='Associated Sayit section object, if imported')

class PMGCommitteeAppearance(models.Model):
    """
    Committe appearances, scraped from PMG site
    """
    # CREATE TABLE appearances (id integer primary key autoincrement,
    # meeting_date TEXT, committee_url TEXT, committee TEXT, meeting
    # TEXT, party TEXT, person TEXT, meeting_url TEXT, text TEXT);
    meeting_date    = models.DateField()
    committee_url   = models.TextField()
    committee       = models.TextField()
    meeting         = models.TextField()
    party           = models.TextField()
    person          = models.TextField()
    meeting_url     = models.TextField()
    report = models.ForeignKey(PMGCommitteeReport,
        null=True,
        on_delete=models.CASCADE,
        related_name='appearances')
    text            = models.TextField()

class Answer (models.Model):

    # Various values that the processed_code can have
    PROCESSED_PENDING    = 0
    PROCESSED_OK         = 1
    PROCESSED_HTTP_ERROR = 2
    PROCESSED_PROCESSING_ERROR = 3
    PROCESSED_CHOICES = (
        ( PROCESSED_PENDING,    'pending' ),
        ( PROCESSED_OK,         'OK' ),
        ( PROCESSED_HTTP_ERROR, 'HTTP error' ),
        ( PROCESSED_PROCESSING_ERROR, 'Processing error' ),
    )

    # CREATE TABLE answers (matched_to_question TEXT, number_oral TEXT,
    # text TEXT, processed NUMERIC, id INTEGER PRIMARY KEY, name TEXT,
    # language TEXT, url TEXT, house TEXT, number_written TEXT, date TEXT, type TEXT);
    number_oral = models.TextField()
    text = models.TextField()
    processed_code = models.IntegerField( null=False, default=PROCESSED_PENDING, choices=PROCESSED_CHOICES )
    name = models.TextField()
    language = models.TextField()
    url = models.TextField()
    house = models.TextField()
    number_written = models.TextField()
    date = models.DateField()
    type = models.TextField()
    last_sayit_import = models.DateTimeField(blank=True, null=True)

class Question (models.Model):
    answer = models.ForeignKey(Answer,
        null=True,
        on_delete=models.CASCADE,
        related_name='question')
    house = models.TextField()
    session = models.TextField()
    number1 = models.TextField()
    number2 = models.TextField()
    date = models.DateField()
    title = models.TextField()
    question = models.TextField()
    questionto = models.TextField()
    source = models.TextField()
    translated = models.IntegerField()
    document = models.TextField()
    type = models.TextField()
    intro = models.TextField()
    parliament = models.TextField()
    askedby = models.TextField()

    last_sayit_import = models.DateTimeField(blank=True, null=True)
    sayit_section = models.ForeignKey(Section, blank=True, null=True, on_delete=models.PROTECT,
        help_text='Associated Sayit section object, if imported')


#CREATE TABLE completed_documents (`url` string);
