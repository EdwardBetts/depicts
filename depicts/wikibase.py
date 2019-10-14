def first_datavalue(entity, pid):
    if pid in entity['claims']:
        mainsnak = entity['claims'][pid][0]['mainsnak']
        if 'datavalue' in mainsnak:
            return mainsnak['datavalue']['value']

def get_entity_label(entity):
    if 'en' in entity['labels']:
        return entity['labels']['en']['value']

    label_values = {l['value'] for l in entity['labels'].values()}
    if len(label_values) == 1:
        return list(label_values)[0]

def get_en_value(entity, key):
    if 'en' in entity[key]:
        return entity[key]['en']['value']

def get_en_label(entity):
    return get_en_value(entity, 'labels')

def get_en_description(entity):
    return get_en_value(entity, 'descriptions')
