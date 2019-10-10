import requests
import lxml.html
import json
import os

def get_html(saam_id):
    filename = f'cache/saam_{saam_id}.html'
    url = 'http://americanart.si.edu/collections/search/artwork/'

    if os.path.exists(filename):
        html = open(filename).read()
    else:
        r = requests.get(url, params={'id': saam_id})
        html = r.text
        open(filename, 'w').write(html)

    return html

def parse_html(html):
    root = lxml.html.fromstring(html)
    ld = json.loads(root.findtext('.//script[@type="application/ld+json"]'))

    ul = root.find('.//ul[@class="ontology-list"]')
    if ul is None:
        return {'ld': ld, 'keywords': []}
    assert ul.tag == 'ul'
    keywords = [li.text for li in ul]
    return {'ld': ld, 'keywords': keywords}

def get_catalog(saam_id):
    data = parse_html(get_html(saam_id))
    ret = {
        'institution': 'Smithsonian American Art Museum',
    }
    if data['keywords']:
        ret['keywords'] = data['keywords']
    if 'description' in data['ld']:
        ret['description'] = data['ld']['description']

    return ret if 'description' in ret or 'keywords' in ret else {}
