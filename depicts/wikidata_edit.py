from depicts import mediawiki
from depicts.model import DepictsItem

def create_depicts_item(item_id):
    qid = f'Q{item_id}'
    entity = mediawiki.get_entity(qid)
    if 'en' in entity['labels']:
        label = entity['labels']['en']['value']
    else:
        label = None

    if 'en' in entity['descriptions']:
        description = entity['descriptions']['en']['value']
    else:
        description = None

    if 'en' in entity['aliases']:
        alt_labels = {alt['value'] for alt in entity['aliases']['en']}
    else:
        alt_labels = set()

    return DepictsItem(item_id=item_id,
                       label=label,
                       description=description,
                       alt_labels=alt_labels,
                       count=0)


