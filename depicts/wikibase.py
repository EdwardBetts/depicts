def first_datavalue(entity, pid):
    if pid in entity['claims']:
        return entity['claims'][pid][0]['mainsnak']['datavalue']['value']

def get_entity_label(entity):
    if 'en' in entity['labels']:
        return entity['labels']['en']['value']

    label_values = {l['value'] for l in entity['labels'].values()}
    if len(label_values) == 1:
        return list(label_values)[0]
