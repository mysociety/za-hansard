from za_hansard.importers.import_json import ImportJson

from pombola.core.models import Position


class ImportJsonZACommittee(ImportJson):
    def set_resolver_for_date(self, date_string='', date=None):
        # FIXME - Highjacking this method to get self.date set.
        # Things should be renamed.

        self.date = date
        super(ImportJsonZACommittee, self).set_resolver_for_date(date_string, date)

    def person_accept_check(self, popit_person):
        person_id = int(popit_person.popit_id.rsplit(':', 1)[1])

        # We want to know that this person is a current member of the
        # National Assembly on the date of the meeting

        qs = Position.objects.filter(
            person__id=person_id,
            title__slug='member',
            organisation__slug='national-assembly',
            ).currently_active(self.date)

        return qs.exists()



