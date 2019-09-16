#!/usr/bin/python3

from flask import Flask, render_template, url_for, redirect, request, g
from depicts import utils, wdqs, commons, mediawiki, painting
import json
import os
import locale
import random

locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')

thumbwidth = 300

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

painting_no_depicts_query = '''
select distinct ?item where {
  ?item wdt:P31 wd:Q3305213 .
  ?item wdt:P18 ?image .
  filter not exists { ?item wdt:P180 ?depicts }
}
'''

@app.template_global()
def set_url_args(**new_args):
    args = request.view_args.copy()
    args.update(request.args)
    args.update(new_args)
    args = {k: v for k, v in args.items() if v is not None}
    return url_for(request.endpoint, **args)

@app.before_request
def init_profile():
    g.profiling = []

@app.route("/")
def index():
    return render_template('index.html', props=find_more_props)

@app.route("/property/P<int:property_id>")
def property_query_page(property_id):
    pid = f'P{property_id}'
    sort = request.args.get('sort')
    sort_by_name = sort and sort.lower().strip() == 'name'

    q = property_query.replace('PID', pid)
    rows = wdqs.run_query_with_cache(q, name=pid)

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

@app.route('/random')
def random_painting():
    rows = wdqs.run_query_with_cache(painting_no_depicts_query)
    row = random.choice(rows)
    item_id = wdqs.row_id(row)
    return redirect(url_for('item_page', item_id=item_id))

@app.route("/item/Q<int:item_id>")
def item_page(item_id):
    qid = f'Q{item_id}'
    item = painting.Painting(qid)

    width = 800
    image_filename = item.image_filename
    filename = f'cache/{qid}_{width}_image.json'
    if os.path.exists(filename):
        detail = json.load(open(filename))
    else:
        detail = commons.image_detail([image_filename], thumbwidth=width)
        json.dump(detail, open(filename, 'w'), indent=2)

    hits = item.run_query()

    return render_template('item.html',
                           qid=qid,
                           item=item,
                           image=detail[image_filename],
                           hits=hits,
                           title=item.display_title)

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
            labels += mediawiki.get_entities(cur, props='labels')

        json.dump({'keys': keys, 'labels': labels},
                  open(filename, 'w'), indent=2)

    return {entity['id']: get_entity_label(entity) for entity in labels}

@app.route("/next/Q<int:item_id>")
def next_page(item_id):
    qid = f'Q{item_id}'

    entity = mediawiki.get_entity_with_cache(qid)

    width = 800
    image_filename = entity['claims']['P18'][0]['mainsnak']['datavalue']['value']
    filename = f'cache/{qid}_{width}_image.json'
    if os.path.exists(filename):
        detail = json.load(open(filename))
    else:
        detail = commons.image_detail([image_filename], thumbwidth=width)
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
    return redirect(url_for('browse_page', **{pid: qid}))

def get_facets(sparql_params, params):
    flat = '_'.join(f'{pid}={qid}' for pid, qid in params)

    property_list = ' '.join(f'wdt:{pid}' for pid in find_more_props.keys()
                             if pid not in request.args)

    q = (facet_query.replace('PARAMS', sparql_params)
                    .replace('PROPERTY_LIST', property_list))

    bindings = wdqs.run_query_with_cache(q, flat + '_facets')

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

    q = find_more_query.replace('PARAMS', sparql_params)

    bindings = wdqs.run_query_with_cache(q, flat)
    facets = get_facets(sparql_params, params)

    page_size = 45

    item_map = wdqs.build_browse_item_map(bindings)
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
        detail = commons.image_detail(filenames, thumbwidth=thumbwidth)
        json.dump(detail, open(filename, 'w'), indent=2)

    for item in items:
        item['url'] = url_for('item_page', item_id=item['item_id'])
        item['image'] = detail[item['image_filename']]

    title = ' / '.join(item_labels[qid] for pid, qid in params)

    return render_template('find_more.html',
                           facets=facets,
                           prop_labels=find_more_props,
                           label=title,
                           labels=find_more_props,
                           bindings=bindings,
                           total=len(bindings),
                           items=items)


if __name__ == "__main__":
    app.debug = True
    app.run(host='0.0.0.0', debug=True)
