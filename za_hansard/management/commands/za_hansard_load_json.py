from speeches.management.import_commands import ImportCommand
from za_hansard.importers.import_json import ImportJson

class Command(ImportCommand):
    importer_class = ImportJson
    document_extension = 'txt'
