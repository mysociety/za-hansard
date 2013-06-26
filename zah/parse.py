import re

from datetime import datetime 
from bs4 import BeautifulSoup

class ZAHansardParser(object):

    def parse(self, html):
        soup = BeautifulSoup(html)

        title = soup.find('h1', class_ = 'title').string
        node = soup.find('div', class_ = 'node')
        # taxonomy?
        content = node.find('div', class_ = 'content')

        dt = content.find('div', class_='field-field-meeting-date')
        date_string = dt.get_text('', strip=True)
        date = datetime.strptime( dt.find('span', class_ = 'date-display-single').get_text('', strip=True), '%d %b %Y' )

        current_speaker = None
        current_speech  = None
        speeches = []

        name_regexp = r'((?:[A-Z][a-z]* )?[A-Z ]+):'

        for p in content.find_all('p'):
            string = p.string
            if not string:
                continue
            if string == u'\xa0':
                continue
            matched = re.match(name_regexp, string)
            if matched:
                speaker = matched.group(1)
                current_speaker = self.getCanonicalPerson(speaker)
                string = string[matched.end():]

                current_speech = ZAHansardSpeech(
                        speaker = current_speaker,
                        from_ = speaker,
                        p = [ string ],
                        )
                speeches.append(current_speech)
                continue

            # FIXME HACK HACK! for now, just append to current speech!
            if current_speech:
                current_speech.append_p(string)

        return {
                'title':       title,
                'date_string': date_string,
                'date' :       date,
                'speeches':    speeches,
                }

    def getCanonicalPerson(self, name):
        # TODO, connect to PopIt
        return name

class ZAHansardSpeech (object):

    def __init__(self, speaker=None, from_='', p = []):
        self.speaker = speaker
        self.from_   = from_
        self.p       = p

    def __repr__(self):
        return (
                '%s(speaker = "%s", from_ = "%s", p = %s)' %
                   (self.__class__.__name__,
                    self.speaker,
                    self.from_,
                    self.p)
                )

    def append_p(self, string):
        self.p.append(string)
