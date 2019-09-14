#!/usr/bin/python3

from flask import Flask, render_template, url_for, redirect, request
from depicts import utils
import dateutil.parser
import urllib.parse
import requests
import json
import os
import locale

locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')

url_start = 'http://www.wikidata.org/entity/Q'
wikidata_url = 'https://www.wikidata.org/w/api.php'
commons_url = 'https://www.wikidata.org/w/api.php'
wikidata_query_api_url = 'https://query.wikidata.org/bigdata/namespace/wdq/sparql'
commons_start = 'http://commons.wikimedia.org/wiki/Special:FilePath/'
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
    'P921': 'main subject',
    'P186': 'material used',
    'P88': 'commissioned by',
    'P1028': 'donated by',
    'P1071': 'location of final assembly',
    'P138': 'named after',
    'P1433': 'published in',
    'P144': 'based on',
    'P2079': 'fabrication method',
    'P2348': 'time period',
    'P361': 'part of',
    'P608': 'exhibition history',

    # possible future props
    # 'P571': 'inception',
    # 'P166': 'award received', (only 2)
    # 'P1419': 'shape',  (only 2)
    # 'P123': 'publisher', (only 1)
}

find_more_query = '''
select ?item ?itemLabel ?image ?artist ?artistLabel ?title ?time ?timeprecision {
  SERVICE wikibase:label { bd:serviceParam wikibase:language "[AUTO_LANGUAGE],en". }
  ?item wdt:P31 wd:Q3305213 .
  PARAMS
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

facet_query = '''
select ?property ?object ?objectLabel (count(*) as ?count) {
  SERVICE wikibase:label { bd:serviceParam wikibase:language "[AUTO_LANGUAGE],en". }
  ?item wdt:P31 wd:Q3305213 .
  ?item wdt:P18 ?image .
  PARAMS
  values ?property { PROPERTY_LIST }
  ?item ?property ?object .
  FILTER NOT EXISTS { ?item wdt:P180 ?depicts }
} group by ?property ?propertyLabel ?object ?objectLabel
'''

property_query = '''
select ?object ?objectLabel ?objectDescription (count(*) as ?count) {
  ?item wdt:P31 wd:Q3305213 .
  ?item wdt:P18 ?image .
  ?item wdt:PID ?object .
  filter not exists { ?item wdt:P180 ?depicts }
  optional {
    ?object rdfs:label ?objectLabel.
    FILTER(LANG(?objectLabel) = "en").
  }
  optional {
    ?object schema:description ?objectDescription .
    filter(lang(?objectDescription) = "en")
  }

} group by ?object ?objectLabel ?objectDescription
order by desc(?count)
'''

def run_wikidata_query(query):
    params = {'query': query, 'format': 'json'}
    r = requests.post(wikidata_query_api_url, data=params, stream=True)
    assert r.status_code == 200
    return r

def row_id(row):
    return int(utils.drop_start(row['item']['value'], url_start))

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
    return render_template('index.html', props=find_more_props)

def run_query_with_cache(q, name):
    filename = f'cache/{name}.json'
    if os.path.exists(filename):
        from_cache = json.load(open(filename))
        if isinstance(from_cache, dict) and from_cache.get('query') == q:
            return from_cache['bindings']

    r = run_wikidata_query(q)
    bindings = r.json()['results']['bindings']
    json.dump({'query': q, 'bindings': bindings},
              open(filename, 'w'), indent=2)

    return bindings

def get_row_value(row, field):
    return row[field]['value'] if field in row else None

@app.route("/property/P<int:property_id>")
def property_query_page(property_id):
    pid = f'P{property_id}'
    sort = request.args.get('sort')
    sort_by_name = sort and sort.lower().strip() == 'name'

    q = property_query.replace('PID', pid)
    rows = run_query_with_cache(q, name=pid)

    no_label_qid = [row['object']['value'].rpartition('/')[2]
                    for row in rows
                    if 'objectLabel' not in row and '/' in row['object']['value']]

    if no_label_qid:
        extra_label = get_labels(no_label_qid, name=f'{pid}_extra_labels')
        if extra_label:
            for row in rows:
                item = row['object']['value']
                if 'objectLabel' in row or '/' not in item:
                    continue
                qid = item.rpartition('/')[2]
                if extra_label.get(qid):
                    row['objectLabel'] = {'value': extra_label[qid]}

    if sort_by_name:
        # put rows with no English label at the end
        no_label = [row for row in rows if 'objectLabel' not in row]
        has_label = sorted((row for row in rows if 'objectLabel' in row),
                            key=lambda row: locale.strxfrm(row['objectLabel']['value']))
        rows = has_label + no_label
    label = find_more_props[pid]

    return render_template('property.html',
                           label=label,
                           order=('name' if sort_by_name else 'count'),
                           pid=pid,
                           rows=rows)

@app.route("/item/Q<int:item_id>")
def item_page(item_id):
    qid = f'Q{item_id}'
    return render_template('item.html', qid=qid)

def get_entity_label(entity):
    if 'en' in entity['labels']:
        return entity['labels']['en']['value']

    label_values = {l['value'] for l in entity['labels'].values()}
    if len(label_values) == 1:
        return list(label_values)[0]

def get_labels(keys, name=None):
    keys = sorted(keys, key=lambda i: int(i[1:]))
    if name is None:
        name = '_'.join(keys)
    filename = f'cache/{name}_labels.json'
    labels = []
    if os.path.exists(filename):
        from_cache = json.load(open(filename))
        if isinstance(from_cache, dict) and from_cache.get('keys') == keys:
            labels = from_cache['labels']
    if not labels:
        for cur in utils.chunk(keys, 50):
            labels += get_entities(cur, props='labels')

        json.dump({'keys': keys, 'labels': labels},
                  open(filename, 'w'), indent=2)

    return {entity['id']: get_entity_label(entity) for entity in labels}

def get_entity_with_cache(qid):
    filename = f'cache/{qid}.json'
    if os.path.exists(filename):
        entity = json.load(open(filename))
    else:
        entity = get_entity(qid)
        json.dump(entity, open(filename, 'w'), indent=2)

    return entity

def commons_uri_to_filename(uri):
    return urllib.parse.unquote(utils.drop_start(uri, commons_start))

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
        filename = utils.drop_start(image['title'], 'File:')
        images[filename] = image['imageinfo'][0]

    return images

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

    return redirect(url_for('browse_page') + f'?{pid}={qid}')

def get_facets(sparql_params, params):
    flat = '_'.join(f'{pid}={qid}' for pid, qid in params)

    property_list = ' '.join(f'wdt:{pid}' for pid in find_more_props.keys()
                             if pid not in request.args)

    q = (facet_query.replace('PARAMS', sparql_params)
                    .replace('PROPERTY_LIST', property_list))

    # open(f'cache/{flat}_facets_query.sparql', 'w').write(q)

    bindings = run_query_with_cache(q, flat + '_facets')

    facets = {key: [] for key in find_more_props.keys()}
    for row in bindings:
        pid = row['property']['value'].rpartition('/')[2]
        qid = row['object']['value'].rpartition('/')[2]
        label = row['objectLabel']['value']
        count = int(row['count']['value'])

        facets[pid].append({'qid': qid, 'label': label, 'count': count})

    return {
        key: sorted(values, key=lambda i: i['count'], reverse=True)[:15]
        for key, values in facets.items()
        if values
    }

def format_time(row_time, row_timeprecision):
    t = dateutil.parser.parse(row_time['value'])
    precision = int(row_timeprecision['value'])

    if precision == 9:
        return t.year
    if precision == 8:
        return f'{t.year}s'
    if precision == 7:
        return f'{utils.ordinal((t.year // 100) + 1)} century'
    if precision == 6:
        return f'{utils.ordinal((t.year // 1000) + 1)} millennium'

    return row_time['value']

@app.route('/browse')
def browse_page():
    params = [(pid, qid) for pid, qid in request.args.items()
              if pid.startswith('P') and qid.startswith('Q')]

    flat = '_'.join(f'{pid}={qid}' for pid, qid in params)

    # item_entity = get_entity_with_cache(qid)

    item_labels = get_labels(qid for pid, qid in params)

    # property_keys = item_entity['claims'].keys()
    # property_labels = get_labels(property_keys, name=f'{flat}_property_labels')

    sparql_params = ''.join(
        f'?item wdt:{pid} wd:{qid} .\n' for pid, qid in params)

    query = find_more_query.replace('PARAMS', sparql_params)

    filename = f'cache/{flat}.json'
    if os.path.exists(filename):
        bindings = json.load(open(filename))
    else:
        r = run_wikidata_query(query)
        bindings = r.json()['results']['bindings']
        json.dump(bindings, open(filename, 'w'), indent=2)

    facets = get_facets(sparql_params, params)

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
            label = get_row_value('title') or 'name missing'

        artist_name = get_row_value['artistLabel'] or '[artist unknown]'

        d = format_time(row['time'], row['timeprecision']) if 'time' in row else None

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

    filename = f'cache/{flat}_{page_size}_images.json'
    if os.path.exists(filename):
        detail = json.load(open(filename))
    else:
        detail = image_detail(filenames, thumbwidth=thumbwidth)
        json.dump(detail, open(filename, 'w'), indent=2)

    for item in items:
        item['image'] = detail[item['image_filename']]

    total = len(bindings)

    title = ' / '.join(item_labels[qid] for pid, qid in params)

    return render_template('find_more.html',
                           facets=facets,
                           prop_labels=find_more_props,
                           label=title,
                           labels=find_more_props,
                           bindings=bindings,
                           items=items,
                           total=total)


if __name__ == "__main__":
    app.debug = True
    app.run(host='0.0.0.0', debug=True)
