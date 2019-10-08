from .model import HumanItem
from . import mediawiki, utils
import re

re_four_digits = re.compile(r'\b\d{4}\b')

re_iso_date = re.compile(r'\b\d{4}-\d{2}-\d{2}\b')
re_four_and_two = re.compile(r'\b(\d{2})(\d{2})[-–](\d{2})\b')
re_catalog_number = re.compile(r'\b\d{4}[^\d]+\d+[^\d]+\d{4}\b')

def query(yob, yod):
    if yod < yob:
        return []
    return HumanItem.query.filter_by(yob=yob, yod=yod).all()

def get_items_from_name(name):
    found = []

    m = re_four_and_two.search(name)
    years = tuple(int(y) for y in re_four_digits.findall(name))

    print(name)

    yob1, yod1 = None, None
    if m:
        century = m.group(1)
        yob1 = int(century + m.group(2))
        yod1 = int(century + m.group(3))

        found += query(yob1, yod1)

    if len(years) == 2 and years != (yob1, yod1):
        print(years)
        found += query(*years)

    return found

def from_name(name):
    candidates = get_items_from_name(name)
    lookup = {item.qid: item for item in candidates}
    qids = list(lookup.keys())

    found = []
    for cur in utils.chunk(qids, 50):
        for entity in mediawiki.get_entities_with_cache(cur, props='labels|descriptions'):
            qid = entity['id']
            item = lookup[qid]
            i = {
                'qid': entity['id'],
                'year_of_birth': item.year_of_birth,
                'year_of_death': item.year_of_death,
            }
            label = mediawiki.get_entity_label(entity)
            if label:
                i['label'] = label
            if 'en' in entity['descriptions']:
                i['description'] = entity['descriptions']['en']['value']
            found.append(i)
    found.sort(key=lambda i: i['label'])
    return found
