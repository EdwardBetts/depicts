import requests
import lxml.html
import os
import re

re_url = re.compile(r'www.museodelprado.es/(.+)$')

def get_html(url):
    catalog_id = re_url.search(url).group(1).replace('/', '_')

    filename = f'cache/museodelprado_{catalog_id}.html'

    if os.path.exists(filename):
        html = open(filename).read()
    else:
        r = requests.get(url)
        html = r.text
        open(filename, 'w').write(html)

    return html

def parse_html(html):
    root = lxml.html.fromstring(html)

    keywords = []
    for h2 in root.findall('.//h2'):
        if not h2.text or h2.text.strip() != 'Displayed objects':
            continue
        div = h2.getparent()
        for keyword_span in div.findall('.//span[@property]'):
            keywords.append(keyword_span.text)

    if not keywords:
        return {}

    return {
        'institution': 'Museo del Prado',
        'keywords': keywords,
    }

def get_catalog(url):
    return parse_html(get_html(url))
