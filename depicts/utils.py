from itertools import islice
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


