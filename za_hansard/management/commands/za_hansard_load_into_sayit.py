import pprint
import datetime
import pytz
import time
import sys

from speeches.importers.import_akomantoso import ImportAkomaNtoso
from speeches.models import Section
from za_hansard.models import Source
from popit.models import ApiInstance
from instances.models import Instance

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from optparse import make_option

class Command(BaseCommand):
    help = 'Import available hansards into sayit'
    option_list = BaseCommand.option_list + (
        #make_option('--reimport',
            #default=False,
            #action='store_true',
            #help='Reimport already imported speeches',
        #),
        make_option('--id',
            type='str',
            help='Import a given id',
        ),
        make_option('--instance',
            type='str',
            default='default',
            help='Instance to import into',
        ),
        make_option('--limit',
            default=0,
            type='int',
            help='limit query (default 0 for none)',
        ),
    )

    def handle(self, *args, **options):
        limit = options['limit']

        instance = None
        try:
            instance = Instance.objects.get(label=options['instance'])
        except Instance.DoesNotExist:
            raise CommandError("Instance specified not found (%s)" % options['instance'])

        sources = Source.objects.filter(last_processing_success__isnull = False)
        sources = sources.filter(sayit_section__isnull = True)

        if options['id']:
            sources = sources.filter(id = options['id'])

        sections = []

        sources = sources[:limit] if limit else sources.all()
        for s in sources:

            path = s.xml_file_path()
            if not path:
                continue

            importer = ImportAkomaNtoso( instance=instance )
            try:
                self.stdout.write("TRYING %s\n" % path)
                section = importer.import_document(path)
                sections.append(section)
                s.sayit_section = section
                s.last_sayit_import = datetime.datetime.now(pytz.utc)
                s.save()

            except Exception as e:
                self.stderr.write('WARN: failed to import %d: %s' %
                    (s.id, str(e)))

            # Get or create the sections above the one we just created and put it in there
            parent = Section.objects.get_or_create_with_parents(instance=instance, titles=s.section_parent_titles)
            section.parent = parent
            section.save()

        self.stdout.write('Imported %d / %d sections\n' %
            (len(sections), len(sources)))

        self.stdout.write( str( [s.id for s in sections] ) )
        self.stdout.write( '\n' )
