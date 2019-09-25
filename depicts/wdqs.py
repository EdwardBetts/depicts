import requests
import json
import urllib.parse
import os
import dateutil.parser
import hashlib
from . import utils

query_url = 'https://query.wikidata.org/bigdata/namespace/wdq/sparql'
url_start = 'http://www.wikidata.org/entity/Q'
commons_start = 'http://commons.wikimedia.org/wiki/Special:FilePath/'

def row_id(row):
    return int(utils.drop_start(row['item']['value'], url_start))

def get_row_value(row, field):
    return row[field]['value'] if field in row else None

def get_row_text(row, field):
    if field in row and 'xml:lang' in row[field]:
        return row[field]['value']

def commons_uri_to_filename(uri):
    return urllib.parse.unquote(utils.drop_start(uri, commons_start))

def run_query(query):
    params = {'query': query, 'format': 'json'}
    r = requests.post(query_url, data=params, stream=True)
    assert r.status_code == 200
    return r

def md5_query(query):
    ''' generate the md5 hexdigest of a SPARQL query '''
    return hashlib.md5(query.encode('utf-8')).hexdigest()

def run_query_with_cache(q, name=None):
    if name is None:
        name = md5_query(q)
    filename = f'cache/{name}.json'
    if os.path.exists(filename):
        from_cache = json.load(open(filename))
        if isinstance(from_cache, dict) and from_cache.get('query') == q:
            return from_cache['bindings']

    r = run_query(q)
    bindings = r.json()['results']['bindings']
    json.dump({'query': q, 'bindings': bindings},
              open(filename, 'w'), indent=2)

    return bindings

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

def build_browse_item_map(bindings):
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
            label = get_row_value(row, 'title') or 'name missing'

        artist_name = get_row_value(row, 'artistLabel') or '[artist unknown]'

        d = format_time(row['time'], row['timeprecision']) if 'time' in row else None

        item = {
            'image_filename': [image_filename],
            'item_id': item_id,
            'qid': row_qid,
            'label': label,
            'date': d,
            'artist_name': artist_name,
        }
        item_map[item_id] = item

    return item_map

def quote_list(l):
    no_dups = list(dict.fromkeys(l))  # remove duplicates
    return ' '.join('("' + s.replace('"', '\\"') + '")' for s in no_dups)

def url_list(l):
    no_dups = list(dict.fromkeys(l))  # remove duplicates
    return ' '.join(f'(<{s}>)' for s in no_dups)
