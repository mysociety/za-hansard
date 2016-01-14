from za_hansard.importers.import_json import ImportJson

from pombola.core.models import Position


class ImportJsonZACommittee(ImportJson):
    def person_accept_check(self, popit_person):
        person_id = int(popit_person.popit_id.rsplit(':', 1)[1])

        # We want to know that this person is a current member of the
        # National Assembly on the date of the meeting

        qs = (Position.objects
              .filter(
                person__id=person_id,
                title__slug='member',
                organisation__slug='national-assembly',
                )
              .currently_active(self.start_date)
              )

        return qs.exists()

