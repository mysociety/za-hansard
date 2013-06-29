import re
import docx
import subprocess
import string

import sys

from itertools import imap, ifilter, groupby
from datetime import datetime 
from lxml import etree
from lxml import objectify

class ZAHansardParser(object):

    E = objectify.ElementMaker(
            annotate=False,
            namespace="http://docs.oasis-open.org/legaldocml/ns/akn/3.0/CSD03",
            nsmap={None : "http://docs.oasis-open.org/legaldocml/ns/akn/3.0/CSD03"},
            )

    def parse(self, document_path):
        
        antiword = subprocess.Popen(
                ['antiword', document_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT)
        if antiword.returncode:
            # e.g. not 0 (success) or None (still running) so presumably an error
            raise Error("antiword failed %d" % antiword.returncode)

        E = self.E
        akomaNtoso = E.akomaNtoso(
                E.debate(
                    E.preface()))
        current = akomaNtoso.debate.preface

        header = {
                'date': None,
                'title': None,
                'subSections': 0,
                'assembled': None,
                'prayers': False,
                }

        lines = imap(lambda l: l.rstrip(' _\n'), 
                iter(antiword.stdout.readline, b''))

        def break_paras(line):
            return len(line) > 0

        fst = lambda(a,_): a
        snd = lambda(_,b): b

        groups = groupby(lines, break_paras)
        paras = imap(snd, ifilter(fst, groups))

        for para in paras:
            p = list(para)
            ret = self.parseLine( p, header, akomaNtoso, current )
            if not ret:
                print >> sys.stderr, "Failed at %s" % p[0]
                break
                # continue
            [current] = ret

        return akomaNtoso

    def parseLine(self, p, header, akomaNtoso, current):

        E = self.E

        # DECORATORS
        def singleLine(f):
            def singleLine_(p, header, akomaNtoso, current):
                if len(p) != 1:
                    return False
                return f(p[0], header, akomaNtoso, current)
            return singleLine_

        def para(f):
            def para_(p, header, akomaNtoso, current):
                p = ' '.join(p)
                p = re.sub(r'\u00a0', '&nbsp;', p)

                p = filter(lambda x: x in string.printable, p)

                return f(p, header, akomaNtoso, current)
            return para_

        @singleLine
        def isDate(line, header, akomaNtoso, current):
            if header['date']:
                return False
            try:
                date = datetime.strptime(line, '%A, %d %B %Y')
                header['date'] = date
                elem = E.p(
                        datetime.strftime(date, '%A, '),
                        E.docDate(datetime.strftime(date, '%d %B %Y'),
                            date=datetime.strftime(date, '%Y-%m-%d')))
                current.append(elem)
                return [current]
            except:
                return False

        @singleLine
        def isTitle(line, header, akomaNtoso, current):
            if re.search(r'[a-z]', line):
                return False
            line = line.lstrip()
            if header['title']:
                # we already have a main title, so this is a subsection
                if header['subSections']:
                    current = current.getparent()
                header['subSections'] += 1
                elem = E.debateSection(
                    E.narrative(line),
                    id='dbs%d' % header['subSections'])
                current.append(elem)
                return [elem]
            else:
                header['title'] = line
                elem = E.debateBody(
                        E.debateSection(
                            E.heading(line),
                            id='db0'))
                akomaNtoso.debate.append( elem )
                return [elem.debateSection]

        @para
        def assembled(p, header, akomaNtoso, current):
            if header['assembled']:
                return
            ret = re.search(r'^(.*(?:assembled|met)(?: in .*)? at )(\d+:\d+)\.?$', p)
            if ret:
                try:
                    groups = ret.groups()
                    time = datetime.strptime(groups[1], '%H:%M').time()
                    assembled = datetime.combine(header['date'], time)
                    header['assembled'] = assembled
                    elem = E.p(
                            groups[0],
                            E.recordedTime(
                                groups[1],
                                time= assembled.isoformat()
                            ))
                    current.append(elem)
                    return [current]
                except:
                    return

        @para
        def prayers(p, header, akomaNtoso, current):
            if header['prayers']:
                return
            if re.search(r'^(.* prayers or meditation.)$', p):
                header['prayers'] = True
                elem = E.prayers(p)
                current.append(elem)
                return [current]

        @para
        def speech(p, header, akomaNtoso, current):
            name_regexp = r'^((?:[A-Z][a-z]* )?[A-Z ]+):\d*(.*)'
            ret = re.search(name_regexp, p)
            if ret:
                (name, speech) = ret.groups()
                id = self.getOrCreateSpeaker(name, akomaNtoso)
                elem = E.speech(
                        E.From( name ),
                        E.p(speech),
                        by='#%s' % id)
                
                if etree.QName(current.tag).localname == 'speech':
                    current = current.getparent()
                current.append(elem)
                return [elem]

        @para
        def continuation(p, header, akomaNtoso, current):
            print >> sys.stderr, "[%s]" % p
            current.append( E.p( p ) )
            return [current]

        funcs = [
                isDate,
                isTitle,
                assembled,
                prayers,
                speech,
                continuation,
                ]

        for f in funcs:
            ret = f(p, header, akomaNtoso, current)
            if ret:
                return ret

    def getOrCreateSpeaker(self, name, akomaNtoso):
        id = re.sub('\W+', '-', name.lower())
        return id
