from depicts import mediawiki, wikibase
from depicts.model import DepictsItem

def create_depicts_item(item_id):
    qid = f'Q{item_id}'
    entity = mediawiki.get_entity(qid)

    if 'en' in entity['aliases']:
        alt_labels = {alt['value'] for alt in entity['aliases']['en']}
    else:
        alt_labels = set()

    return DepictsItem(item_id=item_id,
                       label=wikibase.get_en_label(entity),
                       description=wikibase.get_en_description(entity),
                       alt_labels=alt_labels,
                       count=0)
