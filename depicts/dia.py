import requests
import lxml.html
import os
import re

re_url = re.compile(r'https?://www.dia.org/art/collection/object/(.+)$')

def get_html(url):
    catalog_id = re_url.search(url).group(1).replace('/', '_')

    filename = f'cache/dia_{catalog_id}.html'

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

    for a in root.findall('.//a[@href]'):
        href = a.get('href')
        if not href.startswith('/art/collection?keys='):
            continue
        keywords.append(a.text)

    if False:
        sidebar = root.find('.//aside[@id="sidebar"]')
        h2_list = sidebar.findall('.//h2')
        h2_keyword = next((h2 for h2 in h2_list if h2.text == 'Keywords'), None)
        if not h2_keyword:
            return {}
        keyword_div = h2_keyword.getparent()
        for a in keyword_div:
            if a.tag != 'a':
                continue
            keywords.append(a.text)

    return {
        'institution': 'Detroit Institute of Arts',
        'keywords': keywords,
    }

def get_catalog(url):
    return parse_html(get_html(url))
