from . import mediawiki

class Artwork:
    def __init__(self, qid):
        self.entity = mediawiki.get_entity_with_cache(qid)
        self.item_id = int(qid[1:])

        sites = ['commons', 'enwiki']
        self.parent_categories = {site: {} for site in sites}

    @property
    def image_filename(self):
        if 'P18' in self.entity['claims']:
            return self.entity['claims']['P18'][0]['mainsnak']['datavalue']['value']

    @property
    def display_title(self):
        if 'en' not in self.entity['labels']:
            return self.qid
        return f'{self.en_title} ({self.qid})'

    @property
    def url(self):
        return 'https://www.wikidata.org/wiki/' + self.qid

    def get_artist_entities(self):
        self.artist_entities = []

        for artist in self.artists_claim:
            artist_qid = artist['id']
            self.artist_entities.append(mediawiki.get_entity(artist_qid))

    def artist_labels(self):
        if not hasattr(self, 'artist_entities'):
            self.get_artist_entities()
        return [artist['labels']['en']['value'] for artist in self.artist_entities]

    @property
    def commons_cats(self):
        return [i['mainsnak']['datavalue']['value']
                for i in self.entity['claims'].get('P373', [])]

    @property
    def commons_sitelink(self):
        return self.sitelinks['commons']['value'] if 'commons' in self.sitelinks else None

    @property
    def en_title(self):
        if 'en' in self.entity['labels']:
            return self.entity['labels']['en']['value']
        else:
            return self.qid

    @property
    def artists_claim(self):
        return [image['mainsnak']['datavalue']['value']
                 for image in self.entity['claims'].get('P170', [])]

    @property
    def artists(self):
        if not hasattr(self, 'artist_entities'):
            self.get_artist_entities()

        items = [image['mainsnak']['datavalue']['value']
                 for image in self.entity['claims'].get('P170', [])]

        lookup = {artist['id']: artist['labels'] for artist in self.artist_entities}

        for item in items:
            item['labels'] = lookup[item['id']]

        return items

    @property
    def qid(self):
        return f'Q{self.item_id}'

    @property
    def commons_filenames(self):
        return [image['mainsnak']['datavalue']['value']
                for image in self.entity['claims'].get('P18', [])]

    def commons_cat_from_sitelink(self):
        ns = 'Category:'
        if not self.commons_sitelink or not self.commons_sitelink.startswith(ns):
            return
        return self.commons_sitelink[len(ns):]

    @property
    def enwiki_url(self):
        enwiki = self.enwiki
        if not enwiki:
            return
        return 'https://en.wikipedia.org/wiki/' + enwiki.replace(' ', '_')

    @property
    def sitelinks(self):
        return self.entity['sitelinks']

    @property
    def claims(self):
        return self.entity['claims']

    @property
    def enwiki(self):
        return self.sitelinks['enwiki']['title'] if 'enwiki' in self.sitelinks else None
