import requests
import os
import json
import hashlib
from .category import Category

wikidata_url = 'https://www.wikidata.org/w/api.php'

hosts = {
    'commons': 'commons.wikimedia.org',
    'enwiki': 'en.wikipedia.org',
    'wikidata': 'www.wikidata.org',
}

def api_call(params, api_url=wikidata_url):
    call_params = {
        'format': 'json',
        'formatversion': 2,
        **params,
    }

    r = requests.get(api_url, params=call_params, timeout=5)
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

def get_entities_dict(ids, **params):
    if not ids:
        return []
    params = {
        'action': 'wbgetentities',
        'ids': '|'.join(ids),
        **params,
    }
    return api_call(params).json()['entities']

def get_entity_with_cache(qid, refresh=False):
    filename = f'cache/{qid}.json'
    if not refresh and os.path.exists(filename):
        entity = json.load(open(filename))
    else:
        entity = get_entity(qid)
        json.dump(entity, open(filename, 'w'), indent=2)

    return entity

def get_entities_with_cache(ids, **params):
    md5 = hashlib.md5(' '.join(ids).encode('utf-8')).hexdigest()

    filename = f'cache/entities_{md5}.json'
    if os.path.exists(filename):
        entity = json.load(open(filename))
    else:
        entity = get_entities(ids, **params)
        json.dump(entity, open(filename, 'w'), indent=2)

    return entity

def mediawiki_query(titles, params, site):
    if not titles:
        return []

    # avoid error: Too many values supplied for parameter "titles". The limit is 50.
    if len(titles) > 50:
        titles = titles[:50]
    base = {
        'format': 'json',
        'formatversion': 2,
        'action': 'query',
        'continue': '',
        'titles': '|'.join(titles),
    }
    p = base.copy()
    p.update(params)

    query_url = f'https://{hosts[site]}/w/api.php'
    r = requests.get(query_url, params=p)
    expect = 'application/json; charset=utf-8'
    success = True
    if r.status_code != 200:
        print('status code: {r.status_code}'.format(r=r))
        success = False
    if r.headers['content-type'] != expect:
        print('content-type: {r.headers[content-type]}'.format(r=r))
        success = False
    assert success
    json_reply = r.json()
    if 'query' not in json_reply:
        print(r.url)
        print(r.text)
    return json_reply['query']['pages']

def get_content_and_categories(title, site):
    params = {
        'prop': 'revisions|categories',
        'clshow': '!hidden',
        'cllimit': 'max',
        'rvprop': 'content',
    }

    pages = mediawiki_query([title], params, site)
    assert len(pages) == 1
    page = pages[0]
    return (page['revisions'][0]['content'], page.get('categories', []))

def host_from_site(site):
    return hosts[site]

def process_cats(cats, site):
    return [Category(cat['title'], site) for cat in cats]

def get_categories(titles, site):
    params = {
        'prop': 'categories',
        'clshow': '!hidden',
        'cllimit': 'max',
    }
    from_wiki = mediawiki_query(titles, params, site)
    title_and_cats = []
    for i in from_wiki:
        if 'categories' not in i:
            continue
        cats = process_cats(i['categories'], site)
        if not cats:
            continue
        title_and_cats.append((i['title'], cats))
    return title_and_cats
