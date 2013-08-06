import re
import subprocess
import string

import sys, os

from itertools import imap, ifilter, groupby
from datetime import datetime 
from lxml import etree
from lxml import objectify

class DateParseException(Exception):
    pass

class ConversionException(Exception):
    pass

class ZAHansardParser(object):

    E = objectify.ElementMaker(
            annotate=False,
            namespace="http://docs.oasis-open.org/legaldocml/ns/akn/3.0/CSD03",
            nsmap={None : "http://docs.oasis-open.org/legaldocml/ns/akn/3.0/CSD03"},
            )

    def __init__(self):
        E = self.E
        self.akomaNtoso = E.akomaNtoso(
                E.debate(
                    E.meta(),
                    E.preface()))
        self.current = self.akomaNtoso.debate.preface

        self.hasDate = False
        self.date = None
        self.hasTitle = False
        self.hasAssembled = False
        self.hasArisen = False
        self.hasPrayers = False
        self.subSectionCount = 0
        self.speakers = {}

    @classmethod
    def parse(cls, document_path):
        
        antiword = subprocess.Popen(
                ['antiword', document_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT)
        (stdoutdata, stderrdata) = antiword.communicate()
        if antiword.returncode:
            # e.g. not 0 (success) or None (still running) so presumably an error
            raise ConversionException("Could not convert %s (%s)" % (document_path, stdoutdata.rstrip()))

        def cleanLine(line):
            line = line.rstrip(' _\n')
            # NB: string.printable won't filter unicode correctly...
            line = filter(lambda x: x in string.printable, line)
            return line

        # lines = imap(cleanLine, iter(antiword.stdout.readline, b''))
        lines = imap(cleanLine, iter(stdoutdata.split('\n')))

        def break_paras(line):
            # FIRST we handle exceptions:
            # NB: these lines should probably actually be included with their respective heading
            if re.match( r'\s*\((Member\'?s? [sS]tatement|Minister\'s? [Rr]esponse\))', line ):
                return line # distinct from True or False, but a True value

            # An ALL CAPS heading might be on the first line of a new page and therefore not be separated
            # by blank lines
            if re.match( r'\s*[A-Z]+', line ) and not re.search( r'[a-z]', line ):
                return "TITLE"

            # FINALLY we just swap between True and False for full and blank lines, to chunk into paragraphs
            return len(line) > 0

        fst = lambda(a,_): a
        snd = lambda(_,b): b

        groups = groupby(lines, break_paras)
        nonEmpty = ifilter(fst, groups)
        paras = imap(snd, nonEmpty)

        obj = ZAHansardParser()

        E = obj.E
        # TODO: instead of ctime use other metadata from source document?
        # ctime = datetime.fromtimestamp(os.path.getctime(document_path)).strftime('%Y-%m-%d')
        today = datetime.now().date().strftime('%Y-%m-%d')

        obj.akomaNtoso.debate.meta.append(
            E.identification(
                E.FRBRWork(
                    E.FRBRthis(),
                    E.FRBRuri(),
                    E.FRBRdate( date=today,  name='generation' ),
                    E.FRBRauthor( href='#za-parliament'), # as='#author' # XXX
                    E.FRBRcountry( value='za' ),
                ),
                E.FRBRExpression(
                    E.FRBRthis(),
                    E.FRBRuri(),
                    E.FRBRdate( date=today,  name='markup' ),
                    E.FRBRauthor( href='#za-parliament'), # as='#editor' # XXX
                    E.FRBRlanguage( language='eng' ),
                ),
                E.FRBRManifestation(
                    E.FRBRthis(),
                    E.FRBRuri(),
                    E.FRBRdate( date=today, name='markup' ),
                    E.FRBRauthor( href='#mysociety'), # as='#editor' # XXX
                ),
                source='#mysociety'),
            )
        obj.akomaNtoso.debate.meta.append( 
                E.references(
                    E.TLCOrganization(
                        id='za-parliament',
                        showAs='ZA Parliament',
                        href='http://www.parliament.gov.za/',
                        ),
                    E.TLCOrganization(
                        id='mysociety',
                        showAs='MySociety',
                        href='http://www.mysociety.org/',
                        ),
                    source='#mysociety'))

        for para in paras:
            p = list(para)
            if not obj.parseLine( p ):
                raise Exception("Parsing failed at %s" % p[0])
                # break
                # continue

        return obj

    def setTitle(self, line):
        E = self.E
        line = line.lstrip().replace( '\n', '')
        elem = E.debateBody(
                E.debateSection(
                    E.heading(line, id='dbh0'),
                    id='db0',
                    name=self.slug(line)))
        self.akomaNtoso.debate.append( elem )
        self.akomaNtoso.debate.set('name', line)
        self.current = elem.debateSection
        self.hasTitle = True

    def createSubsection(self, line):
        E = self.E
        line = line.lstrip().replace( '\n', '')
        self.subSectionCount += 1
        elem = E.debateSection(
            E.heading(line,
                id='dbsh%d'% self.subSectionCount),
            id='dbs%d' % self.subSectionCount,
            name=self.slug(line))
        self.akomaNtoso.debate.debateBody.debateSection.append(elem)
        self.current = elem

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
                p = re.compile(r'\s+').sub(' ', p)
                return f(p)
            return para_

        # PARSERS

        @singleLine
        def isDate(line):
            if self.hasDate:
                return False
            try:
                match = re.compile(r'(\d+)[ ,]+(\w+)[ ,]+(\d+)$').search(line)
                if not match:
                    raise DateParseException("Couldn't match date in %s" % line)
                date = datetime.strptime(' '.join(match.groups()), '%d %B %Y')

                date_xml = date.strftime('%Y-%m-%d')
                elem = E.p(
                        datetime.strftime(date, '%A, '),
                        E.docDate(date.strftime('%d %B %Y'),
                            date=date_xml))
                self.current.append(elem)
                self.hasDate = True
                self.date = date

                identification = self.akomaNtoso.debate.meta.identification
                identification.FRBRWork.FRBRthis.set('value', '/za/debaterecord/%s/main' % date_xml)
                identification.FRBRWork.FRBRuri.set('value', '/za/debaterecord/%s' % date_xml)
                identification.FRBRExpression.FRBRthis.set('value', '/za/debaterecord/%s/eng@/main' % date_xml)
                identification.FRBRExpression.FRBRuri.set('value', '/za/debaterecord/%s/eng@' % date_xml)
                identification.FRBRManifestation.FRBRthis.set('value', '/za/debaterecord/%s/eng@/main.xml' % date_xml)
                identification.FRBRManifestation.FRBRuri.set('value', '/za/debaterecord/%s/eng@.akn' % date_xml)

                return True
            except Exception as e:
                raise e
                return False

        @para
        def isTitle(line):
            if re.search(r'[a-z]', line.replace('see col', '')):
                return False
            line = ( line
                    .lstrip()
                    .replace( '\n', ''))
            if self.hasTitle:
                self.createSubsection(line)
            else:
                self.setTitle(line)
            return True

        @singleLine
        def isTitleParenthesis(line):
            if re.match(r'\s*\(.*\)\.?$', line):
                if etree.QName(self.current.tag).localname == 'debateSection':
                    # munging existing text in Objectify seems to be frowned upon.  Ideally refactor
                    # this to be more functionl to avoid having to do call private _setText method...
                    self.current.heading._setText( '%s %s' % (self.current.heading.text, line.lstrip() ))
                    return True
            return False

        @para
        def assembled(p):
            if self.hasAssembled:
                return
            ret = re.search(r'^(.*(?:assembled|met)(?: in .*)? at )(\d+:\d+)\.?$', p)
            if ret:
                try:
                    groups = ret.groups()
                    time = datetime.strptime(groups[1], '%H:%M').time()
                    # assembled = datetime.combine(self.date, time).replace(tzinfo=self.tz)
                    assembled = time
                    elem = E.p(
                            groups[0],
                            E.recordedTime(
                                groups[1],
                                time= assembled.isoformat() 
                            ))
                    self.current.append(elem)
                    self.hasAssembled = True
                    return True
                except Exception as e:
                    raise e
                    return

        @para
        def arose(p):
            if self.hasArisen:
                return
            ret = re.search(r'^(.*(?:rose) at )(\d+:\d+)\.?$', p)
            if ret:
                try:
                    groups = ret.groups()
                    time = datetime.strptime(groups[1], '%H:%M').time()
                    # arose = datetime.combine(self.date, time).replace(tzinfo = self.tz)
                    arose = time
                    elem = E.adjournment(
                            E.p(
                                groups[0],
                                E.recordedTime(
                                    groups[1],
                                    time= arose.isoformat()
                                )),
                            id='adjournment')
                    self.current.getparent().append(elem)
                    self.hasArisen = True
                    return True
                except:
                    return

        @para
        def prayers(p):
            if self.hasPrayers:
                return
            if re.search(r'^(.* prayers or meditation.)$', p):
                elem = E.prayers(
                        E.p(p), 
                        id='prayers')
                self.current.append(elem)
                self.hasPrayers = True
                return True

        @para
        def speech(p):
            name_regexp = r'((?:[A-Z][a-z]+ )[A-Z -]+(?: \(\w+\))?):\s*(.*)'
            ret = re.match(name_regexp, p)
            if ret:
                (name, speech) = ret.groups()
                # print >> sys.stderr, name
                id = self.getOrCreateSpeaker(name)
                elem = E.speech(
                        E('from',  name ),
                        E.p(speech.lstrip()),
                        by='#%s' % id)
                
                if etree.QName(self.current.tag).localname == 'speech':
                    self.current = self.current.getparent()
                self.current.append(elem)
                self.current = elem
                return True

        @para
        def continuation(p):
            if not self.hasTitle:
                self.setTitle(p.upper())
            elif not self.subSectionCount:
                self.createSubsection(p.upper())
            else:
                # TODO: this needs some more thought to emit subheadings if appropriate
                tag = 'p'
                self.current.append( E(tag, p.lstrip() ) )
            return True

        funcs = [
                isDate,
                isTitle,
                isTitleParenthesis,
                assembled,
                arose,
                prayers,
                speech,
                continuation,
                ]

        for f in funcs:
            ret = f(p)
            if ret:
                return ret

    def getOrCreateSpeaker(self, name):
        speaker = self.speakers.get(name)
        if speaker:
            return speaker
        slug = self.slug(name)
        self.speakers[name] = slug
        E = self.E
        self.akomaNtoso.debate.meta.references.append(
                E.TLCPerson(
                    id=slug,
                    showAs=name,
                    href='http://dummy/popit/path/%s' % slug ))
        return slug

    def slug(self, line):
        return re.sub('\W+', '-', line.lower())

