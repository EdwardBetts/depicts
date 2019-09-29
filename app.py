#!/usr/bin/python3

from flask import Flask, render_template, url_for, redirect, request, g, jsonify, session
from depicts import (utils, wdqs, commons, mediawiki, painting, saam, database,
                     dia, rijksmuseum, npg, museodelprado, barnesfoundation,
                     wd_catalog)
from depicts.pager import Pagination, init_pager
from depicts.model import DepictsItem, DepictsItemAltLabel, Edit, PaintingItem
from depicts.error_mail import setup_error_mail
from requests_oauthlib import OAuth1Session
from urllib.parse import urlencode
from werkzeug.exceptions import InternalServerError
from werkzeug.debug.tbtools import get_current_traceback
from sqlalchemy import func, distinct
import requests.exceptions
import requests
import lxml.html
import json
import os
import locale
import random

locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')
user_agent = 'Mozilla/5.0 (X11; Linux i586; rv:32.0) Gecko/20160101 Firefox/32.0'

app = Flask(__name__)
app.config.from_object('config.default')
database.init_db(app.config['DB_URL'])
init_pager(app)
setup_error_mail(app)

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

find_more_basic_query = '''
select distinct ?item ?image {
  VALUES ?value { LIST }
  ?item wdt:P31 wd:Q3305213 .
  ?item wdt:PID ?value .
  ?item wdt:P18 ?image .
  FILTER NOT EXISTS { ?item wdt:P180 ?depicts }
} limit LIMIT
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

@app.errorhandler(InternalServerError)
def exception_handler(e):
    tb = get_current_traceback()
    return render_template('show_error.html', tb=tb), 500

@app.template_global()
def set_url_args(**new_args):
    args = request.view_args.copy()
    args.update(request.args)
    args.update(new_args)
    args = {k: v for k, v in args.items() if v is not None}
    return url_for(request.endpoint, **args)

@app.template_global()
def current_url():
    args = request.view_args.copy()
    args.update(request.args)
    return url_for(request.endpoint, **args)

@app.before_request
def init_profile():
    g.profiling = []

@app.route('/save/Q<int:item_id>', methods=['POST'])
def save(item_id):
    depicts = request.form.getlist('depicts')
    username = get_username()
    assert username

    token = get_token()

    painting_item = PaintingItem.query.get(item_id)
    if painting_item is None:
        painting_entity = mediawiki.get_entity_with_cache(f'Q{item_id}')
        label = get_entity_label(painting_entity)
        painting_item = PaintingItem(item_id=item_id, label=label, entity=painting_entity)
        database.session.add(painting_item)
        database.session.commit()

    for depicts_qid in depicts:
        depicts_id = int(depicts_qid[1:])
        r = create_claim(item_id, depicts_id, token)
        reply = r.json()
        if 'error' in reply:
            return 'error:' + r.text
        print(r.text)
        saved = r.json()
        lastrevid = saved['pageinfo']['lastrevid']
        assert saved['success'] == 1
        edit = Edit(username=username,
                    painting_id=item_id,
                    depicts_id=depicts_id,
                    lastrevid=lastrevid)
        database.session.add(edit)
        database.session.commit()

    return redirect(url_for('next_page', item_id=item_id))

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

@app.route('/')
def start():
    return random_painting()

@app.route('/next')
def random_painting():
    rows = wdqs.run_query_with_cache(painting_no_depicts_query)
    row = random.choice(rows)
    item_id = wdqs.row_id(row)
    return redirect(url_for('item_page', item_id=item_id))

@app.route('/oauth/start')
def start_oauth():

    next_page = request.args.get('next')
    if next_page:
        session['after_login'] = next_page

    client_key = app.config['CLIENT_KEY']
    client_secret = app.config['CLIENT_SECRET']
    base_url = 'https://www.wikidata.org/w/index.php'
    request_token_url = base_url + '?title=Special%3aOAuth%2finitiate'

    oauth = OAuth1Session(client_key,
                          client_secret=client_secret,
                          callback_uri='oob')
    fetch_response = oauth.fetch_request_token(request_token_url)

    session['owner_key'] = fetch_response.get('oauth_token')
    session['owner_secret'] = fetch_response.get('oauth_token_secret')

    base_authorization_url = 'https://www.wikidata.org/wiki/Special:OAuth/authorize'
    authorization_url = oauth.authorization_url(base_authorization_url,
                                                oauth_consumer_key=client_key)
    return redirect(authorization_url)

@app.route("/oauth/callback", methods=["GET"])
def oauth_callback():
    base_url = 'https://www.wikidata.org/w/index.php'
    client_key = app.config['CLIENT_KEY']
    client_secret = app.config['CLIENT_SECRET']

    oauth = OAuth1Session(client_key,
                          client_secret=client_secret,
                          resource_owner_key=session['owner_key'],
                          resource_owner_secret=session['owner_secret'])

    oauth_response = oauth.parse_authorization_response(request.url)
    verifier = oauth_response.get('oauth_verifier')
    access_token_url = base_url + '?title=Special%3aOAuth%2ftoken'
    oauth = OAuth1Session(client_key,
                          client_secret=client_secret,
                          resource_owner_key=session['owner_key'],
                          resource_owner_secret=session['owner_secret'],
                          verifier=verifier)

    oauth_tokens = oauth.fetch_access_token(access_token_url)
    session['owner_key'] = oauth_tokens.get('oauth_token')
    session['owner_secret'] = oauth_tokens.get('oauth_token_secret')

    next_page = session.get('after_login')
    return redirect(next_page) if next_page else random_painting()

@app.route('/oauth/disconnect')
def oauth_disconnect():
    for key in 'owner_key', 'owner_secret', 'username', 'after_login':
        if key in session:
            del session[key]
    return random_painting()

def get_username():
    if 'owner_key' not in session:
        return  # not authorized

    if 'username' in session:
        return session['username']

    params = {'action': 'query', 'meta': 'userinfo', 'format': 'json'}
    reply = oauth_api_request(params)
    if 'query' not in reply:
        return
    session['username'] = reply['query']['userinfo']['name']

    return session['username']

@app.route("/show_user")
def show_user():
    # Make authenticated calls to the API
    params = {'action': 'query', 'meta': 'userinfo', 'format': 'json'}
    reply = oauth_api_request(params)['query']

    return repr(reply)

def oauth_api_request(params):
    url = 'https://www.wikidata.org/w/api.php?' + urlencode(params)
    client_key = app.config['CLIENT_KEY']
    client_secret = app.config['CLIENT_SECRET']
    oauth = OAuth1Session(client_key,
                          client_secret=client_secret,
                          resource_owner_key=session['owner_key'],
                          resource_owner_secret=session['owner_secret'])
    r = oauth.get(url, timeout=2)
    reply = r.json()

    return reply

def create_claim(painting_id, depicts_id, token):
    painting_qid = f'Q{painting_id}'
    value = json.dumps({'entity-type': 'item',
                        'numeric-id': depicts_id})
    params = {
        'action': 'wbcreateclaim',
        'entity': painting_qid,
        'property': 'P180',
        'snaktype': 'value',
        'value': value,
        'token': token,
        'format': 'json',
        'formatversion': 2,
    }
    return oauth_api_post_request(params)

def get_token():
    params = {
        'action': 'query',
        'meta': 'tokens',
        'format': 'json',
        'formatversion': 2,
    }
    reply = oauth_api_request(params)
    token = reply['query']['tokens']['csrftoken']

    return token

def oauth_api_post_request(params):
    url = 'https://www.wikidata.org/w/api.php'
    client_key = app.config['CLIENT_KEY']
    client_secret = app.config['CLIENT_SECRET']
    oauth = OAuth1Session(client_key,
                          client_secret=client_secret,
                          resource_owner_key=session['owner_key'],
                          resource_owner_secret=session['owner_secret'])
    return oauth.post(url, data=params, timeout=2)

def image_with_cache(qid, image_filename, width):
    filename = f'cache/{qid}_{width}_image.json'
    if os.path.exists(filename):
        detail = json.load(open(filename))
    else:
        detail = commons.image_detail([image_filename], thumbwidth=width)
        json.dump(detail, open(filename, 'w'), indent=2)

    return detail[image_filename]

def first_datavalue(entity, pid):
    if pid in entity['claims']:
        return entity['claims'][pid][0]['mainsnak']['datavalue']['value']

def get_catalog_page(property_id, value):
    detail = wd_catalog.lookup(property_id, value)
    url = detail['url']
    catalog_id = value.replace('/', '_')

    filename = f'cache/{property_id}_{catalog_id}.html'

    if os.path.exists(filename):
        html = open(filename).read()
    else:
        r = requests.get(url, headers={'User-Agent': user_agent}, timeout=2)
        html = r.text
        open(filename, 'w').write(html)

    return html

def get_description_from_page(html):
    root = lxml.html.fromstring(html)
    div = root.find('.//div[@itemprop="description"]')
    if div is not None:
        return div.text

@app.route("/item/Q<int:item_id>")
def item_page(item_id):
    qid = f'Q{item_id}'
    item = painting.Painting(qid)
    entity = mediawiki.get_entity_with_cache(qid)

    width = 800
    image_filename = item.image_filename
    image = image_with_cache(qid, image_filename, width)

    # hits = item.run_query()
    label = get_entity_label(entity)
    other = get_other(item.entity)

    painting_item = PaintingItem.query.get(item_id)
    if painting_item is None:
        painting_item = PaintingItem(item_id=item_id, label=label, entity=entity)
        database.session.add(painting_item)

    catalog_ids = wd_catalog.find_catalog_id(entity)
    catalog_detail = []
    for property_id in sorted(catalog_ids):
        value = first_datavalue(entity, property_id)
        detail = wd_catalog.lookup(property_id, value)
        catalog_detail.append(detail)

    catalog_url = first_datavalue(entity, 'P973')

    catalog = None
    try:
        if 'P4704' in entity['claims']:
            saam_id = first_datavalue(entity, 'P4704')
            catalog = saam.get_catalog(saam_id)
        elif 'P4709' in entity['claims']:
            catalog_id = first_datavalue(entity, 'P4709')
            catalog = barnesfoundation.get_catalog(catalog_id)
        elif catalog_url and 'www.dia.org' in catalog_url:
            catalog = dia.get_catalog(catalog_url)
        elif catalog_url and 'www.rijksmuseum.nl' in catalog_url:
            catalog = rijksmuseum.get_catalog(catalog_url)
        elif catalog_url and 'www.npg.org.uk' in catalog_url:
            catalog = npg.get_catalog(catalog_url)
        elif catalog_url and 'www.museodelprado.es' in catalog_url:
            catalog = museodelprado.get_catalog(catalog_url)

        if not catalog and catalog_ids:
            for property_id in sorted(catalog_ids):
                if property_id == 'P350':
                    continue  # RKDimages ID
                value = first_datavalue(entity, property_id)
                detail = wd_catalog.lookup(property_id, value)
                try:
                    html = get_catalog_page(property_id, value)
                except requests.exceptions.SSLError:
                    continue  # ignore this error
                description = get_description_from_page(html)
                if not description:
                    continue
                catalog = {
                    'institution': detail['label'],
                    'description': description,
                }
    except requests.exceptions.ReadTimeout:
        pass

    return render_template('item.html',
                           qid=qid,
                           item_id=item_id,
                           item=item,
                           catalog=catalog,
                           catalog_url=catalog_url,
                           catalog_detail=catalog_detail,
                           labels=find_more_props,
                           entity=item.entity,
                           username=get_username(),
                           label=label,
                           image=image,
                           other=other,
                           # hits=hits,
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

def get_other(entity):
    other_items = set()
    for key in find_more_props.keys():
        if key not in entity['claims']:
            continue
        for claim in entity['claims'][key]:
            if 'datavalue' in claim['mainsnak']:
                other_items.add(claim['mainsnak']['datavalue']['value']['id'])

    return get_labels(other_items)

@app.route("/admin/edits")
def list_edits():
    edit_list = Edit.query.order_by(Edit.timestamp)

    painting_count = (database.session
                              .query(func.count(distinct(Edit.painting_id)))
                              .scalar())

    user_count = (database.session
                          .query(func.count(distinct(Edit.username)))
                          .scalar())

    return render_template('list_edits.html',
                           edits=Edit.query,
                           edit_list=edit_list,
                           painting_count=painting_count,
                           user_count=user_count)

@app.route("/user/<username>")
def user_page(username):
    edit_list = Edit.query.filter_by(username=username).order_by(Edit.timestamp)

    painting_count = (database.session
                              .query(func.count(distinct(Edit.painting_id)))
                              .filter_by(username=username)
                              .scalar())

    return render_template('user_page.html',
                           username=username,
                           edits=Edit.query,
                           edit_list=edit_list,
                           painting_count=painting_count)

@app.route("/next/Q<int:item_id>")
def next_page(item_id):
    qid = f'Q{item_id}'

    entity = mediawiki.get_entity_with_cache(qid)

    width = 800
    image_filename = first_datavalue(entity, 'P18')
    image = image_with_cache(qid, image_filename, width)

    label = get_entity_label(entity)
    other = get_other(entity)

    other_list = []
    for key, prop_label in find_more_props.items():
        if key == 'P186':  # skip material used
            continue       # too generic
        claims = entity['claims'].get(key)
        if not claims:
            continue

        values = []

        for claim in claims:
            if 'datavalue' not in claim['mainsnak']:
                continue
            value = claim['mainsnak']['datavalue']['value']
            claim_qid = value['id']
            if claim_qid == 'Q4233718':
                continue  # anonymous artist
            numeric_id = value['numeric-id']
            href = url_for('find_more_page', property_id=key[1:], item_id=numeric_id)
            values.append({
                'href': href,
                'qid': claim_qid,
                'label': other.get(claim_qid),
            })

        if not values:
            continue

        qid_list = [v['qid'] for v in values]

        other_list.append({
            'label': prop_label,
            'image_lookup': url_for('find_more_json', pid=key, qid=qid_list),
            'pid': key,
            'values': values,
            'images': [],
        })

    return render_template('next.html',
                           qid=qid,
                           label=label,
                           image=image,
                           labels=find_more_props,
                           other=other,
                           entity=entity,
                           other_props=other_list)

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

    if not params:
        return render_template('browse_index.html',
                               props=find_more_props,
                               username=get_username())

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

    all_items = []
    for item in item_map.values():
        if len(item['image_filename']) != 1:
            continue
        item['image_filename'] = item['image_filename'][0]
        all_items.append(item)

    page = utils.get_int_arg('page') or 1
    pager = Pagination(page, page_size, len(all_items))

    items = pager.slice(all_items)

    filenames = [cur['image_filename'] for cur in items]

    thumbwidth = app.config['THUMBWIDTH']

    filename = f'cache/{flat}_{page}_{page_size}_images.json'
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
                           pager=pager,
                           page=page,
                           labels=find_more_props,
                           bindings=bindings,
                           total=len(bindings),
                           items=items)

@app.route('/find_more.json')
def find_more_json():
    pid = request.args.get('pid')
    qid_list = request.args.getlist('qid')
    limit = 6

    value_list = ' '.join(f'wd:{qid}' for qid in qid_list)

    q = (find_more_basic_query
         .replace('LIST', value_list)
         .replace('PID', pid)
         .replace('LIMIT', str(limit)))

    filenames = []
    bindings = wdqs.run_query_with_cache(q, f'{pid}={",".join(qid_list)}_{limit}')
    items = []
    for row in bindings:
        item_id = wdqs.row_id(row)
        row_qid = f'Q{item_id}'
        image_filename = wdqs.commons_uri_to_filename(row['image']['value'])
        filenames.append(image_filename)
        items.append({'qid': row_qid,
                      'item_id': item_id,
                      'href': url_for('item_page', item_id=item_id),
                      'filename': image_filename})

    thumbheight = 120
    detail = commons.image_detail(filenames, thumbheight=thumbheight)

    for item in items:
        item['image'] = detail[item['filename']]

    return jsonify(items=items, q=q)

@app.route('/lookup')
def depicts_lookup():
    terms = request.args.get('terms')
    if not terms:
        return jsonify(error='terms parameter is required')

    terms = terms.strip()
    if len(terms) < 3:
        return jsonify(
            count=0,
            hits=[],
            notice='terms too short for lookup',
        )

    item_ids = []
    hits = []
    q1 = DepictsItem.query.filter(DepictsItem.label.ilike(terms + '%'))
    for item in q1:
        hit = {
            'label': item.label,
            'description': item.description,
            'qid': item.qid,
            'count': item.count,
        }
        item_ids.append(item.item_id)
        hits.append(hit)

    cls = DepictsItemAltLabel
    q2 = cls.query.filter(cls.alt_label.ilike(terms + '%'),
                          ~cls.item_id.in_(item_ids))

    for alt in q2:
        item = alt.item
        hit = {
            'label': item.label,
            'description': item.description,
            'qid': item.qid,
            'count': item.count,
            'alt_label': alt.alt_label,
        }
        hits.append(hit)

    hits.sort(key=lambda hit: hit['count'], reverse=True)

    ret = {
        'count': q1.count() + q2.count(),
        'hits': hits,
        'terms': terms,
    }

    return jsonify(ret)


if __name__ == "__main__":
    app.debug = True
    app.run(host='0.0.0.0', debug=True)
