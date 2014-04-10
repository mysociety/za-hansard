from optparse import make_option

from popit_resolver.resolve import SetupEntities
from speeches.management.import_commands import ImportCommand

class ImportCommand(ImportCommand):
    option_list = ImportCommand.option_list + (
        make_option('--popit_url', action='store', default=None, help="PopIt API base url - eg 'http://foo.popit.mysociety.org/api/v0.1/'"),
    )

    def handle(self, *args, **kwargs):
        SetupEntities(kwargs['popit_url']).init_popit_data()
        return super(ImportCommand, self).handle(*args, **kwargs)
