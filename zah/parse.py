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

    akomaNtoso = E.akomaNtoso(
            E.debate(
                E.preface()))
    current = akomaNtoso.debate.preface

    hasDate = False
    hasTitle = False
    hasAssembled = False
    hasPrayers = False
    subSectionCount = 0

    @classmethod
    def parse(cls, document_path):
        
        antiword = subprocess.Popen(
                ['antiword', document_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT)
        if antiword.returncode:
            # e.g. not 0 (success) or None (still running) so presumably an error
            raise Error("antiword failed %d" % antiword.returncode)

        def cleanLine(line):
            line = line.rstrip(' _\n')
            # NB: string.printable won't filter unicode correctly...
            line = filter(lambda x: x in string.printable, line)
            return line

        lines = imap(cleanLine, iter(antiword.stdout.readline, b''))

        def break_paras(line):
            return len(line) > 0

        fst = lambda(a,_): a
        snd = lambda(_,b): b

        groups = groupby(lines, break_paras)
        paras = imap(snd, ifilter(fst, groups))

        obj = ZAHansardParser()

        for para in paras:
            p = list(para)
            ret = obj.parseLine( p )
            if not ret:
                print >> sys.stderr, "Failed at %s" % p[0]
                break
                # continue

        return obj

    def parseLine(self, p):

        E = self.E

        # DECORATORS
        def singleLine(f):
            def singleLine_(p):
                if len(p) != 1:
                    return False
                return f(p[0])
            return singleLine_

        def para(f):
            def para_(p):
                p = ' '.join(p)

                return f(p)
            return para_

        # PARSERS

        @singleLine
        def isDate(line):
            if self.hasDate:
                return False
            try:
                date = datetime.strptime(line, '%A, %d %B %Y')
                elem = E.p(
                        datetime.strftime(date, '%A, '),
                        E.docDate(datetime.strftime(date, '%d %B %Y'),
                            date=datetime.strftime(date, '%Y-%m-%d')))
                self.current.append(elem)
                self.hasDate = True
                return True
            except:
                return False

        @singleLine
        def isTitle(line):
            if re.search(r'[a-z]', line):
                return False
            line = line.lstrip()
            if self.hasTitle:
                # we already have a main title, so this is a subsection
                if self.subSectionCount:
                    self.current = self.current.getparent()
                self.subSectionCount += 1
                elem = E.debateSection(
                    E.narrative(line),
                    id='dbs%d' % self.subSectionCount)
                self.current.append(elem)
                self.current = elem
            else:
                elem = E.debateBody(
                        E.debateSection(
                            E.heading(line),
                            id='db0'))
                self.akomaNtoso.debate.append( elem )
                self.current = elem.debateSection
                self.hasTitle = True
            return True

        @para
        def assembled(p):
            if self.hasAssembled:
                return
            ret = re.search(r'^(.*(?:assembled|met)(?: in .*)? at )(\d+:\d+)\.?$', p)
            if ret:
                try:
                    groups = ret.groups()
                    time = datetime.strptime(groups[1], '%H:%M').time()
                    assembled = datetime.combine(header['date'], time)
                    elem = E.p(
                            groups[0],
                            E.recordedTime(
                                groups[1],
                                time= assembled.isoformat()
                            ))
                    self.current.append(elem)
                    self.hasAssembled = True
                    return True
                except:
                    return

        @para
        def prayers(p):
            if self.hasPrayers:
                return
            if re.search(r'^(.* prayers or meditation.)$', p):
                elem = E.prayers(p)
                self.current.append(elem)
                self.hasPrayers = True
                return True

        @para
        def speech(p):
            name_regexp = r'^((?:[A-Z][a-z]* )?[A-Z ]+):\d*(.*)'
            ret = re.search(name_regexp, p)
            if ret:
                (name, speech) = ret.groups()
                id = self.getOrCreateSpeaker(name)
                elem = E.speech(
                        E('from',  name ),
                        E.p(speech),
                        by='#%s' % id)
                
                if etree.QName(self.current.tag).localname == 'speech':
                    self.current = self.current.getparent()
                self.current.append(elem)
                return True

        @para
        def continuation(p):
            self.current.append( E.p( p ) )
            return True

        funcs = [
                isDate,
                isTitle,
                assembled,
                prayers,
                speech,
                continuation,
                ]

        for f in funcs:
            ret = f(p)
            if ret:
                return ret

    def getOrCreateSpeaker(self, name):
        id = re.sub('\W+', '-', name.lower())
        return id
