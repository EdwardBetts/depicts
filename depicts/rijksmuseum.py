import requests
import lxml.html
import os
import re

re_url = re.compile(r'^https://www.rijksmuseum.nl/(?:nl/collectie|en/collection)/([^/]+)$')

def get_html(catalog_id):
    filename = f'cache/rijksmuseum_{catalog_id}.html'
    en_url = 'https://www.rijksmuseum.nl/en/collection/' + catalog_id

    if os.path.exists(filename):
        html = open(filename).read()
    else:
        r = requests.get(en_url)
        html = r.text
        open(filename, 'w').write(html)

    return html

def parse_html(html):
    root = lxml.html.fromstring(html)
    keywords = [a.text for a in root.findall('.//a[@href]')
                if 'f.classification.iconClassDescription.sort' in a.get('href')]

    return {
        'institution': 'Rijksmuseum',
        'keywords': keywords,
    }

def get_catalog(url):
    catalog_id = re_url.search(url).group(1)

    return parse_html(get_html(catalog_id))
