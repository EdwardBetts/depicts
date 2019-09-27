import requests
import lxml.html
import os
import re

re_url = re.compile(r'www.npg.org.uk/collections/search/(.+)$')

def get_html(url):
    catalog_id = re_url.search(url).group(1).replace('/', '_')

    filename = f'cache/npg_{catalog_id}.html'

    if os.path.exists(filename):
        html = open(filename).read()
    else:
        r = requests.get(url)
        html = r.text
        open(filename, 'w').write(html)

    return html

def parse_html(html):
    root = lxml.html.fromstring(html)

    keywords = [a.text for a in root.findall('.//a[@href]')
                if 'subj=' in a.get('href')]

    skip = {'oil', 'painting'}
    keywords = [k for k in keywords if k.lower() not in skip]

    return {
        'institution': 'National Portrait Gallery',
        'keywords': keywords,
    }

def get_catalog(url):
    return parse_html(get_html(url))
