from flask import request
from itertools import islice
from datetime import datetime
import urllib.parse
import inflect

hosts = {
    'commons': 'commons.wikimedia.org',
    'enwiki': 'en.wikipedia.org',
    'wikidata': 'www.wikidata.org',
}

engine = inflect.engine()

skip_names = {
    'National Gallery'
}

def ordinal(n):
    return "%d%s" % (n, 'tsnrhtdd'[(n / 10 % 10 != 1) * (n % 10 < 4) * n % 10::4])

def chunk(it, size):
    it = iter(it)
    return iter(lambda: tuple(islice(it, size)), ())

def drop_start(s, start):
    assert s.startswith(start)
    return s[len(start):]

def drop_category_ns(s):
    return drop_start(s, 'Category:')

def parse_sitelink(s, start):
    return urllib.parse.unquote(drop_start(s, start)).replace('_', ' ')

def word_contains_letter(word):
    return any(c.isalpha() for c in word)

def also_singular(name):
    names = also_singular_main(name)
    extra = []
    for n in names:
        words = set(n.lower().split())
        for word in 'girl', 'boy':
            if word in words:
                extra.append(word)
        if {'female', 'females', 'women'} & words:
            extra.append('woman')
        if {'male', 'males', 'men'} & words:
            extra.append('man')
    return [n for n in names + extra if n not in skip_names]

def also_singular_main(name):
    '''
    given a singular name return a list of both the plural and singular versions
    just return the name if it isn't singular
    '''
    singular = engine.singular_noun(name.strip('|'))
    if not singular:
        return [name]
    n, s = name.lower(), singular.lower()
    if (n == s or
            n.replace('paintings', '') == s.replace('painting', '') or
            n == 'venus' and s == 'venu'):
        return [name]
    return [name, singular]

def wiki_url(title, site, ns=None):
    host = hosts[site]
    url_ns = ns + ':' if ns else ''
    if not title:
        return
    if title[0].islower():
        title = title[0].upper() + title[1:]

    return f'https://{host}/wiki/' + url_ns + urllib.parse.quote(title.replace(' ', '_'))

def get_int_arg(name):
    if name in request.args and request.args[name].isdigit():
        return int(request.args[name])

def format_time(time_value, precision):
    # FIXME handle dates like '1965-04-00T00:00:00Z'
    # FIXME handle BC dates properly, "120 B.C." instead of "-120"
    year = None
    if '-00' in time_value:
        # can't be represented as python datetime
        year = int(time_value[:time_value.find('-', 1)])
    else:
        try:
            t = datetime.strptime(time_value[1:], "%Y-%m-%dT%H:%M:%SZ")
        except ValueError:
            return time_value
        year = t.year

    if precision == 9:
        return str(year)
    if precision == 8:
        return f'{year}s'
    if precision == 7:
        return f'{ordinal((year // 100) + 1)} century'
    if precision == 6:
        return f'{ordinal((year // 1000) + 1)} millennium'

    return time_value
