import logging

from django.core.exceptions import ObjectDoesNotExist

from popolo_name_resolver.resolve import ResolvePopoloName
from speeches.models import Speaker

logger = logging.getLogger(__name__)


class AllowedPersonFilter(object):

    def __init__(self, pombola_id_blacklist):
        self.pombola_id_blacklist = set(pombola_id_blacklist or ())

    def is_person_allowed(self, person):
        try:
            pombola_person = person.speaker.pombola_link.pombola_person
        except ObjectDoesNotExist:
            # If there's no corresponding Pombola person, allow the
            # speaker anyway - there may be an existing
            # non-Pombola-associated person for this name.
            return True
        pombola_person_id = pombola_person.id
        return pombola_person_id not in self.pombola_id_blacklist


class ImportZAMixin(object):
    def __init__(self, instance=None, commit=True, pombola_id_blacklist=None, **kwargs):
        super(ImportZAMixin, self).__init__(
            instance=instance,
            commit=commit,
            **kwargs
        )
        self.person_cache = {}
        self.pombola_id_blacklist = pombola_id_blacklist

    def set_resolver_for_date(self, date_string='', date=None):
        self.resolver = ResolvePopoloName(
            date=date,
            date_string=date_string,
            person_filter=AllowedPersonFilter(self.pombola_id_blacklist),
        )

    def get_person(self, name, party):
        cached = self.person_cache.get(name, None)
        if cached:
            return cached

        display_name = name or '(narrative)'

        speaker = None
        person = None

        if name:
            person = self.resolver.get_person(display_name, party)
            if person:
                speaker = person.speaker

        if not speaker:
            try:
                speaker = Speaker.objects.get(instance=self.instance, name=display_name)
            except Speaker.DoesNotExist:
                speaker = Speaker(instance=self.instance, name=display_name)
                if self.commit:
                    speaker.save()

        self.person_cache[name] = speaker
        return speaker
