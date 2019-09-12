#!/usr/bin/python3

from flask import Flask, render_template, url_for
from itertools import islice
from pprint import pprint
import dateutil.parser
import urllib.parse
import lxml.etree
import requests
import json
import os

url_start = 'http://www.wikidata.org/entity/Q'
wikidata_url = 'https://www.wikidata.org/w/api.php'
commons_url = 'https://www.wikidata.org/w/api.php'
wikidata_query_api_url = 'https://query.wikidata.org/bigdata/namespace/wdq/sparql'
commons_start = 'http://commons.wikimedia.org/wiki/Special:FilePath/'
commons_api_url = 'https://tools.wmflabs.org/magnus-toolserver/commonsapi.php'
commons_query_url = 'https://commons.wikimedia.org/w/api.php'
thumbwidth = 300
thumbheight = 400

app = Flask(__name__)

find_more_props = {
    'P135': 'movement',
    'P136': 'genre',
    'P170': 'artist',
    'P195': 'collection',
    'P276': 'location',
    'P495': 'country of origin',
    'P127': 'owned by',
    'P179': 'part of the series',
    # possible future props
    # 'P571': 'inception',
    # 'P921': 'main subject',
}

find_more_query = '''
select ?item ?itemLabel ?image ?artist ?artistLabel ?title ?time ?timeprecision {
  SERVICE wikibase:label { bd:serviceParam wikibase:language "[AUTO_LANGUAGE],en". }
  ?item wdt:P31 wd:Q3305213 .
  ?item wdt:PID wd:QID .
  ?item wdt:P18 ?image .
  OPTIONAL {
    ?item p:P571/psv:P571 ?timenode .
    ?timenode wikibase:timeValue         ?time.
    ?timenode wikibase:timePrecision     ?timeprecision.
  }
  OPTIONAL { ?item wdt:P1476 ?title }
  OPTIONAL { ?item wdt:P170 ?artist }
  FILTER NOT EXISTS { ?item wdt:P180 ?depicts }
}
'''

def ordinal(n):
    return "%d%s" % (n, 'tsnrhtdd'[(n / 10 % 10 != 1) * (n % 10 < 4) * n % 10::4])

def chunk(it, size):
    it = iter(it)
    return iter(lambda: tuple(islice(it, size)), ())

def run_wikidata_query(query):
    params = {'query': query, 'format': 'json'}
    r = requests.post(wikidata_query_api_url, data=params, stream=True)
    assert r.status_code == 200
    return r

def drop_start(s, start):
    assert s.startswith(start)
    return s[len(start):]

def row_id(row):
    return int(drop_start(row['item']['value'], url_start))

def api_call(params, api_url=wikidata_url):
    call_params = {
        'format': 'json',
        'formatversion': 2,
        **params,
    }

    r = requests.get(wikidata_url, params=call_params)
    return r

def get_entity(qid):
    json_data = api_call({'action': 'wbgetentities', 'ids': qid}).json()

    try:
        entity = list(json_data['entities'].values())[0]
    except KeyError:
        return
    if 'missing' not in entity:
        return entity

def get_entities(ids, **params):
    if not ids:
        return []
    params = {
        'action': 'wbgetentities',
        'ids': '|'.join(ids),
        **params,
    }
    r = api_call(params)
    json_data = r.json()
    return list(json_data['entities'].values())

@app.route("/")
def index():
    return render_template('index.html')

@app.route("/item/Q<int:item_id>")
def item_page(item_id):
    qid = f'Q{item_id}'
    return render_template('item.html', qid=qid)

def get_labels(keys, name=None):
    keys = sorted(keys, key=lambda i: int(i[1:]))
    if name is None:
        name = '_'.join(keys)
    filename = f'cache/{name}_labels.json'
    if os.path.exists(filename):
        labels = json.load(open(filename))
    else:
        labels = []
        for cur in chunk(keys, 50):
            labels += get_entities(cur, props='labels')
        json.dump(labels, open(filename, 'w'), indent=2)

    try:
        return {prop['id']: prop['labels']['en']['value'] for prop in labels}
    except TypeError:
        pprint(labels)
        raise


def get_entity_with_cache(qid):
    filename = f'cache/{qid}.json'
    if os.path.exists(filename):
        entity = json.load(open(filename))
    else:
        entity = get_entity(qid)
        json.dump(entity, open(filename, 'w'), indent=2)

    return entity

def commons_uri_to_filename(uri):
    return urllib.parse.unquote(drop_start(uri, commons_start))

def image_detail(filenames, thumbheight=None, thumbwidth=None):
    if not isinstance(filenames, list):
        filenames = [filenames]
    if not filenames:
        return {}

    params = {
        'action': 'query',
        'titles': '|'.join(f'File:{f}' for f in filenames),
        'prop': 'imageinfo',
        'iiprop': 'url',
    }
    if thumbheight is not None:
        params['iiurlheight'] = thumbheight
    if thumbwidth is not None:
        params['iiurlwidth'] = thumbwidth
    r = api_call(params, api_url=commons_url)

    images = {}

    for image in r.json()['query']['pages']:
        filename = drop_start(image['title'], 'File:')
        images[filename] = image['imageinfo'][0]

    return images

def image_detail_old(filenames, thumbwidth=None):
    if not isinstance(filenames, list):
        filenames = [filenames]
    params = {'image': '|'.join(filenames)}
    if thumbwidth is not None:
        params['thumbwidth'] = thumbwidth
    r = requests.get(commons_api_url, params=params)
    xml = r.text
    # workaround a bug in the commons API
    # the API doesn't encode " in filenames
    for f in filenames:
        if '"' not in f:
            continue
        esc = f.replace('"', '&quot;')

        xml = xml.replace(f'name="{f}"', f'name="{esc}"')

    # print(xml)

    root = lxml.etree.fromstring(xml.encode('utf-8'))

    images = []
    for image in root:
        if image.tag == 'image':
            file_element = image.find('./file')
        elif image.tag == 'file':
            file_element = image
        else:
            continue
        thumb_element = file_element.find('./urls/thumbnail')

        image = {
            'name': image.get('name'),
            'image': file_element.find('./urls/file').text,
            'height': int(file_element.find('./height').text),
            'width': int(file_element.find('./width').text),
        }

        if thumb_element is not None:
            image['thumbnail'] = thumb_element.text

        images.append(image)

    return images

# def commons_filename(row):
#     image = row['image']['value']
#     assert image.startswith(commons_start)
#     return urllib.parse.unquote(image[len(commons_start):])
#
# def commons_api(row):
#     params = {
#         'image': commons_filename(row),
#         'thumbwidth': thumbwidth,
#     }
#     r = requests.get(commons_api_url, params=params)
#     return r
#
# def get_commons(row):
#     r = commons_api(row)
#     root = lxml.etree.fromstring(r.content)
#
#     return root.find('./file/urls/thumbnail').text

@app.route("/next/Q<int:item_id>")
def next_page(item_id):
    qid = f'Q{item_id}'

    entity = get_entity_with_cache(qid)

    width = 800
    image_filename = entity['claims']['P18'][0]['mainsnak']['datavalue']['value']
    filename = f'cache/{qid}_{width}_image.json'
    if os.path.exists(filename):
        detail = json.load(open(filename))
    else:
        detail = image_detail([image_filename], thumbwidth=width)
        json.dump(detail, open(filename, 'w'), indent=2)

    other_items = set()
    for key in find_more_props.keys():
        if key not in entity['claims']:
            continue
        for claim in entity['claims'][key]:
            other_items.add(claim['mainsnak']['datavalue']['value']['id'])

    item_labels = get_labels(other_items)

    if 'en' in entity['labels']:
        label = entity['labels']['en']['value']
    elif len(entity['labels']) == 1:
        label = list(entity['labels'].values())[0]['value']
    else:
        label = 'title missing'

    return render_template('next.html',
                           qid=qid,
                           label=label,
                           image=detail[image_filename],
                           labels=find_more_props,
                           other=item_labels,
                           entity=entity)

@app.route('/P<int:property_id>/Q<int:item_id>')
def find_more_page(property_id, item_id):
    pid, qid = f'P{property_id}', f'Q{item_id}'

    item_entity = get_entity_with_cache(qid)

    property_keys = item_entity['claims'].keys()
    property_labels = get_labels(property_keys, name=f'{qid}_property_labels')

    query = find_more_query.replace('QID', qid).replace('PID', pid)

    filename = f'cache/{pid}_{qid}.json'
    if os.path.exists(filename):
        bindings = json.load(open(filename))
    else:
        r = run_wikidata_query(query)
        bindings = r.json()['results']['bindings']
        json.dump(bindings, open(filename, 'w'), indent=2)

    page_size = 45

    item_map = {}
    for row in bindings:
        item_id = row_id(row)
        row_qid = f'Q{item_id}'
        label = row['itemLabel']['value']
        image_filename = commons_uri_to_filename(row['image']['value'])
        if item_id in item_map:
            item = item_map[item_id]
            item['image_filename'].append(image_filename)
            continue

        if label == row_qid:
            if 'title' in row:
                label = row['title']['value']
            else:
                label = 'name missing'
        if 'artistLabel' in row:
            artist_name = row['artistLabel']['value']
        else:
            artist_name = '[artist unknown]'

        if 'time' in row:
            t = dateutil.parser.parse(row['time']['value'])
            precision = int(row['timeprecision']['value'])
            print((row['time']['value'], precision))

            if precision == 9:
                d = t.year
            elif precision == 8:
                d = f'{t.year}s'
            elif precision == 7:
                d = f'{ordinal((t.year // 100) + 1)} century'
            elif precision == 6:
                d = f'{ordinal((t.year // 1000) + 1)} millennium'
            else:
                d = row['time']['value']
        else:
            d = None

        item = {
            'url': url_for('next_page', item_id=item_id),
            'image_filename': [image_filename],
            'item_id': item_id,
            'qid': row_qid,
            'label': label,
            'date': d,
            'artist_name': artist_name,
        }
        item_map[item_id] = item

    items = []
    for item in item_map.values():
        if len(item['image_filename']) != 1:
            continue
        item['image_filename'] = item['image_filename'][0]
        items.append(item)
        if len(items) >= page_size:
            break

    filenames = [cur['image_filename'] for cur in items]

    filename = f'cache/{pid}_{qid}_{page_size}_images.json'
    if os.path.exists(filename):
        detail = json.load(open(filename))
    else:
        detail = image_detail(filenames, thumbwidth=thumbwidth)
        json.dump(detail, open(filename, 'w'), indent=2)

    for item in items:
        item['image'] = detail[item['image_filename']]

    total = len(bindings)

    return render_template('find_more.html',
                           qid=qid,
                           pid=pid,
                           item_entity=item_entity,
                           property_labels=property_labels,
                           labels=find_more_props,
                           bindings=bindings,
                           items=items,
                           total=total)


if __name__ == "__main__":
    app.debug = True
    app.run(host='0.0.0.0', debug=True)

    # server = Server(app.wsgi_app)
    # server.watch('template/*')
    # server.serve()
