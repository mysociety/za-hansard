import re
import docx
import subprocess
from itertools import imap, ifilter, groupby

import sys

from datetime import datetime 
from lxml import etree
from lxml import objectify

class ZAHansardParser2(object):

    def parse(self, document_path):
        
        antiword = subprocess.Popen(
                ['antiword', document_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT)
        if antiword.returncode:
            # e.g. not 0 (success) or None (still running) so presumably an error
            raise Error("antiword failed %d" % antiword.returncode)

        E = objectify.ElementMaker(
                annotate=False,
                namespace="http://docs.oasis-open.org/legaldocml/ns/akn/3.0/CSD03",
                nsmap={None : "http://docs.oasis-open.org/legaldocml/ns/akn/3.0/CSD03"},
                )

        akomaNtoso = E.akomaNtoso(
                E.debate(
                    E.preface()))
        current = akomaNtoso.debate.preface

        name_regexp = r'((?:[A-Z][a-z]* )?[A-Z ]+):'

        header = {
                'date': None,
                'title': None,
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

        def get_element(p):
            p = list(p)
            if len(p) == 1:
                line = p[0]
                print >> sys.stderr, line
                if not header['date']:
                    try:
                        date = datetime.strptime(line, '%A, %d %B %Y')
                        header['date'] = date
                        elem = E.p(
                                datetime.strftime(date, '%A, '),
                                E.docDate(datetime.strftime(date, '%d %B %Y'),
                                    date=datetime.strftime(date, '%Y-%m-%d')))
                        return (elem, None)
                    except:
                        pass
            else:
                line = p[0]

            # not yet handled!
            # print >> sys.stderr, "EEEEEK! %s" % str(p)
            return (None, None)

        for p in paras:
            (elem, where) = get_element(p)
            if elem is None:
                continue
            if where == 'pop':
                current = current.getparent()
            parent = current

            current.append(elem)
            if where == 'push':
                current = elem

        return akomaNtoso
