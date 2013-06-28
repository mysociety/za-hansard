import re
import docx
import subprocess
from itertools import imap, ifilter, groupby

import sys

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

        for p in paras:
            elem_data = self.get_element( list(p), header.copy() )
            if not elem_data:
                continue
            (elem, where, header) = elem_data
            if where == 'pop':
                current = current.getparent()
            parent = current

            current.append(elem)
            if where == 'push':
                current = elem

        return akomaNtoso

    def get_element(self, p, header):

        E = self.E

        def singleLine(f):
            def new_f(p, header):
                if len(p) != 1:
                    return False
                return f(p[0], header)
            return new_f

        @singleLine
        def isDate(line,header):
            if header['date']:
                return False
            try:
                date = datetime.strptime(line, '%A, %d %B %Y')
                header['date'] = date
                elem = E.p(
                        datetime.strftime(date, '%A, '),
                        E.docDate(datetime.strftime(date, '%d %B %Y'),
                            date=datetime.strftime(date, '%Y-%m-%d')))
                return (elem, None, header)
            except Exception as e:
                print e
                return False

        funcs = [
                isDate,
                ]

        for f in funcs:
            ret = f(p, header)
            if ret:
                return ret
