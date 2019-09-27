import requests
import os
import json

def get_json(catalog_id):
    filename = f'cache/barnesfoundation_{catalog_id}.html'

    url = 'https://collection.barnesfoundation.org/api/search'

    body = {"query": {"bool": {"filter": {"exists": {"field": "imageSecret"}},
                               "must": {"match": {"_id": int(catalog_id)}}}}}

    if os.path.exists(filename):
        return json.load(open(filename))
    else:
        r = requests.get(url, params={'body': json.dumps(body)})
        print(r.url)
        open(filename, 'w').write(r.text)
        return r.json()

def parse_catalog(data):
    hit = data['hits']['hits'][0]['_source']

    return {
        'institution': 'Barnes Foundation',
        'description': hit['shortDescription'],
        'keywords': [tag['tag'] for tag in hit['tags']],
    }

def get_catalog(catalog_id):
    data = get_json(catalog_id)
    return parse_catalog(data)
