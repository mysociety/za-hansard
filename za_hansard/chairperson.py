import re

from bs4 import NavigableString

# For checking regressions, just a note that the following committee
# meeting IDs are known to work:
#   8655
#   8567
#   8593
#   6040
#   6256
#   5593
#   8564
#   8220
#   10052
#   9956
#   7941

def get_earliest_text(span):
    children = list(span.children)
    if not children:
        return None
    first = children[0]
    if isinstance(first, NavigableString):
        return first
    if first.name != 'span':
        return None
    return get_earliest_text(first)

def get_split_across_spans(soup):
    """Extract the chairperson name, e.g. for meetings with IDs: 8655, 8567)"""

    p = soup.find('p', class_="MsoNormal")
    if not p:
        return
    spans = p.find_all('span')
    if len(spans) < 2:
        return
    span0_children = list(spans[0].children)
    if not span0_children:
        return
    span0_last_child = span0_children[-1]
    if not isinstance(span0_last_child, NavigableString):
        return
    if not re.search(r'(?ms)Chairperson:\s*$', span0_last_child):
        return
    s = get_earliest_text(spans[1])
    return s.strip()

def get_bold_and_sibling(soup):
    """e.g. for meeting with ID: 8593"""

    b = soup.find('b', text=re.compile('^\s*Chairperson\s*:?\s*$'))
    if not b:
        return
    after = b.next_sibling
    if not isinstance(after, NavigableString):
        return
    m = re.search(r'^(?ms)[\s\n:]*(.*)', after)
    if not m:
        return
    return m.group(1).strip()

def should_ignore_tag(tag):
    """In 8820 there's a extra <span class="SpellE"> around part of the name

    In 10052 it's 'spelle'"""

    classes = tag.get('class', [])
    return tag.name == 'span' and (
        'SpellE' in classes or
        'spelle' in classes or
        (not classes)
    )

def merge_with_adjacent(ns, with_element_after=True):
    if not isinstance(ns, NavigableString):
        return
    adjacent = ns.next_sibling if with_element_after else ns.previous_sibling
    if adjacent is None or not isinstance(adjacent, NavigableString):
        return
    if with_element_after:
        squashed = NavigableString(ns + adjacent)
    else:
        squashed = NavigableString(adjacent + ns)
    adjacent.extract()
    ns.replace_with(squashed)

def strip_tags(soup):
    """Replace any useless spans with their contents

    A modified version of http://stackoverflow.com/a/3225671/223092
    The issue with that one is that you can end up with two adjancent
    or three NavigableString objects; I'd like them to be coalesced
    because otherwise when you do get_text with a join string you end
    up with spurious joins in the middle of strings. """

    for tag in soup.find_all(True):
        if should_ignore_tag(tag):
            s = ""
            for c in tag.contents:
                if not isinstance(c, NavigableString):
                    c = strip_tags(unicode(c))
                s += unicode(c)
            previous_sibling = tag.previous_sibling
            next_sibling = tag.next_sibling
            tag.replace_with(s)
            merge_with_adjacent(previous_sibling, with_element_after=True)
            merge_with_adjacent(next_sibling, with_element_after=False)
    return soup

def get_from_text_version(soup):
    """e.g. for meeting with ID: 6040, 8564"""

    soup = strip_tags(soup)
    text = soup.get_text('_')
    m = re.search(
        r'_\s*(?:Acting\s*)?Chair(?:person)?\s*:?[\s_]*([^_]*)_[\s_]*Documents?\s+handed\s+out',
        text,
        re.IGNORECASE,
    )
    if m:
        return m.group(1).strip()
    # Another thing to check is that sometimes we just get a mention
    # of the chairperson in the body of the text, like:
    # 'The Chairperson, Mr Holomisa, informed the committee' (from 6256)
    # (You need to allow '.' in the name because the title 'Adv.' is sometimes
    # used.)
    m = re.search(
        r'The\s+[Cc]hairperson\s*,\s*([a-zA-Z \.-]+)\s*,',
        text,
    )
    if m:
        return m.group(1).strip()
    # Another possibility is that the chairperson is introduced with:
    # "The meeting was Chaired by ..." (e.g. 5593)
    m = re.search(
        r'_\s*The meeting was [cC]haired by ([^_]*)_',
        text
    )
    if m:
        return m.group(1).strip()
