import logging

from popit_resolver.resolve import ResolvePopitName

from popit.models import ApiInstance
from speeches.models import Speaker

logger = logging.getLogger(__name__)

class ImportZAMixin(object):
    def __init__(
        self,
        instance=None,
        commit=True,
        popit_url=None,
        popit_id_blacklist=None,
        person_accept_check=lambda person, date: True,
        **kwargs
        ):
        self.instance = instance
        self.commit = commit
        self.ai, _ = ApiInstance.objects.get_or_create(url=popit_url)
        self.person_cache = {}
        self.popit_id_blacklist = set(popit_id_blacklist or ())
        # Make sure that there are no speakers associated with
        # blacklisted PopIt IDs:
        Speaker.objects.filter(person__popit_id__in=self.popit_id_blacklist) \
            .update(person=None)

        self.person_accept_check = person_accept_check

    def set_start_date(self, date=None):
        self.start_date=date
        self.resolver = ResolvePopitName(date=date)

    def get_person(self, name, party):
        cached = self.person_cache.get(name)
        if cached:
            return cached

        speaker = None

        # We'd better make this just a normal variable, so we don't get self passed to it.
        person_accept_check = self.person_accept_check

        if name:
            popit_person = self.resolver.get_person(name, party)
            if popit_person:
                if popit_person.popit_id in self.popit_id_blacklist:
                    message = u" - Ignoring blacklisted popit_id {0}"
                    logger.info(message.format(popit_person.popit_id))
                elif person_accept_check(popit_person, self.start_date):
                    try:
                        speaker = Speaker.objects.get(
                            instance = self.instance,
                            person = popit_person)
                    except Speaker.DoesNotExist:
                        speaker = Speaker(
                            instance=self.instance,
                            name=name,
                            person=popit_person)

                        if self.commit:
                            speaker.save()
                    self.person_cache[name] = speaker
            else:
                logger.info(" - Failed to get user %s" % name)

        return speaker
